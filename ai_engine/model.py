"""
ai_engine/model.py — CNN architecture for parking slot occupancy detection.

Architecture: MobileNetV2 backbone (pretrained on ImageNet) + custom classifier head.

Why MobileNetV2?
  - Lightweight: 3.4MB vs ResNet50's 100MB
  - Fast inference: runs on a Raspberry Pi at the parking gate
  - Strong accuracy: 95%+ on PKLot with fine-tuning
  - Pretrained features transfer well to parking imagery

Binary output:
  0 = Vacant (slot is free)
  1 = Occupied (vehicle present)
"""

import torch
import torch.nn as nn
from torchvision import models


class ParkingSlotCNN(nn.Module):
    """
    MobileNetV2 fine-tuned for parking slot occupancy classification.
    The backbone's convolutional layers are frozen; only the classifier is trained.
    For fine-tuning, unfreeze with model.unfreeze_backbone().
    """

    def __init__(self, pretrained=True):
        super().__init__()

        # Load MobileNetV2 backbone
        weights = models.MobileNet_V2_Weights.DEFAULT if pretrained else None
        backbone = models.mobilenet_v2(weights=weights)

        # Keep all conv layers, replace the classifier
        self.features = backbone.features

        # Freeze backbone weights — only train the head initially
        for param in self.features.parameters():
            param.requires_grad = False

        # Custom classification head
        # MobileNetV2 outputs 1280 channels after global avg pool
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),   # global average pooling → (batch, 1280, 1, 1)
            nn.Flatten(),              # → (batch, 1280)
            nn.Dropout(p=0.3),
            nn.Linear(1280, 256),
            nn.ReLU(),
            nn.Dropout(p=0.2),
            nn.Linear(256, 1),         # binary: occupied or vacant
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x  # raw logit — apply sigmoid for probability

    def unfreeze_backbone(self, layers_from=-3):
        """Unfreeze the last N feature blocks for fine-tuning."""
        for i, child in enumerate(self.features.children()):
            if i >= len(list(self.features.children())) + layers_from:
                for param in child.parameters():
                    param.requires_grad = True

    def predict_proba(self, x):
        """Return occupancy probability (0.0 = vacant, 1.0 = occupied)."""
        with torch.no_grad():
            logits = self.forward(x)
            return torch.sigmoid(logits)

    def predict(self, x, threshold=0.5):
        """Return binary prediction: 0 = vacant, 1 = occupied."""
        proba = self.predict_proba(x)
        return (proba >= threshold).long()


def build_model(pretrained=True):
    """Create a fresh ParkingSlotCNN model."""
    return ParkingSlotCNN(pretrained=pretrained)


def load_model(checkpoint_path, device="cpu"):
    """Load a trained model from a .pth checkpoint file."""
    model = ParkingSlotCNN(pretrained=False)
    state = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state["model_state_dict"])
    model.eval()
    return model


def save_model(model, path, epoch=None, val_acc=None):
    """Save model checkpoint with metadata."""
    torch.save({
        "model_state_dict": model.state_dict(),
        "epoch": epoch,
        "val_accuracy": val_acc,
        "architecture": "MobileNetV2-ParkingSlotCNN",
    }, path)
    return path
