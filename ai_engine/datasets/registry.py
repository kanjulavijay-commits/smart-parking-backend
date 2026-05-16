"""
ai_engine/datasets/registry.py

Definitions for all 12 datasets.

Datasets 1-5, 7-11 require manual download (instructions in each class).
Dataset 6  — fully generated with Python/PIL, no download needed.
Dataset 12 — extracted live from the Django booking database.

Usage:
    from ai_engine.datasets.registry import get_all_datasets, get_dataset
    ds = get_dataset("pklot")
    print(ds.info())
"""

import os
from .base import BaseDataset


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 1 — PKLot
# ─────────────────────────────────────────────────────────────────────────────
class PKLotDataset(BaseDataset):
    """
    The gold-standard parking dataset.
    12,417 images from 3 Brazilian parking lots under 3 weather conditions.
    Each image is a single cropped parking slot: occupied or empty.

    Download: https://www.kaggle.com/datasets/ammarnassanalhajali/pklot-dataset
    Extract to: ai_engine/data/pklot/
    Expected structure:
      ai_engine/data/pklot/train/occupied/  ai_engine/data/pklot/train/empty/
      ai_engine/data/pklot/test/occupied/   ai_engine/data/pklot/test/empty/
    """
    name        = "PKLot"
    description = "12,417 parking slot images — 3 lots, 3 weather conditions (UFPR, Brazil)"
    source_url  = "https://www.kaggle.com/datasets/ammarnassanalhajali/pklot-dataset"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "pklot")

    def is_available(self):
        return os.path.isdir(os.path.join(self.ROOT, "train", "occupied"))

    def get_image_samples(self, split="train"):
        split_map = {"val": "test", "train": "train"}
        folder = os.path.join(self.ROOT, split_map.get(split, split))
        samples = []
        for label_name, label_idx in [("occupied", 1), ("empty", 0), ("vacant", 0)]:
            d = os.path.join(folder, label_name)
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.lower().endswith((".jpg", ".jpeg", ".png")):
                        samples.append((os.path.join(d, f), label_idx))
        return samples


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 2 — CNRPark-EXT
# ─────────────────────────────────────────────────────────────────────────────
class CNRParkDataset(BaseDataset):
    """
    144,965 patches from 9 cameras in an Italian parking lot.
    Captures extreme lighting variation — best for robustness training.

    Download: http://cnrpark.it/  (free registration)
    Extract to: ai_engine/data/cnrpark/
    Expected structure:
      ai_engine/data/cnrpark/train/occupied/
      ai_engine/data/cnrpark/train/free/
    """
    name        = "CNRPark-EXT"
    description = "144,965 parking patches from 9 cameras (Italian lot, day/night/weather)"
    source_url  = "http://cnrpark.it/"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "cnrpark")

    def is_available(self):
        return os.path.isdir(os.path.join(self.ROOT, "train", "occupied"))

    def get_image_samples(self, split="train"):
        folder = os.path.join(self.ROOT, split)
        samples = []
        for label_name, label_idx in [("occupied", 1), ("free", 0), ("vacant", 0), ("empty", 0)]:
            d = os.path.join(folder, label_name)
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.lower().endswith((".jpg", ".jpeg", ".png")):
                        samples.append((os.path.join(d, f), label_idx))
        return samples


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 3 — ACPDS (Aerial Car Park Detection)
# ─────────────────────────────────────────────────────────────────────────────
class ACPDSDataset(BaseDataset):
    """
    Overhead/aerial view parking lot images with bounding-box annotations.
    Used for top-down camera parking detection (different from ground-level).

    Download: https://github.com/Baneeishaque/ACPDS
    Extract to: ai_engine/data/acpds/
    """
    name        = "ACPDS"
    description = "Aerial parking lot detection — overhead camera view with bounding boxes"
    source_url  = "https://github.com/Baneeishaque/ACPDS"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "acpds")

    def is_available(self):
        return os.path.isdir(self.ROOT) and any(
            f.endswith((".jpg", ".png")) for f in os.listdir(self.ROOT)
            if os.path.isfile(os.path.join(self.ROOT, f))
        )


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 4 — SpotFinder (Indoor Parking)
# ─────────────────────────────────────────────────────────────────────────────
class SpotFinderDataset(BaseDataset):
    """
    Indoor multi-level parking images with overhead lighting.
    Complements outdoor PKLot — captures fluorescent lighting, concrete walls.

    Download: Collect or use OPIXray / similar indoor datasets.
    Extract to: ai_engine/data/spotfinder/
    """
    name        = "SpotFinder"
    description = "Indoor parking slot images — fluorescent lighting, multi-level garages"
    source_url  = "https://www.kaggle.com/datasets/search?q=indoor+parking"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "spotfinder")

    def is_available(self):
        return os.path.isdir(os.path.join(self.ROOT, "train"))


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 5 — CARPK (Drone-View Counting)
# ─────────────────────────────────────────────────────────────────────────────
class CARPKDataset(BaseDataset):
    """
    1,448 drone-captured images of parking lots. 89,777 car annotations.
    Used for counting total parked cars in large open lots.

    Download: https://lafi.github.io/LPN/  (free)
    Extract to: ai_engine/data/carpk/
    """
    name        = "CARPK"
    description = "1,448 drone-view parking images — 89,777 car bounding boxes for counting"
    source_url  = "https://lafi.github.io/LPN/"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "carpk")

    def is_available(self):
        return os.path.isdir(self.ROOT)


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 6 — SynthParking (Generated — NO DOWNLOAD NEEDED)
# ─────────────────────────────────────────────────────────────────────────────
class SynthParkingDataset(BaseDataset):
    """
    Fully synthetic parking slot images generated with Python + PIL.
    Created programmatically: no download, no registration, instant training.

    Run: python manage.py generate_synthetic_dataset
    Output: ai_engine/data/synthetic/
    """
    name        = "SynthParking"
    description = "Synthetically generated parking slots (PIL) — no download, instant training"
    source_url  = "Generated locally"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "synthetic")

    def is_available(self):
        return os.path.isdir(os.path.join(self.ROOT, "train", "occupied"))

    def get_image_samples(self, split="train"):
        folder = os.path.join(self.ROOT, split)
        samples = []
        for label_name, label_idx in [("occupied", 1), ("vacant", 0)]:
            d = os.path.join(folder, label_name)
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.lower().endswith(".png"):
                        samples.append((os.path.join(d, f), label_idx))
        return samples


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 7 — OpenImages Cars Subset
# ─────────────────────────────────────────────────────────────────────────────
class OpenImagesCarsDataset(BaseDataset):
    """
    Google Open Images V7 — cars subset (~200k vehicle images).
    Used for vehicle type classification (car, truck, bike, bus).

    Download via: pip install openimages  then  openimages download --category Car
    Extract to: ai_engine/data/openimages/
    """
    name        = "OpenImages-Cars"
    description = "Google Open Images cars subset — vehicle type classification"
    source_url  = "https://storage.googleapis.com/openimages/web/index.html"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "openimages")

    def is_available(self):
        return os.path.isdir(os.path.join(self.ROOT, "Car"))


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 8 — Stanford Cars
# ─────────────────────────────────────────────────────────────────────────────
class StanfordCarsDataset(BaseDataset):
    """
    16,185 images of 196 car classes (make, model, year).
    Used for fine-grained vehicle recognition at the parking gate.

    Download: https://www.kaggle.com/datasets/jessicali9530/stanford-cars-dataset
    Extract to: ai_engine/data/stanford_cars/
    """
    name        = "StanfordCars"
    description = "16,185 car images, 196 classes — make/model/year recognition"
    source_url  = "https://www.kaggle.com/datasets/jessicali9530/stanford-cars-dataset"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "stanford_cars")

    def is_available(self):
        return os.path.isdir(os.path.join(self.ROOT, "cars_train"))


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 9 — Vehicle Re-ID
# ─────────────────────────────────────────────────────────────────────────────
class VehicleReIDDataset(BaseDataset):
    """
    VeRi-776: 776 vehicles across 20 cameras.
    Used for tracking the same vehicle across multiple parking cameras.

    Download: https://vehiclereid.github.io/VeRi/
    Extract to: ai_engine/data/vehicle_reid/
    """
    name        = "VehicleReID"
    description = "VeRi-776 — 776 vehicles across 20 cameras for cross-camera tracking"
    source_url  = "https://vehiclereid.github.io/VeRi/"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "vehicle_reid")

    def is_available(self):
        return os.path.isdir(self.ROOT)


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 10 — Indian License Plates
# ─────────────────────────────────────────────────────────────────────────────
class IndianLicensePlateDataset(BaseDataset):
    """
    Indian vehicle license plate images with OCR annotations.
    Used for automatic number plate recognition (ANPR) at the gate.

    Download: https://www.kaggle.com/datasets/saisirishan/indian-vehicle-dataset
    Extract to: ai_engine/data/license_plates/
    """
    name        = "IndianLicensePlates"
    description = "Indian number plate images — ANPR/OCR for gate automation"
    source_url  = "https://www.kaggle.com/datasets/saisirishan/indian-vehicle-dataset"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "license_plates")

    def is_available(self):
        return os.path.isdir(self.ROOT)


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 11 — Weather Classification
# ─────────────────────────────────────────────────────────────────────────────
class WeatherDataset(BaseDataset):
    """
    Weather condition images: sunny, cloudy, rainy, foggy.
    Used to adapt CNN confidence thresholds based on current conditions.
    (Rain degrades camera quality → lower confidence threshold needed)

    Download: https://www.kaggle.com/datasets/pratik2901/multiclass-weather-dataset
    Extract to: ai_engine/data/weather/
    """
    name        = "WeatherClassification"
    description = "Multiclass weather images — adapts CNN confidence threshold per condition"
    source_url  = "https://www.kaggle.com/datasets/pratik2901/multiclass-weather-dataset"
    dataset_type = "image"
    ROOT        = os.path.join("ai_engine", "data", "weather")

    def is_available(self):
        return os.path.isdir(self.ROOT)

    def get_image_samples(self, split="train"):
        folder = os.path.join(self.ROOT, split)
        samples = []
        for condition in ("sunny", "cloudy", "rainy", "foggy", "shine", "sunrise"):
            d = os.path.join(folder, condition)
            if os.path.isdir(d):
                label = 0 if condition in ("sunny", "shine", "sunrise") else 1
                for f in os.listdir(d):
                    if f.lower().endswith((".jpg", ".jpeg", ".png")):
                        samples.append((os.path.join(d, f), label))
        return samples


# ─────────────────────────────────────────────────────────────────────────────
# DATASET 12 — Booking History (Internal Django DB)
# ─────────────────────────────────────────────────────────────────────────────
class BookingHistoryDataset(BaseDataset):
    """
    Extracted live from your Django database.
    No download — uses YOUR system's real booking records.
    Features: hour, day_of_week, lot, zone, month, is_weekend, occupancy_rate
    Target:   slot available (0) or occupied (1) at a given time window.

    Used by: Random Forest (availability prediction) + LSTM (time-series forecast).
    """
    name        = "BookingHistory"
    description = "Live booking records from your Django DB — for RF and LSTM models"
    source_url  = "Internal database"
    dataset_type = "tabular"

    def is_available(self):
        try:
            from bookings.models import Booking
            return Booking.objects.exists()
        except Exception:
            return False

    def get_tabular_samples(self):
        """Extract features from booking history as a pandas DataFrame."""
        import pandas as pd
        from bookings.models import Booking

        bookings = Booking.objects.select_related(
            "slot__zone__floor__lot"
        ).values(
            "start_time", "end_time", "status",
            "slot__zone__floor__lot__name",
            "slot__zone__name",
        )

        rows = []
        for b in bookings:
            st = b["start_time"]
            if st is None:
                continue
            rows.append({
                "hour":         st.hour,
                "day_of_week":  st.weekday(),    # 0=Monday, 6=Sunday
                "month":        st.month,
                "is_weekend":   int(st.weekday() >= 5),
                "lot_name":     b["slot__zone__floor__lot__name"] or "",
                "zone_name":    b["slot__zone__name"] or "",
                "status":       b["status"],
                "is_occupied":  int(b["status"] in ("confirmed", "active", "completed")),
            })

        return pd.DataFrame(rows) if rows else pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────
_ALL_DATASETS = [
    PKLotDataset(),
    CNRParkDataset(),
    ACPDSDataset(),
    SpotFinderDataset(),
    CARPKDataset(),
    SynthParkingDataset(),
    OpenImagesCarsDataset(),
    StanfordCarsDataset(),
    VehicleReIDDataset(),
    IndianLicensePlateDataset(),
    WeatherDataset(),
    BookingHistoryDataset(),
]

_DATASET_MAP = {ds.name.lower().replace("-", "").replace("_", ""): ds for ds in _ALL_DATASETS}


def get_all_datasets():
    return _ALL_DATASETS


def get_dataset(name: str) -> BaseDataset:
    key = name.lower().replace("-", "").replace("_", "").replace(" ", "")
    ds = _DATASET_MAP.get(key)
    if ds is None:
        available = ", ".join(_DATASET_MAP.keys())
        raise KeyError(f"Dataset '{name}' not found. Available: {available}")
    return ds
