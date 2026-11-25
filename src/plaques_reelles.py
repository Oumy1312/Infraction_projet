"""Lecture des plaques réelles déjà découpées. Aucune lecture du texte."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).resolve().parents[1]
PLATES = PROJECT / "data" / "processed" / "plates_detection"


def source_de(name: str) -> str:
    """Famille de fichier. Ce n'est pas un type de véhicule ni un format."""
    low = name.lower()
    if "moped" in low:
        return "moped"
    if low.startswith("marokko"):
        return "marokko"
    if "maroc" in low or low.startswith("ma-") or low.startswith("ma_"):
        return "maroc"
    if low.startswith("img"):
        return "IMG"
    if low.startswith("photo"):
        return "PHOTO"
    if low.startswith("vid"):
        return "VID"
    if low.startswith("y ("):
        return "y"
    if len(low) >= 2 and low[0] == "t" and low[1].isdigit():
        return "serie_T"
    if "download" in low or low.startswith("downlo"):
        return "telechargement"
    if "ecole" in low:
        return "auto-ecole"
    if low.startswith("unnamed"):
        return "unnamed"
    stem = name.split("_jpg")[0].split("_jpeg")[0].split("_png")[0]
    digits = stem.split("-")[0]
    if digits.isdigit():
        return "id_numerique"
    return "autre"


def lister() -> list[dict]:
    rows = []
    for split in ("train", "val", "test"):
        images = PLATES / split / "images"
        labels = PLATES / split / "labels"
        if not images.is_dir():
            continue
        for image in images.iterdir():
            if image.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            label = labels / f"{image.stem}.txt"
            if not label.is_file():
                continue
            rows.append(
                {
                    "image": image,
                    "label": label,
                    "split": split,
                    "source": source_de(image.name),
                    "nom": image.name,
                }
            )
    return rows


def plus_grande_boite(label: Path, width: int, height: int) -> tuple[int, int, int, int] | None:
    best = None
    best_area = 0
    for line in label.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            cx, cy, bw, bh = (float(part) for part in parts[1:])
        except ValueError:
            continue
        x1 = int(round((cx - bw / 2) * width))
        y1 = int(round((cy - bh / 2) * height))
        x2 = int(round((cx + bw / 2) * width))
        y2 = int(round((cy + bh / 2) * height))
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
        area = max(0, x2 - x1) * max(0, y2 - y1)
        if area > best_area:
            best_area = area
            best = (x1, y1, x2, y2)
    return best


def recadrer(item: dict) -> np.ndarray | None:
    image = cv2.imread(str(item["image"]))
    if image is None:
        return None
    height, width = image.shape[:2]
    box = plus_grande_boite(item["label"], width, height)
    if box is None:
        return None
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        return None
    return image[y1:y2, x1:x2].copy()


def nettete(crop: np.ndarray) -> float:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def ecrire_planche(cases: list[dict], destination: Path, titre: str, columns: int = 5, font_path: str | None = None) -> None:
    thumb_w, thumb_h = 220, 78
    caption_h = 36
    pad = 8
    rows = max(1, (len(cases) + columns - 1) // columns)
    sheet = Image.new("RGB", (pad + columns * (thumb_w + pad), 34 + rows * (thumb_h + caption_h + pad)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    chosen = font_path or r"C:\Windows\Fonts\arial.ttf"
    try:
        font = ImageFont.truetype(chosen, 13)
        small = ImageFont.truetype(chosen, 12)
    except OSError:
        font = ImageFont.load_default()
        small = font
    draw.text((pad, 8), titre, fill=(240, 240, 240), font=font)
    for index, case in enumerate(cases):
        column = index % columns
        row = index // columns
        origin_x = pad + column * (thumb_w + pad)
        origin_y = 32 + row * (thumb_h + caption_h + pad)
        canvas = Image.new("RGB", (thumb_w, thumb_h), (32, 32, 32))
        crop = case.get("crop")
        if crop is not None and getattr(crop, "size", 0):
            picture = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            picture.thumbnail((thumb_w - 4, thumb_h - 4))
            canvas.paste(picture, ((thumb_w - picture.width) // 2, (thumb_h - picture.height) // 2))
        sheet.paste(canvas, (origin_x, origin_y))
        draw.text((origin_x, origin_y + thumb_h + 1), str(case.get("caption", ""))[:40], fill=(230, 230, 210), font=small)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)
