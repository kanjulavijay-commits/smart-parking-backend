"""
Management command: python manage.py prepare_dataset --source <path>

Organizes a downloaded PKLot (or CNRPark) dataset into the folder structure
that train.py expects:

  dataset/
    train/
      occupied/
      vacant/
    val/
      occupied/
      vacant/

Handles two common PKLot download formats:
  Format A (Kaggle): train/occupied/, train/empty/
  Format B (UFPR):   PUCPR/Sunny/2012-09-12/*.jpg  (label in filename: _0=vacant, _1=occupied)

Usage:
  python manage.py prepare_dataset --source C:/Downloads/PKLot
  python manage.py prepare_dataset --source C:/Downloads/PKLot --val_split 0.2 --limit 5000
"""

import os
import shutil
import random
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Organize a PKLot download into the dataset/ folder for training."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Path to your downloaded PKLot folder")
        parser.add_argument("--output", default="dataset", help="Output folder (default: dataset/)")
        parser.add_argument("--val_split", type=float, default=0.2, help="Fraction of data for validation (default: 0.2)")
        parser.add_argument("--limit", type=int, default=0, help="Max images per class (0 = no limit)")

    def handle(self, *args, **options):
        source = options["source"]
        output = options["output"]
        val_split = options["val_split"]
        limit = options["limit"]

        if not os.path.exists(source):
            self.stderr.write(f"Source folder not found: {source}")
            return

        self.stdout.write(f"Scanning {source} ...")
        occupied, vacant = self._collect_images(source)

        if not occupied and not vacant:
            self.stderr.write(
                "No images found. Make sure you extracted the zip file correctly.\n"
                "Expected to find images in 'occupied/' and 'empty/' or 'vacant/' subfolders,\n"
                "or PKLot-style filenames ending in _0.jpg (vacant) or _1.jpg (occupied)."
            )
            return

        self.stdout.write(f"Found: {len(occupied)} occupied, {len(vacant)} vacant")

        # Balance classes and apply limit
        min_count = min(len(occupied), len(vacant))
        if limit > 0:
            min_count = min(min_count, limit)

        random.seed(42)
        occupied = random.sample(occupied, min_count)
        vacant = random.sample(vacant, min_count)

        self.stdout.write(f"Using: {min_count} per class (balanced)")

        # Create output folders
        for split in ("train", "val"):
            for label in ("occupied", "vacant"):
                os.makedirs(os.path.join(output, split, label), exist_ok=True)

        # Split and copy
        split_idx = int(min_count * (1 - val_split))
        stats = {"train": 0, "val": 0}

        for i, (img_path, label) in enumerate(occupied + vacant):
            is_occupied = label == "occupied"
            label_name = "occupied" if is_occupied else "vacant"
            split = "train" if i % (min_count * 2) < split_idx * 2 or i % (min_count * 2) >= min_count + split_idx else "val"

            # Simpler split: first 80% train, last 20% val per class
            class_idx = i % min_count
            split = "train" if class_idx < split_idx else "val"

            dst_dir = os.path.join(output, split, label_name)
            dst_file = os.path.join(dst_dir, f"{label_name}_{i:06d}{os.path.splitext(img_path)[1]}")
            shutil.copy2(img_path, dst_file)
            stats[split] += 1

        for split in ("train", "val"):
            occ = len(os.listdir(os.path.join(output, split, "occupied")))
            vac = len(os.listdir(os.path.join(output, split, "vacant")))
            self.stdout.write(f"  {split}: {occ} occupied, {vac} vacant")

        self.stdout.write(self.style.SUCCESS(
            f"\nDataset ready at '{output}/'.\n"
            f"Next step: python manage.py train_model"
        ))

    def _collect_images(self, source):
        """Auto-detect PKLot format and collect (path, label) pairs."""
        occupied, vacant = [], []
        IMG_EXTS = {".jpg", ".jpeg", ".png"}

        for root, dirs, files in os.walk(source):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if os.path.splitext(fname)[1].lower() not in IMG_EXTS:
                    continue
                fpath = os.path.join(root, fname)
                folder = os.path.basename(root).lower()

                # Format A: Kaggle-style folder names
                if folder in ("occupied",):
                    occupied.append((fpath, "occupied"))
                elif folder in ("empty", "vacant", "free"):
                    vacant.append((fpath, "vacant"))
                # Format B: UFPR filename convention (_1 = occupied, _0 = vacant)
                elif fname.endswith("_1.jpg") or fname.endswith("_1.png"):
                    occupied.append((fpath, "occupied"))
                elif fname.endswith("_0.jpg") or fname.endswith("_0.png"):
                    vacant.append((fpath, "vacant"))

        return occupied, vacant
