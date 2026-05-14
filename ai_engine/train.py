"""
ai_engine/train.py — Training script for the parking slot CNN.

Dataset: PKLot (recommended) or CNRPark.
  PKLot download: https://web.inf.ufpr.br/vri/databases/parking-lot-database/
  Expected folder structure after download:
    dataset/
      train/
        occupied/   ← images of occupied slots
        vacant/     ← images of vacant slots
      val/
        occupied/
        vacant/

Run:
  python ai_engine/train.py --data_dir dataset/ --epochs 20 --output ai_engine/checkpoints/

Training strategy:
  Phase 1 (epochs 1-10): Backbone frozen — only train the head (fast)
  Phase 2 (epochs 11-20): Unfreeze last 3 backbone blocks — fine-tune (careful)
"""

import os
import argparse
import time
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from PIL import Image
from .model import build_model, save_model


class ParkingDataset(Dataset):
    """
    Loads parking slot images from a directory structure:
      root/occupied/*.jpg
      root/vacant/*.jpg
    """

    LABEL_MAP = {"occupied": 1, "vacant": 0}

    def __init__(self, root_dir, transform=None):
        self.samples = []
        self.transform = transform

        for label_name, label_idx in self.LABEL_MAP.items():
            folder = os.path.join(root_dir, label_name)
            if not os.path.isdir(folder):
                continue
            for fname in os.listdir(folder):
                if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    self.samples.append((os.path.join(folder, fname), label_idx))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, torch.tensor(label, dtype=torch.float32)


def get_transforms(split="train"):
    if split == "train":
        return transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])
    else:
        return transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])


def train_one_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss, correct, total = 0.0, 0, 0
    for imgs, labels in loader:
        imgs, labels = imgs.to(device), labels.to(device).unsqueeze(1)
        optimizer.zero_grad()
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * imgs.size(0)
        preds = (torch.sigmoid(outputs) >= 0.5).long()
        correct += (preds == labels.long()).sum().item()
        total += imgs.size(0)
    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    for imgs, labels in loader:
        imgs, labels = imgs.to(device), labels.to(device).unsqueeze(1)
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        total_loss += loss.item() * imgs.size(0)
        preds = (torch.sigmoid(outputs) >= 0.5).long()
        correct += (preds == labels.long()).sum().item()
        total += imgs.size(0)
    return total_loss / total, correct / total


def train(data_dir, epochs=20, batch_size=32, lr=1e-3, output_dir="ai_engine/checkpoints/"):
    os.makedirs(output_dir, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on: {device}")

    # Datasets
    train_ds = ParkingDataset(os.path.join(data_dir, "train"), get_transforms("train"))
    val_ds = ParkingDataset(os.path.join(data_dir, "val"), get_transforms("val"))
    print(f"Train: {len(train_ds)} | Val: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=2)

    model = build_model(pretrained=True).to(device)
    criterion = nn.BCEWithLogitsLoss()

    # Phase 1: Train head only
    optimizer = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()), lr=lr
    )
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.5)

    best_val_acc = 0.0
    phase1_epochs = min(epochs // 2, 10)

    for epoch in range(1, epochs + 1):
        # Switch to fine-tuning at halfway point
        if epoch == phase1_epochs + 1:
            print("\n── Fine-tuning backbone (last 3 blocks) ──")
            model.unfreeze_backbone(layers_from=-3)
            optimizer = torch.optim.Adam(
                filter(lambda p: p.requires_grad, model.parameters()), lr=lr / 10
            )
            scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.5)

        t0 = time.time()
        train_loss, train_acc = train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        print(
            f"Epoch {epoch:02d}/{epochs} | "
            f"Train loss={train_loss:.4f} acc={train_acc:.3f} | "
            f"Val loss={val_loss:.4f} acc={val_acc:.3f} | "
            f"Time={time.time()-t0:.1f}s"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            save_model(model, os.path.join(output_dir, "best_model.pth"), epoch, val_acc)
            print(f"  ✓ Best model saved (val_acc={val_acc:.4f})")

    save_model(model, os.path.join(output_dir, "final_model.pth"), epochs, val_acc)
    print(f"\nTraining complete. Best val accuracy: {best_val_acc:.4f}")
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", default="dataset/")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--output", default="ai_engine/checkpoints/")
    args = parser.parse_args()
    train(args.data_dir, args.epochs, args.batch_size, args.lr, args.output)
