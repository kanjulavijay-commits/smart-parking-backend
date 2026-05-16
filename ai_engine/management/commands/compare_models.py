"""
Management command: python manage.py compare_models --data data_library/combined_master/val

Compares CNN, SVM, and Random Forest on the same validation set.
"""

import os
import time
import torch
import joblib
import numpy as np
from PIL import Image
from torchvision import transforms
from sklearn.metrics import accuracy_score, f1_score
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Compare all 3 AI models side-by-side."

    def handle(self, *args, **options):
        val_path = "data_library/combined_master/val"
        if not os.path.exists(val_path):
            self.stderr.write("Validation data not found. Prepare the dataset first.")
            return

        self.stdout.write("\n" + "="*50)
        self.stdout.write("   *** THE BATTLE OF THE MODELS: AI COMPARISON ***")
        self.stdout.write("="*50 + "\n")

        # 1. Load Data
        self.stdout.write("Loading test images...")
        images, labels = self._load_images(val_path)
        self.stdout.write(f"Total test images: {len(images)}\n")

        # 2. Evaluate CNN (Model 1)
        self.stdout.write("Testing Model 1: CNN (MobileNetV2)...")
        cnn_acc, cnn_f1, cnn_time = self._test_cnn(images, labels)
        
        # 3. Evaluate SVM (Model 2)
        self.stdout.write("Testing Model 2: SVM (Classic ML)...")
        svm_acc, svm_f1, svm_time = self._test_svm(images, labels)

        # 4. Evaluate Random Forest (Model 3)
        self.stdout.write("Testing Model 3: Random Forest (Ensemble)...")
        rf_acc, rf_f1, rf_time = self._test_rf(images, labels)

        # 5. FINAL TABLE
        self.stdout.write("\n" + "-"*65)
        self.stdout.write(f"{'MODEL':<20} | {'ACCURACY':<10} | {'F1-SCORE':<10} | {'TIME (s)':<10}")
        self.stdout.write("-"*65)
        self.stdout.write(f"{'1. CNN':<20} | {cnn_acc:>9.1%} | {cnn_f1:>9.3f} | {cnn_time:>9.2f}")
        self.stdout.write(f"{'2. SVM':<20} | {svm_acc:>9.1%} | {svm_f1:>9.3f} | {svm_time:>9.2f}")
        self.stdout.write(f"{'3. Random Forest':<20} | {rf_acc:>9.1%} | {rf_f1:>9.3f} | {rf_time:>9.2f}")
        self.stdout.write("-"*65 + "\n")

        # WINNER
        winner = "CNN" if cnn_f1 > svm_f1 and cnn_f1 > rf_f1 else ("SVM" if svm_f1 > rf_f1 else "Random Forest")
        self.stdout.write(self.style.SUCCESS(f"--- THE WINNER IS: {winner}! ---\n"))

    def _load_images(self, path):
        imgs, labels = [], []
        # Match the CNN's LABEL_MAP: occupied=1, vacant=0
        label_map = {"occupied": 1, "vacant": 0}
        for label_name, label_idx in label_map.items():
            folder = os.path.join(path, label_name)
            if not os.path.exists(folder): continue
            for fname in os.listdir(folder):
                if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                    imgs.append(os.path.join(folder, fname))
                    labels.append(label_idx)
        return imgs, np.array(labels)

    def _test_cnn(self, img_paths, labels):
        from ai_engine.model import build_model
        device = torch.device("cpu")
        model = build_model().to(device)
        checkpoint = torch.load("ai_engine/checkpoints/best_model.pth", map_location=device)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()

        preprocess = transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        preds = []
        t0 = time.time()
        with torch.no_grad():
            for p in img_paths:
                img = Image.open(p).convert("RGB")
                tensor = preprocess(img).unsqueeze(0).to(device)
                out = model(tensor)
                preds.append(1 if torch.sigmoid(out).item() > 0.5 else 0)
        
        dt = time.time() - t0
        return accuracy_score(labels, preds), f1_score(labels, preds, average='macro'), dt

    def _test_svm(self, img_paths, labels):
        data = joblib.load("ai_engine/checkpoints/svm_model.joblib")
        svm = data["model"]
        scaler = data["scaler"]

        X = []
        t0 = time.time()
        for p in img_paths:
            img = Image.open(p).convert('L').resize((64, 64))
            X.append(np.array(img).flatten())
        
        X_scaled = scaler.transform(X)
        preds = svm.predict(X_scaled)
        dt = time.time() - t0
        return accuracy_score(labels, preds), f1_score(labels, preds, average='macro'), dt

    def _test_rf(self, img_paths, labels):
        rf = joblib.load("ai_engine/checkpoints/rf_model.joblib")
        X = []
        t0 = time.time()
        for p in img_paths:
            img = Image.open(p).convert('L').resize((64, 64))
            X.append(np.array(img).flatten())
        
        preds = rf.predict(X)
        dt = time.time() - t0
        return accuracy_score(labels, preds), f1_score(labels, preds, average='macro'), dt
