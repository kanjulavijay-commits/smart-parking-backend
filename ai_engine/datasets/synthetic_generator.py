"""
ai_engine/datasets/synthetic_generator.py

Generates realistic synthetic parking slot images using PIL.
No external download required — runs completely offline.

Each image (64x64 px) shows a parking slot from a camera's perspective:
  - "occupied" : a car-shaped rectangle with realistic color and shadows
  - "vacant"   : empty asphalt with parking line markings

Variation applied to each image:
  - Random asphalt color (day/night/dusk lighting)
  - Random car color for occupied slots
  - Random noise and brightness jitter
  - Random camera angle (slight rotation/perspective)
  - Weather simulation: rain streaks, fog overlay, glare
"""

import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance


# ─── Constants ───────────────────────────────────────────────────────────────
IMG_SIZE    = 64
ASPHALT_COLORS = [
    (60, 60, 65), (70, 70, 75), (50, 52, 58),   # dark wet asphalt
    (100, 98, 95), (90, 88, 85), (80, 80, 80),  # dry asphalt
    (40, 42, 48), (55, 55, 60),                  # night
]
CAR_COLORS = [
    (200, 200, 200), (230, 230, 230),  # silver/white
    (30, 30, 30),   (50, 50, 50),      # black/dark gray
    (180, 0, 0),    (150, 20, 20),     # red
    (0, 60, 150),   (20, 80, 180),     # blue
    (220, 180, 0),  (200, 160, 20),    # yellow/gold
    (0, 120, 50),   (20, 100, 40),     # green
    (150, 80, 20),                      # brown
]
LINE_COLORS = [
    (255, 255, 255), (220, 220, 220),  # white lines (faded or fresh)
    (240, 200, 0),   (220, 180, 0),    # yellow lines
]
WEATHER_MODES = ["clear", "clear", "clear", "rain", "fog", "glare"]  # clear is more common


# ─── Core image generators ────────────────────────────────────────────────────

def _make_base(size=IMG_SIZE):
    """Generate asphalt background with random texture."""
    color = random.choice(ASPHALT_COLORS)
    img = Image.new("RGB", (size, size), color)
    # Add subtle noise texture (simulates asphalt grain)
    arr = np.array(img, dtype=np.int16)
    noise = np.random.randint(-12, 12, arr.shape, dtype=np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _draw_slot_lines(img):
    """Draw parking bay lines on the asphalt."""
    draw = ImageDraw.Draw(img)
    line_color = random.choice(LINE_COLORS)
    lw = random.randint(1, 2)
    # Left and right vertical lines
    x1 = random.randint(3, 7)
    x2 = random.randint(57, 61)
    draw.line([(x1, 0), (x1, IMG_SIZE)], fill=line_color, width=lw)
    draw.line([(x2, 0), (x2, IMG_SIZE)], fill=line_color, width=lw)
    return img


def _draw_car(img):
    """Draw a car-shaped rectangle with roof, windows, and shadow."""
    draw = ImageDraw.Draw(img)
    car_color = random.choice(CAR_COLORS)

    # Car body — takes up most of the slot
    margin_x = random.randint(8, 14)
    margin_y = random.randint(6, 12)
    x1, y1 = margin_x, margin_y
    x2, y2 = IMG_SIZE - margin_x, IMG_SIZE - margin_y

    # Shadow under car
    shadow_offset = random.randint(2, 4)
    shadow_color = (
        max(0, ASPHALT_COLORS[0][0] - 15),
        max(0, ASPHALT_COLORS[0][1] - 15),
        max(0, ASPHALT_COLORS[0][2] - 15),
    )
    draw.rectangle([x1 + shadow_offset, y1 + shadow_offset,
                    x2 + shadow_offset, y2 + shadow_offset], fill=shadow_color)

    # Car body
    draw.rectangle([x1, y1, x2, y2], fill=car_color)

    # Windscreen highlight (lighter rectangle on top portion)
    highlight = tuple(min(255, c + 60) for c in car_color)
    wy1 = y1 + (y2 - y1) // 5
    wy2 = y1 + (y2 - y1) // 2
    draw.rectangle([x1 + 4, wy1, x2 - 4, wy2], fill=highlight)

    # Roof (slightly darker center rectangle)
    roof_color = tuple(max(0, c - 30) for c in car_color)
    draw.rectangle([x1 + 4, wy2, x2 - 4, y2 - 6], fill=roof_color)

    return img


def _apply_weather(img, mode):
    """Apply weather effects: rain streaks, fog, or glare."""
    if mode == "rain":
        arr = np.array(img)
        # Rain streaks: random dark diagonal lines
        for _ in range(random.randint(5, 15)):
            x = random.randint(0, IMG_SIZE)
            y = random.randint(0, IMG_SIZE - 10)
            length = random.randint(5, 12)
            # Darken a thin diagonal line
            for i in range(length):
                px = min(IMG_SIZE - 1, x + i // 3)
                py = min(IMG_SIZE - 1, y + i)
                arr[py, px] = np.clip(arr[py, px].astype(int) - 40, 0, 255)
        img = Image.fromarray(arr.astype(np.uint8))
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    elif mode == "fog":
        fog = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (200, 200, 200))
        img = Image.blend(img, fog, alpha=random.uniform(0.2, 0.45))
        img = img.filter(ImageFilter.GaussianBlur(radius=1.0))

    elif mode == "glare":
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(random.uniform(1.3, 1.8))
        # Add bright spot
        draw = ImageDraw.Draw(img)
        gx = random.randint(0, IMG_SIZE)
        gy = random.randint(0, IMG_SIZE // 2)
        draw.ellipse([gx - 8, gy - 8, gx + 8, gy + 8], fill=(255, 255, 220))

    return img


def _apply_jitter(img):
    """Random brightness, contrast, and slight blur."""
    # Brightness jitter
    factor = random.uniform(0.7, 1.3)
    img = ImageEnhance.Brightness(img).enhance(factor)
    # Contrast jitter
    factor = random.uniform(0.8, 1.2)
    img = ImageEnhance.Contrast(img).enhance(factor)
    # Occasional slight blur (camera focus)
    if random.random() < 0.15:
        img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    return img


def _apply_rotation(img):
    """Slight random rotation (camera not perfectly aligned)."""
    angle = random.uniform(-8, 8)
    return img.rotate(angle, fillcolor=random.choice(ASPHALT_COLORS))


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_occupied_image():
    """Generate one occupied parking slot image."""
    weather = random.choice(WEATHER_MODES)
    img = _make_base()
    img = _draw_slot_lines(img)
    img = _draw_car(img)
    img = _apply_weather(img, weather)
    img = _apply_jitter(img)
    img = _apply_rotation(img)
    return img


def generate_vacant_image():
    """Generate one vacant parking slot image."""
    weather = random.choice(WEATHER_MODES)
    img = _make_base()
    img = _draw_slot_lines(img)
    img = _apply_weather(img, weather)
    img = _apply_jitter(img)
    img = _apply_rotation(img)
    return img


def generate_dataset(output_dir, n_occupied=3000, n_vacant=3000, val_split=0.2):
    """
    Generate a full synthetic dataset.

    Args:
        output_dir: root folder (e.g. "ai_engine/data/synthetic")
        n_occupied: number of occupied images to generate
        n_vacant:   number of vacant images to generate
        val_split:  fraction for validation (0.2 = 80/20 split)

    Returns:
        dict with counts
    """
    splits = {
        "train": {"occupied": int(n_occupied * (1 - val_split)),
                  "vacant":   int(n_vacant   * (1 - val_split))},
        "val":   {"occupied": n_occupied - int(n_occupied * (1 - val_split)),
                  "vacant":   n_vacant   - int(n_vacant   * (1 - val_split))},
    }

    total = 0
    for split, labels in splits.items():
        for label, count in labels.items():
            folder = os.path.join(output_dir, split, label)
            os.makedirs(folder, exist_ok=True)
            generator = generate_occupied_image if label == "occupied" else generate_vacant_image
            for i in range(count):
                img = generator()
                img.save(os.path.join(folder, f"{label}_{i:05d}.png"))
            total += count

    return {
        "train_occupied": splits["train"]["occupied"],
        "train_vacant":   splits["train"]["vacant"],
        "val_occupied":   splits["val"]["occupied"],
        "val_vacant":     splits["val"]["vacant"],
        "total":          total,
        "output_dir":     output_dir,
    }
