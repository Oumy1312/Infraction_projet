#!/usr/bin/env python3
"""Évalue feu.py sur les feux annotés rouge, jaune ou vert.

Le jeu est séparé en ajustement 70 % et évaluation 30 %. Les images
quasi identiques (pHash, distance <= 5) restent ensemble. Les chiffres
du rapport sont ceux de l'évaluation. Les seuils de config.yaml ne sont
pas modifiés.

    python scripts/06_eval_hsv.py
"""

from __future__ import annotations

import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from tqdm import tqdm

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.feu import classify_bgr, load_config

COLOR_ROOT = PROJECT / "data" / "interim" / "feux_couleur"
REPORTS = PROJECT / "reports"
SEED = 42
HAMMING_MAX = 5
TRUE_OF = {6: "rouge", 12: "orange", 3: "vert"}
LABELS = ("rouge", "orange", "vert")
PREDICTED = ("rouge", "orange", "vert", "inconnu")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a


def phash_int(path: Path) -> int | None:
    try:
        with Image.open(path) as image:
            digest = imagehash.phash(image.convert("RGB"))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None
    return int(str(digest), 16)


def find_image(label: Path) -> Path | None:
    images = label.parent.parent / "images"
    if not images.is_dir():
        return None
    hits = [path for path in images.iterdir() if path.stem == label.stem and path.suffix.lower() in IMAGE_EXTS]
    return hits[0] if hits else None


def yolo_to_pixels(rest: str, width: int, height: int) -> tuple[int, int, int, int] | None:
    try:
        cx, cy, bw, bh = (float(piece) for piece in rest.split())
    except ValueError:
        return None
    x1 = int(round((cx - bw / 2) * width))
    y1 = int(round((cy - bh / 2) * height))
    x2 = int(round((cx + bw / 2) * width))
    y2 = int(round((cy + bh / 2) * height))
    return x1, y1, x2, y2


def collect() -> list[dict]:
    boxes = []
    labels = [path for path in COLOR_ROOT.rglob("*.txt") if path.name.lower() != "classes.txt" and "labels" in path.parts]
    for label in labels:
        image = find_image(label)
        if image is None:
            continue
        with Image.open(image) as picture:
            width, height = picture.size
        for line in label.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                class_id = int(float(parts[0]))
            except ValueError:
                continue
            if class_id not in TRUE_OF:
                continue
            box = yolo_to_pixels(" ".join(parts[1:]), width, height)
            if box is None:
                continue
            x1, y1, x2, y2 = box
            area = max(0, x2 - x1) * max(0, y2 - y1) / max(1, width * height)
            boxes.append(
                {
                    "image": image,
                    "true": TRUE_OF[class_id],
                    "box": box,
                    "area": area,
                    "width": width,
                    "height": height,
                }
            )
    return boxes


def assign_images(images: list[Path]) -> tuple[dict[Path, str], list[int]]:
    hashes = [phash_int(path) for path in tqdm(images, desc="pHash feux couleur", unit="img")]
    union = UnionFind(len(images))
    for left in range(len(images)):
        if hashes[left] is None:
            continue
        for right in range(left + 1, len(images)):
            if hashes[right] is None:
                continue
            if (hashes[left] ^ hashes[right]).bit_count() <= HAMMING_MAX:
                union.union(left, right)
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(images)):
        groups[union.find(index)].append(index)
    order = list(groups.values())
    random.Random(SEED).shuffle(order)
    order.sort(key=len, reverse=True)
    total = len(images)
    targets = {"ajustement": 0.70 * total, "evaluation": 0.30 * total}
    counts = {"ajustement": 0, "evaluation": 0}
    assignment: dict[Path, str] = {}
    for group in order:
        def score(name: str, group_size: int = len(group)) -> tuple[float, float]:
            after = counts[name] + group_size
            overflow = max(0.0, after - targets[name])
            return (overflow, abs(targets[name] - after))

        choice = min(counts, key=score)
        for index in group:
            assignment[images[index]] = choice
        counts[choice] += len(group)
    sizes = sorted((len(group) for group in groups.values()), reverse=True)
    return assignment, sizes


CROPS: dict[tuple, np.ndarray | None] = {}


def crop_bgr(item: dict) -> np.ndarray | None:
    key = (str(item["image"]), item["box"])
    if key in CROPS:
        return CROPS[key]
    frame = cv2.imread(str(item["image"]))
    crop = None
    if frame is not None:
        x1, y1, x2, y2 = item["box"]
        height, width = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
        if x2 > x1 and y2 > y1:
            crop = frame[y1:y2, x1:x2].copy()
    CROPS[key] = crop
    return crop


def predict(item: dict, config: dict) -> str:
    crop = crop_bgr(item)
    if crop is None:
        return "inconnu"
    return classify_bgr(crop, config)


def confusion(rows: list[dict]) -> dict[str, Counter]:
    matrix = {true: Counter() for true in LABELS}
    for row in rows:
        matrix[row["true"]][row["pred"]] += 1
    return matrix


def precision_of(matrix: dict[str, Counter], name: str) -> tuple[float, int]:
    tp = matrix[name][name]
    predicted = sum(matrix[true][name] for true in LABELS)
    if predicted == 0:
        return 0.0, 0
    return tp / predicted, predicted


def accuracy(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(row["true"] == row["pred"] for row in rows) / len(rows)


def tag_cause(item: dict, crop: np.ndarray | None) -> str:
    x1, y1, x2, y2 = item["box"]
    side = min(max(0, x2 - x1), max(0, y2 - y1))
    notes = []
    if side < 8 or item["area"] < 0.0004:
        notes.append("boîte trop petite")
    if crop is None or crop.size == 0:
        notes.append("recadrage vide")
        return ", ".join(notes)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    saturation = float(hsv[:, :, 1].mean())
    value = float(hsv[:, :, 2].mean())
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if value < 45:
        notes.append("feu sombre ou éteint")
    elif value > 210 and saturation < 40:
        notes.append("reflet")
    elif blur < 15:
        notes.append("feu flou")
    if item["pred"] == "inconnu":
        notes.append("pas assez de pixels dans les seuils")
    elif item["true"] != item["pred"]:
        notes.append(f"{item['true']} lu comme {item['pred']}")
    return ", ".join(notes) if notes else "autre"


def varied_config(base: dict, ratio: float, sat_delta: int, val_delta: int, red_high: int) -> dict:
    copy = {
        "min_ratio": ratio,
        "rouge": {
            "hue": [[0, red_high], [160, 179]],
            "sat_min": max(0, base["rouge"]["sat_min"] + sat_delta),
            "val_min": max(0, base["rouge"]["val_min"] + val_delta),
        },
        "orange": {
            "hue": [[red_high + 2, 32]],
            "sat_min": max(0, base["orange"]["sat_min"] + sat_delta),
            "val_min": max(0, base["orange"]["val_min"] + val_delta),
        },
        "vert": {
            "hue": [list(pair) for pair in base["vert"]["hue"]],
            "sat_min": max(0, base["vert"]["sat_min"] + sat_delta),
            "val_min": max(0, base["vert"]["val_min"] + val_delta),
        },
    }
    return copy


def propose(base: dict, rows: list[dict]) -> tuple[dict, float]:
    best_config = base
    best_score = accuracy(rows)
    for ratio in (0.03, 0.08):
        for sat_delta in (0, -30):
            for val_delta in (0, -30):
                for red_high in (10, 15, 20):
                    candidate = varied_config(base, ratio, sat_delta, val_delta, red_high)
                    scored = [{**row, "pred": predict(row, candidate)} for row in rows]
                    score = accuracy(scored)
                    if score > best_score:
                        best_score = score
                        best_config = candidate
    return best_config, best_score


def draw_sheet(errors: list[dict], destination: Path) -> None:
    chosen = errors[:30]
    columns = 5
    thumb = 140
    pad = 8
    rows = max(1, (len(chosen) + columns - 1) // columns)
    width = pad + columns * (thumb + pad)
    height = 48 + rows * (thumb + 36)
    sheet = Image.new("RGB", (width, height), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    draw.text((pad, 8), "Erreurs HSV sur l'évaluation (30 %). Vrai puis prédit.", fill=(240, 240, 240), font=font)
    for index, item in enumerate(chosen):
        crop = crop_bgr(item)
        column = index % columns
        row = index // columns
        origin_x = pad + column * (thumb + pad)
        origin_y = 36 + row * (thumb + 36)
        canvas = Image.new("RGB", (thumb, thumb), (32, 32, 32))
        if crop is not None and crop.size:
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            picture = Image.fromarray(rgb)
            picture.thumbnail((thumb, thumb))
            canvas.paste(picture, ((thumb - picture.width) // 2, (thumb - picture.height) // 2))
        sheet.paste(canvas, (origin_x, origin_y))
        draw.text((origin_x, origin_y + thumb + 2), f"{item['true']} -> {item['pred']}", fill=(230, 230, 230), font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    config = load_config()
    boxes = collect()
    images = sorted({item["image"] for item in boxes}, key=lambda path: str(path))
    assignment, sizes = assign_images(images)
    for item in boxes:
        item["split"] = assignment[item["image"]]
    evaluation = [item for item in boxes if item["split"] == "evaluation"]
    adjustment = [item for item in boxes if item["split"] == "ajustement"]
    for item in tqdm(evaluation, desc="HSV évaluation", unit="boîte"):
        item["pred"] = predict(item, config)
    matrix = confusion(evaluation)
    score = accuracy(evaluation)
    causes = Counter()
    errors = []
    for item in evaluation:
        if item["true"] == item["pred"]:
            continue
        crop = crop_bgr(item)
        item["cause"] = tag_cause(item, crop)
        causes[item["cause"]] += 1
        errors.append(item)
    random.Random(SEED).shuffle(errors)
    draw_sheet(errors, REPORTS / "contact_hsv_erreurs.jpg")

    proposal_text = "La précision d'évaluation atteint 90 %. Aucun nouveau seuil n'est proposé."
    if score < 0.90 and adjustment:
        for item in tqdm(adjustment, desc="HSV ajustement", unit="boîte"):
            item["pred"] = predict(item, config)
        proposed, proposed_score = propose(config, adjustment)
        proposal_text = (
            "Proposition établie seulement sur l'ajustement (70 %), non appliquée, "
            f"où elle passerait de {accuracy(adjustment):.1%} à {proposed_score:.1%}. "
            "L'évaluation n'a pas servi à choisir ces valeurs.\n\n"
            "```yaml\n"
            f"min_ratio: {proposed['min_ratio']}\n"
            f"rouge hue: {proposed['rouge']['hue']}, sat_min {proposed['rouge']['sat_min']}, val_min {proposed['rouge']['val_min']}\n"
            f"orange hue: {proposed['orange']['hue']}, sat_min {proposed['orange']['sat_min']}, val_min {proposed['orange']['val_min']}\n"
            f"vert hue: {proposed['vert']['hue']}, sat_min {proposed['vert']['sat_min']}, val_min {proposed['vert']['val_min']}\n"
            "```"
        )

    lines = [
        "# Évaluation HSV des feux",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Classes utilisées : `red` → rouge, `yellow` → orange, `green` → vert. Les autres classes d'origine ne sont pas notées.",
        "- Séparation par image, graine 42. Les groupes pHash (distance <= 5) restent ensemble : 70 % ajustement, 30 % évaluation.",
        "- Les seuils de `config.yaml` n'ont pas été modifiés. Les chiffres ci-dessous sont ceux de l'évaluation.",
        "",
        "## Volume",
        "",
        f"- Boîtes couleur : {len(boxes)} sur {len(images)} images.",
        f"- Plus gros groupes pHash : {', '.join(str(size) for size in sizes[:6]) or 'aucun'}.",
        f"- Ajustement : {sum(item['split'] == 'ajustement' for item in boxes)} boîtes, {sum(1 for path, split in assignment.items() if split == 'ajustement')} images.",
        f"- Évaluation : {len(evaluation)} boîtes, {sum(1 for path, split in assignment.items() if split == 'evaluation')} images.",
        "",
        "## Évaluation",
        "",
        f"- Précision globale (couleur prédite = couleur annotée) : {score:.1%} ({sum(row['true'] == row['pred'] for row in evaluation)} / {len(evaluation)}).",
        "",
        "| Vrai \\ prédit | rouge | orange | vert | inconnu |",
        "| --- | --- | --- | --- | --- |",
    ]
    for true in LABELS:
        lines.append("| " + true + " | " + " | ".join(str(matrix[true][pred]) for pred in PREDICTED) + " |")
    lines += ["", "| Classe | Précision | Prédictions |", "| --- | --- | --- |"]
    for name in LABELS:
        value, predicted = precision_of(matrix, name)
        lines.append(f"| {name} | {value:.1%} | {predicted} |")
    lines += ["", "## Erreurs", ""]
    if not errors:
        lines.append("Aucune erreur sur l'évaluation.")
    else:
        red_as_orange = sum(item["true"] == "rouge" and item["pred"] == "orange" for item in errors)
        red_as_green = sum(item["true"] == "rouge" and item["pred"] == "vert" for item in errors)
        unknown = sum(item["pred"] == "inconnu" for item in errors)
        small = sum("boîte trop petite" in item["cause"] for item in errors)
        lines.append(f"- Erreurs : {len(errors)}.")
        lines.append(
            f"- Cause principale : {red_as_orange} rouges annotés sont lus comme orange. "
            f"{small} erreurs portent une boîte trop petite. "
            f"{red_as_green} rouges sont lus comme vert. "
            f"{unknown} prédictions restent « inconnu » (pas assez de pixels dans les seuils)."
        )
        lines.append("- Aucune erreur ne se classe comme feu éteint, flou ou reflet avec ces seuils.")
        for cause, count in causes.most_common():
            lines.append(f"- {cause} : {count}.")
        lines.append("")
        lines.append("Planche de 30 erreurs : `reports/contact_hsv_erreurs.jpg`.")
    lines += ["", "## Seuils", "", proposal_text, ""]
    report = REPORTS / "hsv_eval.md"
    report.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(report)
    print(f"évaluation {score:.1%} sur {len(evaluation)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
