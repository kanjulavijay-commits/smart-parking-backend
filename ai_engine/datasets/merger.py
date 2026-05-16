"""
ai_engine/datasets/merger.py

Merges multiple image datasets into one unified training set.
Primary combination: PKLot (DS1) + CNRPark (DS2) + SynthParking (DS6).

Why these three?
  PKLot       → Real outdoor images, 3 weather conditions, Brazilian lots
  CNRPark     → Real images, 9 cameras, Italian lot (different geography)
  SynthParking → Generated images, always available, extreme variation

Together they cover: geography diversity, lighting diversity,
weather diversity, and camera-angle diversity.

Usage:
    from ai_engine.datasets.merger import DatasetMerger
    merger = DatasetMerger(["PKLot", "CNRPark-EXT", "SynthParking"])
    train_samples = merger.get_merged_samples("train")
    # Returns list of (image_path, label) tuples — feed directly to ParkingDataset
"""

import random
from .registry import get_dataset


class DatasetMerger:
    """
    Merges multiple image datasets into a single sample list.
    Automatically skips datasets that aren't available on disk.
    """

    PRIMARY_COMBINATION = ["PKLot", "CNRPark-EXT", "SynthParking"]

    def __init__(self, dataset_names=None, max_per_dataset=None, balance=True):
        """
        Args:
            dataset_names: list of dataset names to merge (default: primary combination)
            max_per_dataset: cap samples per dataset (None = no cap)
            balance: if True, equalize occupied vs vacant counts in final set
        """
        self.dataset_names = dataset_names or self.PRIMARY_COMBINATION
        self.max_per_dataset = max_per_dataset
        self.balance = balance
        self._datasets = []
        self._load_datasets()

    def _load_datasets(self):
        for name in self.dataset_names:
            try:
                ds = get_dataset(name)
                if ds.is_available():
                    self._datasets.append(ds)
                else:
                    print(f"  [merger] Skipping {name} — not downloaded yet")
            except KeyError:
                print(f"  [merger] Unknown dataset: {name}")

        if not self._datasets:
            print("  [merger] WARNING: No datasets available. Generate synthetic data first.")
            print("           Run: python manage.py generate_synthetic_dataset")

    @property
    def available_datasets(self):
        return [ds.name for ds in self._datasets]

    def get_merged_samples(self, split="train"):
        """
        Return merged (path, label) list from all available datasets.
        """
        all_samples = []
        for ds in self._datasets:
            samples = ds.get_image_samples(split)
            if self.max_per_dataset:
                random.shuffle(samples)
                samples = samples[:self.max_per_dataset]
            all_samples.extend(samples)
            print(f"  [merger] {ds.name}: {len(samples)} {split} samples")

        if not all_samples:
            return []

        if self.balance:
            all_samples = self._balance(all_samples)

        random.shuffle(all_samples)
        return all_samples

    def _balance(self, samples):
        """Equalize class distribution by undersampling the majority class."""
        occupied = [s for s in samples if s[1] == 1]
        vacant   = [s for s in samples if s[1] == 0]
        min_count = min(len(occupied), len(vacant))
        occupied = random.sample(occupied, min_count)
        vacant   = random.sample(vacant,   min_count)
        return occupied + vacant

    def summary(self):
        """Print a summary of the merged dataset."""
        print(f"\nDataset Merger — {len(self._datasets)} datasets combined")
        print(f"Combination: {' + '.join(self.available_datasets)}")
        for split in ("train", "val"):
            samples = self.get_merged_samples(split)
            occupied = sum(1 for _, l in samples if l == 1)
            vacant   = sum(1 for _, l in samples if l == 0)
            print(f"  {split:5s}: {len(samples):6,d} total | {occupied:,d} occupied | {vacant:,d} vacant")
        print()


class MergedParkingDataset:
    """
    PyTorch-compatible Dataset that wraps the DatasetMerger.
    Drop-in replacement for ParkingDataset from train.py.

    Usage:
        merger = DatasetMerger()
        train_ds = MergedParkingDataset(merger, split="train", transform=...)
    """

    def __init__(self, merger, split="train", transform=None):
        import torch
        from PIL import Image as PILImage
        self._torch = torch
        self._Image = PILImage
        self.transform = transform
        self.samples = merger.get_merged_samples(split)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = self._Image.open(path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, self._torch.tensor(label, dtype=self._torch.float32)
