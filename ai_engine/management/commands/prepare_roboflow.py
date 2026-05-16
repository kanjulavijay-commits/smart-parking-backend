"""
Management command: python manage.py prepare_roboflow --source <path>

Converts a Roboflow Object Detection dataset (full frames + COCO JSON) 
into a Classification dataset (cropped slots) that train_model expects.
"""

import os
import json
import random
from PIL import Image
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Convert Roboflow Object Detection data to Classification crops."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Path to extracted Roboflow folder (contains train/valid/test)")
        parser.add_argument("--output", default="dataset", help="Output folder (default: dataset/)")
        parser.add_argument("--limit", type=int, default=3000, help="Max images per class (default: 3000)")

    def handle(self, *args, **options):
        source = options["source"]
        output = options["output"]
        limit = options["limit"]

        if not os.path.exists(source):
            self.stderr.write(f"Source not found: {source}")
            return

        # Mapping from Roboflow IDs to our labels
        # id 1: space-empty -> vacant
        # id 2: space-occupied -> occupied
        CATEGORY_MAP = {1: "vacant", 2: "occupied"}

        counts = {"occupied": 0, "vacant": 0}
        
        # We'll process train, valid, test and map them to our train/val splits
        splits = {
            "train": "train",
            "valid": "val",
            "test": "val" # combine test into val for training purposes
        }

        self.stdout.write(f"Processing Roboflow dataset from {source}...")

        for roboflow_split, our_split in splits.items():
            split_path = os.path.join(source, roboflow_split)
            json_path = os.path.join(split_path, "_annotations.coco.json")
            
            if not os.path.exists(json_path):
                self.stdout.write(f"Skipping {roboflow_split} (no JSON found)")
                continue

            with open(json_path, 'r') as f:
                data = json.load(f)

            # Create mapping of image_id to filename
            images = {img['id']: img['file_name'] for img in data['images']}
            
            # Create output directories
            for label in ["occupied", "vacant"]:
                os.makedirs(os.path.join(output, our_split, label), exist_ok=True)

            self.stdout.write(f"  Extracting crops from {roboflow_split}...")
            
            # Use a local limit for this split to ensure we get data from all splits
            split_limit = limit if roboflow_split == "train" else int(limit * 0.2)
            
            annotations = data['annotations']
            random.shuffle(annotations)

            processed_in_split = 0
            for ann in annotations:
                cat_id = ann['category_id']
                if cat_id not in CATEGORY_MAP:
                    continue
                
                label = CATEGORY_MAP[cat_id]
                
                # Check limit for this split specifically
                if processed_in_split >= split_limit * 2: # total for split
                    continue

                img_id = ann['image_id']
                file_name = images.get(img_id)
                if not file_name:
                    continue

                img_path = os.path.join(split_path, file_name)
                if not os.path.exists(img_path):
                    continue

                # Crop
                bbox = ann['bbox'] # [x, y, w, h]
                x, y, w, h = bbox
                
                try:
                    with Image.open(img_path) as img:
                        # PIL crop uses (left, top, right, bottom)
                        crop = img.crop((x, y, x + w, y + h))
                        
                        # Save
                        dst_name = f"{label}_{counts[label]:06d}.jpg"
                        dst_path = os.path.join(output, our_split, label, dst_name)
                        crop.convert("RGB").save(dst_path, "JPEG")
                        
                        counts[label] += 1
                        processed_in_split += 1
                except Exception as e:
                    self.stderr.write(f"Error processing {file_name}: {e}")

            self.stdout.write(f"    Done {roboflow_split}: created {processed_in_split} crops.")

        self.stdout.write(self.style.SUCCESS(
            f"\nSuccess! Prepared {counts['occupied']} occupied and {counts['vacant']} vacant images.\n"
            f"Dataset location: {output}/\n"
            f"Next step: python manage.py train_model"
        ))
