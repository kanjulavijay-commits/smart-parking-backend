"""
Management command: python manage.py train_cnn_combined

Trains the CNN (Model 1) on the COMBINED dataset: PKLot + CNRPark + SynthParking.
Automatically uses whichever of the three are available on disk.
SynthParking is always included (generated locally).

Usage:
  python manage.py train_cnn_combined
  python manage.py train_cnn_combined --epochs 20
  python manage.py train_cnn_combined --quick        # 3 epochs sanity check
"""

import os
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Train CNN on combined dataset: PKLot + CNRPark-EXT + SynthParking (Model 1)."

    def add_arguments(self, parser):
        parser.add_argument("--epochs",     type=int,   default=10)
        parser.add_argument("--batch_size", type=int,   default=32)
        parser.add_argument("--lr",         type=float, default=1e-3)
        parser.add_argument("--output",     default="ai_engine/checkpoints")
        parser.add_argument("--quick",      action="store_true",
                            help="3-epoch sanity check")
        parser.add_argument("--datasets",   nargs="+",
                            default=["PKLot", "CNRPark-EXT", "SynthParking"],
                            help="Which datasets to merge")

    def handle(self, *args, **options):
        from ai_engine.datasets.merger import DatasetMerger, MergedParkingDataset
        from ai_engine.train import get_transforms, train_one_epoch, evaluate
        from ai_engine.model import build_model, save_model

        epochs     = 3 if options["quick"] else options["epochs"]
        batch_size = options["batch_size"]
        lr         = options["lr"]
        output_dir = options["output"]
        datasets   = options["datasets"]

        # Check SynthParking is available
        synth_path = os.path.join("ai_engine", "data", "synthetic", "train", "occupied")
        if not os.path.isdir(synth_path):
            self.stderr.write(
                "SynthParking not found. Generate it first:\n"
                "  python manage.py generate_synthetic_dataset"
            )
            return

        self.stdout.write(f"\nMerging datasets: {' + '.join(datasets)}")
        merger = DatasetMerger(dataset_names=datasets)

        if not merger.available_datasets:
            self.stderr.write("No datasets available.")
            return

        self.stdout.write(f"Available: {' + '.join(merger.available_datasets)}\n")

        train_ds = MergedParkingDataset(merger, split="train", transform=get_transforms("train"))
        val_ds   = MergedParkingDataset(merger, split="val",   transform=get_transforms("val"))
        self.stdout.write(f"Train: {len(train_ds):,} | Val: {len(val_ds):,}")

        if len(train_ds) == 0:
            self.stderr.write("No training images found.")
            return

        os.makedirs(output_dir, exist_ok=True)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.stdout.write(f"Device: {device} | Epochs: {epochs}\n")

        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=0)
        val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=0)

        model     = build_model(pretrained=True).to(device)
        criterion = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.Adam(
            filter(lambda p: p.requires_grad, model.parameters()), lr=lr
        )
        scheduler   = torch.optim.lr_scheduler.StepLR(optimizer, step_size=4, gamma=0.5)
        phase2_ep   = max(epochs // 2, 1)
        best_acc    = 0.0
        best_path   = os.path.join(output_dir, "cnn_best.pth")

        self.stdout.write("-- Phase 1: Training classifier head --")
        for epoch in range(1, epochs + 1):
            if epoch == phase2_ep + 1:
                self.stdout.write("-- Phase 2: Fine-tuning backbone --")
                model.unfreeze_backbone(layers_from=-3)
                optimizer = torch.optim.Adam(
                    filter(lambda p: p.requires_grad, model.parameters()), lr=lr / 10
                )
                scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.5)

            t0 = time.time()
            tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, criterion, device)
            vl_loss, vl_acc = evaluate(model, val_loader, criterion, device)
            scheduler.step()

            star = " * best" if vl_acc > best_acc else ""
            self.stdout.write(
                f"  Epoch {epoch:02d}/{epochs} | "
                f"train={tr_acc:.3f} | val={vl_acc:.3f} | {time.time()-t0:.0f}s{star}"
            )

            if vl_acc > best_acc:
                best_acc = vl_acc
                save_model(model, best_path, epoch, vl_acc)

        save_model(model, os.path.join(output_dir, "cnn_final.pth"), epochs, vl_acc)

        self.stdout.write(self.style.SUCCESS(
            f"\nCNN training complete!\n"
            f"  Datasets used : {' + '.join(merger.available_datasets)}\n"
            f"  Best val acc  : {best_acc:.1%}\n"
            f"  Model saved   : {best_path}\n"
        ))
