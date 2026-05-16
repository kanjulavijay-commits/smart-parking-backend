"""
Management command: python manage.py combine_datasets --ids 1,2,3

Merges 3 datasets from data_library/ into data_library/combined_master
for training a robust model.
"""

import os
import shutil
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Combine 3 specific datasets into a master training set."

    def add_arguments(self, parser):
        parser.add_argument("--ids", required=True, help="Comma-separated IDs of datasets to combine (e.g. 1,2,3)")
        parser.add_argument("--output", default="data_library/combined_master", help="Output folder")

    def handle(self, *args, **options):
        ids = options["ids"].split(",")
        output = options["output"]
        
        if len(ids) != 3:
            self.stderr.write("Error: You must select exactly 3 dataset IDs to combine.")
            return

        # Find the folders in data_library
        base_dir = "data_library"
        all_dirs = sorted([d for d in os.listdir(base_dir) if d.startswith("dataset_")])
        
        selected_dirs = []
        for i_str in ids:
            try:
                idx = int(i_str) - 1
                if 0 <= idx < len(all_dirs):
                    selected_dirs.append(all_dirs[idx])
                else:
                    self.stderr.write(f"Invalid ID: {i_str}")
                    return
            except ValueError:
                self.stderr.write(f"Invalid ID format: {i_str}")
                return

        self.stdout.write(f"Combining datasets: {', '.join(selected_dirs)}...")

        # Clear output folder
        if os.path.exists(output):
            shutil.rmtree(output)
        os.makedirs(output)

        for split in ["train", "val"]:
            for label in ["occupied", "vacant"]:
                os.makedirs(os.path.join(output, split, label), exist_ok=True)

        # In a real scenario, each dataset_XX folder would already have crops.
        # But for dataset_01 (Roboflow), we need to handle the structure.
        # To keep it simple, we'll look for 'occupied' and 'vacant' subfolders
        # or if it's the raw Roboflow folder, we'd need to run prepare_roboflow first.
        
        # For this tool, we assume we are combining PREPARED classification folders.
        # We'll check if the source has 'train/occupied'. If not, we'll warn the user.

        stats = {"occupied": 0, "vacant": 0}

        for dname in selected_dirs:
            src_path = os.path.join(base_dir, dname)
            
            # Special case: if it's dataset_01 and it's not prepared, we should mention it.
            # But let's look for images recursively to be robust.
            
            self.stdout.write(f"  Copying from {dname}...")
            
            found_any = False
            for root, dirs, files in os.walk(src_path):
                for fname in files:
                    if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                        continue
                    
                    label = ""
                    if "occupied" in root.lower() or "occupied" in fname.lower():
                        label = "occupied"
                    elif "vacant" in root.lower() or "empty" in root.lower() or "vacant" in fname.lower():
                        label = "vacant"
                    
                    if not label:
                        continue
                    
                    found_any = True
                    # Determine split (80/20)
                    split = "train" if stats[label] % 5 != 0 else "val"
                    
                    dst_dir = os.path.join(output, split, label)
                    dst_name = f"{dname}_{stats[label]:06d}_{fname}"
                    shutil.copy2(os.path.join(root, fname), os.path.join(dst_dir, dst_name))
                    stats[label] += 1
            
            if not found_any:
                self.stdout.write(self.style.WARNING(f"    Warning: No labeled images found in {dname}. Did you prepare it?"))

        self.stdout.write(self.style.SUCCESS(
            f"\nSuccess! Combined {stats['occupied']} occupied and {stats['vacant']} vacant images.\n"
            f"Master Dataset location: {output}/"
        ))
