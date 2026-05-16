"""
Management command: python manage.py train_model

Trains the MobileNetV2 parking slot CNN and saves the model to
ai_engine/checkpoints/best_model.pth

Usage:
  python manage.py train_model                  # default: 10 epochs
  python manage.py train_model --epochs 20      # more epochs = better accuracy
  python manage.py train_model --quick          # 3 epochs, sanity-check only
  python manage.py train_model --data dataset2  # different data folder
"""

import os
import sys
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import transforms
from PIL import Image
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Train the MobileNetV2 parking slot CNN on the prepared dataset."

    def add_arguments(self, parser):
        parser.add_argument("--data", default="dataset", help="Dataset folder (default: dataset/)")
        parser.add_argument("--epochs", type=int, default=10, help="Training epochs (default: 10)")
        parser.add_argument("--batch_size", type=int, default=32, help="Batch size (default: 32)")
        parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate (default: 0.001)")
        parser.add_argument("--output", default="ai_engine/checkpoints", help="Where to save model")
        parser.add_argument("--quick", action="store_true", help="Quick 3-epoch sanity check")

    def handle(self, *args, **options):
        data_dir = options["data"]
        epochs = 3 if options["quick"] else options["epochs"]
        batch_size = options["batch_size"]
        lr = options["lr"]
        output_dir = options["output"]

        # Validate dataset exists
        for split in ("train", "val"):
            for label in ("occupied", "vacant"):
                folder = os.path.join(data_dir, split, label)
                if not os.path.isdir(folder):
                    self.stderr.write(
                        f"Missing folder: {folder}\n"
                        "Run: python manage.py prepare_dataset --source <PKLot folder>"
                    )
                    return

        os.makedirs(output_dir, exist_ok=True)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.stdout.write(f"Device: {device} | Epochs: {epochs} | Batch: {batch_size}")

        # Build datasets
        from ai_engine.train import ParkingDataset, get_transforms, train_one_epoch, evaluate
        train_ds = ParkingDataset(os.path.join(data_dir, "train"), get_transforms("train"))
        val_ds   = ParkingDataset(os.path.join(data_dir, "val"),   get_transforms("val"))

        if len(train_ds) == 0:
            self.stderr.write("No training images found. Check your dataset folder.")
            return

        self.stdout.write(f"Train: {len(train_ds)} images | Val: {len(val_ds)} images")

        # Windows requires num_workers=0
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=0)
        val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=0)

        from ai_engine.model import build_model, save_model
        model = build_model(pretrained=True).to(device)
        criterion = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.Adam(
            filter(lambda p: p.requires_grad, model.parameters()), lr=lr
        )
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=4, gamma=0.5)

        phase2_start = max(epochs // 2, 1)
        best_val_acc = 0.0
        best_path = os.path.join(output_dir, "best_model.pth")

        self.stdout.write("\n-- Phase 1: Training classifier head --")
        for epoch in range(1, epochs + 1):
            if epoch == phase2_start + 1:
                self.stdout.write("-- Phase 2: Fine-tuning backbone --")
                model.unfreeze_backbone(layers_from=-3)
                optimizer = torch.optim.Adam(
                    filter(lambda p: p.requires_grad, model.parameters()), lr=lr / 10
                )
                scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.5)

            t0 = time.time()
            train_loss, train_acc = train_one_epoch(model, train_loader, optimizer, criterion, device)
            val_loss,   val_acc   = evaluate(model, val_loader, criterion, device)
            scheduler.step()

            marker = " * best" if val_acc > best_val_acc else ""
            self.stdout.write(
                f"  Epoch {epoch:02d}/{epochs} | "
                f"train acc={train_acc:.3f} loss={train_loss:.4f} | "
                f"val acc={val_acc:.3f} loss={val_loss:.4f} | "
                f"{time.time()-t0:.0f}s{marker}"
            )

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                save_model(model, best_path, epoch, val_acc)

        save_model(model, os.path.join(output_dir, "final_model.pth"), epochs, val_acc)

        self.stdout.write(self.style.SUCCESS(
            f"\nTraining complete!\n"
            f"Best validation accuracy: {best_val_acc:.1%}\n"
            f"Model saved to: {best_path}\n\n"
            f"The AI system is now active. It will classify parking slot images\n"
            f"as occupied or vacant with ~{best_val_acc:.0%} accuracy."
        ))
