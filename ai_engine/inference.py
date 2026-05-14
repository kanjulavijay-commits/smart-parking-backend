"""
ai_engine/inference.py — Real-time slot occupancy inference pipeline.

Flow:
  Camera frame (JPEG bytes) → OpenCV decode → Extract slot ROIs → CNN inference
  → Confidence scores → Update ParkingSlot status in DB → Return results

The inference engine is stateless — it can be called per-frame or on a schedule.
In production: connect to RTSP streams via ParkingCamera model.
"""

import os
import io
import numpy as np
import torch
from torchvision import transforms
from PIL import Image
from django.conf import settings

from .model import load_model, build_model
from .preprocessing import preprocess_camera_frame, extract_slot_roi, SLOT_IMG_SIZE


# ImageNet normalization — must match training transforms
_NORMALIZE = transforms.Normalize(
    mean=[0.485, 0.456, 0.406],
    std=[0.229, 0.224, 0.225],
)

_INFERENCE_TRANSFORM = transforms.Compose([
    transforms.Resize(SLOT_IMG_SIZE),
    transforms.ToTensor(),
    _NORMALIZE,
])

_MODEL_CACHE = {}  # module-level cache so we don't reload on every request


def get_model(checkpoint_path=None, device="cpu"):
    """
    Return the inference model.
    Loads from checkpoint if provided, otherwise returns an untrained model
    (useful for development before training is done).
    """
    cache_key = checkpoint_path or "untrained"
    if cache_key not in _MODEL_CACHE:
        if checkpoint_path and os.path.exists(checkpoint_path):
            model = load_model(checkpoint_path, device=device)
        else:
            model = build_model(pretrained=False)
            model.eval()
        _MODEL_CACHE[cache_key] = model
    return _MODEL_CACHE[cache_key]


def _img_to_tensor(img_array):
    """Convert numpy RGB array (H, W, 3) to a normalized PyTorch tensor."""
    pil_img = Image.fromarray(img_array)
    return _INFERENCE_TRANSFORM(pil_img).unsqueeze(0)  # add batch dim


def predict_slot_occupancy(img_array, checkpoint_path=None, threshold=0.5):
    """
    Predict whether a single slot image is occupied or vacant.

    Args:
        img_array: numpy RGB array of the slot (already cropped)
        checkpoint_path: path to .pth model file (None = use untrained model)
        threshold: probability threshold for "occupied"

    Returns:
        dict: { "is_occupied": bool, "confidence": float }
    """
    model = get_model(checkpoint_path)
    tensor = _img_to_tensor(img_array)

    with torch.no_grad():
        prob = torch.sigmoid(model(tensor)).item()

    return {
        "is_occupied": prob >= threshold,
        "confidence": round(prob if prob >= threshold else 1 - prob, 4),
        "raw_probability": round(prob, 4),
    }


def analyze_camera_frame(frame_bytes, slot_coordinates, checkpoint_path=None):
    """
    Full pipeline: decode a camera frame, analyze all slots in it.

    Args:
        frame_bytes: raw JPEG/PNG bytes from camera
        slot_coordinates: list of dicts [{ "slot_id": str, "x", "y", "w", "h" }]
        checkpoint_path: path to trained model

    Returns:
        list of dicts: [{ "slot_id", "is_occupied", "confidence", "raw_probability" }]
    """
    frame = preprocess_camera_frame(frame_bytes)
    if frame is None:
        raise ValueError("Could not decode camera frame.")

    results = []
    for coord in slot_coordinates:
        roi = extract_slot_roi(frame, coord)
        if roi.size == 0:
            continue

        import cv2
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        prediction = predict_slot_occupancy(roi_rgb, checkpoint_path)
        prediction["slot_id"] = coord["slot_id"]
        results.append(prediction)

    return results


def sync_slot_statuses(camera_id, frame_bytes, checkpoint_path=None):
    """
    High-level function: analyze a camera frame and update ParkingSlot DB records.
    Called from the API view when a camera posts a new frame.

    Returns: { "updated": int, "results": list }
    """
    from parking.models import ParkingCamera, ParkingSlot, SensorData

    try:
        camera = ParkingCamera.objects.get(id=camera_id, is_active=True)
    except ParkingCamera.DoesNotExist:
        raise ValueError(f"Camera {camera_id} not found or inactive.")

    # Get slots in this camera's zone with their stored coordinates
    slots = ParkingSlot.objects.filter(
        zone=camera.zone,
        is_active=True,
        floor_position_x__isnull=False,
    ).values("id", "slot_number", "floor_position_x", "floor_position_y")

    # Build coordinate list (using stored grid positions scaled to pixel coords)
    SCALE = 80  # pixels per grid unit
    slot_coords = [
        {
            "slot_id": str(s["id"]),
            "x": int(s["floor_position_x"] * SCALE),
            "y": int(s["floor_position_y"] * SCALE),
            "w": 70,
            "h": 70,
        }
        for s in slots
    ]

    results = analyze_camera_frame(frame_bytes, slot_coords, checkpoint_path)

    updated = 0
    for r in results:
        try:
            slot = ParkingSlot.objects.get(id=r["slot_id"])
            new_status = "occupied" if r["is_occupied"] else "available"

            # Record sensor data for analytics
            SensorData.objects.create(
                slot=slot,
                is_occupied=r["is_occupied"],
                confidence_score=r["confidence"],
                raw_value=r["raw_probability"],
            )

            # Only update if status changed (avoid unnecessary DB writes)
            if slot.status != new_status and slot.status not in ("reserved", "maintenance"):
                slot.status = new_status
                slot.save(update_fields=["status", "updated_at"])
                updated += 1
        except ParkingSlot.DoesNotExist:
            continue

    return {"updated": updated, "results": results}
