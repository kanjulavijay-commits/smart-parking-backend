"""
Management command: python manage.py generate_synthetic_dataset

Generates Dataset 6 (SynthParking) — synthetic parking slot images.
No download required. Runs completely offline using Python + PIL.

Usage:
  python manage.py generate_synthetic_dataset               # 3000 per class
  python manage.py generate_synthetic_dataset --count 1000 # smaller/faster
  python manage.py generate_synthetic_dataset --count 5000 # larger/more accurate
"""

import os
import time
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate synthetic parking slot images (Dataset 6 — SynthParking)."

    def add_arguments(self, parser):
        parser.add_argument("--count",  type=int, default=3000,
                            help="Images per class (occupied + vacant). Default: 3000 each.")
        parser.add_argument("--output", default=os.path.join("ai_engine", "data", "synthetic"),
                            help="Output directory.")
        parser.add_argument("--val_split", type=float, default=0.2)

    def handle(self, *args, **options):
        from ai_engine.datasets.synthetic_generator import generate_dataset

        count     = options["count"]
        output    = options["output"]
        val_split = options["val_split"]

        self.stdout.write(f"\nGenerating {count:,} occupied + {count:,} vacant images...")
        self.stdout.write(f"Output: {output}/\n")

        t0 = time.time()
        stats = generate_dataset(
            output_dir=output,
            n_occupied=count,
            n_vacant=count,
            val_split=val_split,
        )
        elapsed = time.time() - t0

        self.stdout.write(self.style.SUCCESS(
            f"\nDataset 6 (SynthParking) ready!\n"
            f"  Train: {stats['train_occupied']:,} occupied, {stats['train_vacant']:,} vacant\n"
            f"  Val  : {stats['val_occupied']:,}   occupied, {stats['val_vacant']:,}   vacant\n"
            f"  Total: {stats['total']:,} images in {elapsed:.0f}s\n"
            f"  Path : {stats['output_dir']}/\n\n"
            f"Next: python manage.py train_cnn_combined"
        ))
