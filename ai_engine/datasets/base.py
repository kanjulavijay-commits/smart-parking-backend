"""
ai_engine/datasets/base.py

Abstract base class for all 12 parking datasets.
Every dataset has a consistent interface:
  - .name, .description, .source_url
  - .is_available()  → True if data files are present
  - .get_image_samples(split)  → list of (path, label) for CNN
  - .get_tabular_samples()     → DataFrame for RF/LSTM
  - .info()          → prints dataset statistics
"""

import os
from abc import ABC, abstractmethod


class BaseDataset(ABC):
    name: str = "unnamed"
    description: str = ""
    source_url: str = ""
    dataset_type: str = "image"  # "image" | "tabular" | "both"

    def is_available(self) -> bool:
        """Return True if the data files are actually present on disk."""
        return False

    def get_image_samples(self, split="train"):
        """
        Return list of (image_path, label) tuples.
        label: 1 = occupied, 0 = vacant
        split: "train" or "val"
        """
        return []

    def get_tabular_samples(self):
        """Return a pandas DataFrame for RF/LSTM training."""
        return None

    def info(self):
        available = "AVAILABLE" if self.is_available() else "not downloaded"
        print(f"[{self.name}] {self.description}")
        print(f"  Type   : {self.dataset_type}")
        print(f"  Source : {self.source_url}")
        print(f"  Status : {available}")
        if self.is_available():
            samples = self.get_image_samples("train")
            if samples:
                occupied = sum(1 for _, l in samples if l == 1)
                vacant   = sum(1 for _, l in samples if l == 0)
                print(f"  Train  : {occupied} occupied, {vacant} vacant")
        print()
