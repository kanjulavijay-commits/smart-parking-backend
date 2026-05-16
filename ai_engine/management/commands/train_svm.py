"""
Management command: python manage.py train_svm --data data_library/combined_master

Trains a Support Vector Machine (SVM) classifier using HOG features.
Saves the model to ai_engine/checkpoints/svm_model.joblib
"""

import os
import joblib
import numpy as np
from PIL import Image
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Train a Support Vector Machine (SVM) on the prepared dataset."

    def add_arguments(self, parser):
        parser.add_argument("--data", default="data_library/combined_master", help="Dataset folder")
        parser.add_argument("--output", default="ai_engine/checkpoints/svm_model.joblib", help="Output file")

    def handle(self, *args, **options):
        data_dir = options["data"]
        output_file = options["output"]

        self.stdout.write(f"Training SVM on {data_dir}...")

        # 1. Load Data and Extract Simple Features (Flattened Grayscale)
        # For a professional SVM, we'd use HOG, but for a start, resized grayscale works well.
        X_train, y_train = self._load_data(os.path.join(data_dir, "train"))
        X_val, y_val = self._load_data(os.path.join(data_dir, "val"))

        if len(X_train) == 0:
            self.stderr.write("No images found. Prepare the dataset first.")
            return

        # 2. Scaling (Important for SVM)
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)

        # 3. Train SVM
        self.stdout.write("Fitting SVM model (this may take a minute)...")
        svm = SVC(kernel='rbf', probability=True, random_state=42)
        svm.fit(X_train_scaled, y_train)

        # 4. Evaluate
        y_pred = svm.predict(X_val_scaled)
        acc = accuracy_score(y_val, y_pred)
        
        self.stdout.write(self.style.SUCCESS(f"SVM Training Complete! Accuracy: {acc:.1%}"))
        self.stdout.write("\nClassification Report:")
        self.stdout.write(classification_report(y_val, y_pred, target_names=["occupied", "vacant"]))

        # 5. Save Model and Scaler
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        joblib.dump({"model": svm, "scaler": scaler}, output_file)
        self.stdout.write(f"Model saved to {output_file}")

    def _load_data(self, split_path):
        X, y = [], []
        size = (64, 64) # Small size for SVM speed
        
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
                    # Load, convert to grayscale, resize, and flatten
                    img = Image.open(fpath).convert('L').resize(size)
                    X.append(np.array(img).flatten())
                    y.append(label_idx)
                except Exception as e:
                    self.stderr.write(f"Error loading {fname}: {e}")
                    
        return np.array(X), np.array(y)
