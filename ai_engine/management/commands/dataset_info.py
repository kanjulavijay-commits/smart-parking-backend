"""
Management command: python manage.py dataset_info

Shows the status of all 12 datasets defined in this project.
Displays which are available on disk, which need downloading, and which
are auto-generated.

Usage:
  python manage.py dataset_info
"""

import os
from django.core.management.base import BaseCommand

STATUS_ICONS = {
    "available":    "[OK]",
    "not_found":    "[--]",
    "auto":         "[GEN]",
    "db":           "[DB]",
}


class Command(BaseCommand):
    help = "Display status of all 12 datasets used in this project."

    def handle(self, *args, **options):
        from ai_engine.datasets.registry import get_all_datasets

        self.stdout.write("\n" + "=" * 65)
        self.stdout.write("  Smart Parking — Dataset Status Report")
        self.stdout.write("=" * 65)

        all_ds = get_all_datasets()
        available_count = 0
        total_count = len(all_ds)

        DB_SOURCES    = {"Internal database", "database"}
        AUTO_SOURCES  = {"Generated locally", "generated"}

        for i, ds in enumerate(all_ds, start=1):
            is_avail = ds.is_available()
            src      = ds.source_url or ""

            if src in DB_SOURCES or "database" in src.lower():
                icon  = STATUS_ICONS["db"]
                label = "LIVE DB"
            elif src in AUTO_SOURCES or "generated" in src.lower():
                icon  = STATUS_ICONS["auto"]
                label = "AUTO-GEN"
            elif is_avail:
                icon  = STATUS_ICONS["available"]
                label = "READY"
            else:
                icon  = STATUS_ICONS["not_found"]
                label = "MISSING"

            if is_avail:
                available_count += 1

            self.stdout.write(f"\n  DS{i:02d}  {icon} [{label:8s}]  {ds.name}")
            self.stdout.write(f"         Desc  : {ds.description}")
            self.stdout.write(f"         Type  : {ds.dataset_type}")
            self.stdout.write(f"         Source: {src}")

        self.stdout.write("\n" + "-" * 65)
        self.stdout.write(f"  {available_count}/{total_count} datasets available")
        self.stdout.write("=" * 65 + "\n")

        # Show model checkpoint statuses
        self.stdout.write("  Trained Model Checkpoints")
        self.stdout.write("-" * 65)
        checkpoints = {
            "CNN  (MobileNetV2)  ": "ai_engine/checkpoints/cnn_best.pth",
            "Random Forest       ": "ai_engine/checkpoints/random_forest.pkl",
            "LSTM Forecaster     ": "ai_engine/checkpoints/lstm_model.pth",
        }
        for label, path in checkpoints.items():
            exists = os.path.exists(path)
            icon   = STATUS_ICONS["available"] if exists else STATUS_ICONS["not_found"]
            status = "TRAINED" if exists else "not trained yet"
            size_str = ""
            if exists:
                size_kb = os.path.getsize(path) / 1024
                size_str = f"  ({size_kb:.0f} KB)"
            self.stdout.write(f"  {icon} {label}: {status}{size_str}")

        self.stdout.write("")
        self.stdout.write("  Quick-start (no downloads needed):")
        self.stdout.write("    python manage.py generate_synthetic_dataset")
        self.stdout.write("    python manage.py train_cnn_combined")
        self.stdout.write("    python manage.py train_random_forest --synthetic")
        self.stdout.write("    python manage.py train_lstm")
        self.stdout.write("=" * 65 + "\n")
