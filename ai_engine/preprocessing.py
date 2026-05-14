"""
ai_engine/preprocessing.py — Image preprocessing with OpenCV.

Pipeline:
  Raw camera frame → Extract slot ROI → Normalize → Tensor

Designed for PKLot / CNRPark dataset conventions:
  - Slot images: 64x64 RGB
  - Pixel values normalized to [0, 1]
  - Data augmentation during training only
"""

import cv2
import numpy as np


SLOT_IMG_SIZE = (64, 64)


def preprocess_slot_image(image_or_path, augment=False):
    """
    Load and preprocess a single parking slot image.

    Args:
        image_or_path: file path string OR numpy BGR image array
        augment: apply random augmentation (True during training only)

    Returns:
        numpy float32 array of shape (3, 64, 64) — channels first for PyTorch
    """
    if isinstance(image_or_path, str):
        img = cv2.imread(image_or_path)
        if img is None:
            raise FileNotFoundError(f"Cannot open image: {image_or_path}")
    else:
        img = image_or_path.copy()

    # Convert BGR → RGB (OpenCV reads as BGR, models expect RGB)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Resize to standard slot size
    img = cv2.resize(img, SLOT_IMG_SIZE, interpolation=cv2.INTER_AREA)

    if augment:
        img = _augment(img)

    # Normalize to [0, 1]
    img = img.astype(np.float32) / 255.0

    # HWC → CHW (height, width, channels) → (channels, height, width)
    img = np.transpose(img, (2, 0, 1))

    return img


def extract_slot_roi(frame, slot_coords):
    """
    Crop a single slot region from a full camera frame.

    Args:
        frame: full camera frame as numpy array (H, W, 3)
        slot_coords: dict with keys x, y, w, h (pixel coordinates)

    Returns:
        Cropped slot image as numpy array
    """
    x = int(slot_coords["x"])
    y = int(slot_coords["y"])
    w = int(slot_coords["w"])
    h = int(slot_coords["h"])
    return frame[y:y + h, x:x + w]


def preprocess_camera_frame(frame_bytes):
    """
    Decode a raw JPEG/PNG frame received from a camera stream.

    Args:
        frame_bytes: raw bytes from camera

    Returns:
        numpy BGR image array
    """
    nparr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return frame


def _augment(img):
    """Random flips and brightness jitter — increases dataset diversity."""
    # Horizontal flip
    if np.random.rand() > 0.5:
        img = cv2.flip(img, 1)

    # Brightness/contrast jitter
    alpha = np.random.uniform(0.8, 1.2)   # contrast
    beta = np.random.randint(-20, 20)      # brightness
    img = np.clip(alpha * img.astype(np.float32) + beta, 0, 255).astype(np.uint8)

    # Random rotation ±15°
    angle = np.random.uniform(-15, 15)
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    img = cv2.warpAffine(img, M, (w, h))

    return img


def batch_preprocess(image_paths, augment=False):
    """Preprocess a list of image paths into a batched numpy array."""
    batch = []
    for path in image_paths:
        try:
            img = preprocess_slot_image(path, augment=augment)
            batch.append(img)
        except Exception:
            continue
    return np.stack(batch, axis=0) if batch else np.array([])
