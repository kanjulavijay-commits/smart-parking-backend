"""
Management command: python manage.py train_rf --data data_library/combined_master

Trains a Random Forest classifier.
Saves the model to ai_engine/checkpoints/rf_model.joblib
"""

import os
import joblib
import numpy as np
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Train a Random Forest classifier on the prepared dataset."

    def add_arguments(self, parser):
        parser.add_argument("--data", default="data_library/combined_master", help="Dataset folder")
        parser.add_argument("--output", default="ai_engine/checkpoints/rf_model.joblib", help="Output file")
        parser.add_argument("--n_estimators", type=int, default=100, help="Number of trees")

    def handle(self, *args, **options):
        data_dir = options["data"]
        output_file = options["output"]
        n_estimators = options["n_estimators"]

        self.stdout.write(f"Training Random Forest ({n_estimators} trees) on {data_dir}...")

        # 1. Load Data
        X_train, y_train = self._load_data(os.path.join(data_dir, "train"))
        X_val, y_val = self._load_data(os.path.join(data_dir, "val"))

        if len(X_train) == 0:
            self.stderr.write("No images found. Prepare the dataset first.")
            return

        # 2. Train Random Forest
        self.stdout.write("Growing the forest...")
        rf = RandomForestClassifier(n_estimators=n_estimators, random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train)

        # 3. Evaluate
        y_pred = rf.predict(X_val)
        acc = accuracy_score(y_val, y_pred)
        
        self.stdout.write(self.style.SUCCESS(f"Random Forest Training Complete! Accuracy: {acc:.1%}"))
        self.stdout.write("\nClassification Report:")
        self.stdout.write(classification_report(y_val, y_pred, target_names=["occupied", "vacant"]))

        # 4. Save Model
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        joblib.dump(rf, output_file)
        self.stdout.write(f"Model saved to {output_file}")

    def _load_data(self, split_path):
        X, y = [], []
        size = (64, 64)
        
        label_map = {"occupied": 1, "vacant": 0}
        for label_name, label_idx in label_map.items():
            folder = os.path.join(split_path, label_name)
            if not os.path.isdir(folder):
                continue
                
            for fname in os.listdir(folder):
                if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                    continue
                    
                fpath = os.path.join(folder, fname)
                try:
                    img = Image.open(fpath).convert('L').resize(size)
                    X.append(np.array(img).flatten())
                    y.append(label_idx)
                except Exception as e:
                    self.stderr.write(f"Error loading {fname}: {e}")
                    
        return np.array(X), np.array(y)
