#!/usr/bin/env python3
"""Petite CNN de l'état du feu, de zéro, sur CPU.

Classes : rouge, orange, vert, autre. Entraînement sur les 70 % d'ajustement,
mêmes groupes pHash que l'évaluation HSV pour les images déjà réparties.
Évaluation une fois sur les 30 %. La perte est pondérée : l'orange est rare.
Limite 15 minutes.

    python scripts/07_cnn_feu.py
"""

from __future__ import annotations

import importlib.util
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.feu import _mask, load_config

SPEC = importlib.util.spec_from_file_location("eval_hsv", PROJECT / "scripts" / "06_eval_hsv.py")
hsv = importlib.util.module_from_spec(SPEC)
sys.modules["eval_hsv"] = hsv
SPEC.loader.exec_module(hsv)

COLOR_ROOT = PROJECT / "data" / "interim" / "feux_couleur"
REPORTS = PROJECT / "reports"
MODEL_PATH = PROJECT / "data" / "models" / "feu_cnn.pt"
NAMES = ("rouge", "orange", "vert", "autre")
INDEX = {name: index for index, name in enumerate(NAMES)}
TRUE_OF = {6: "rouge", 12: "orange", 3: "vert"}
SIZE = 48
EPOCHS = 8
BATCH = 128
LIMIT_S = 15 * 60
SEED = 42


class PetitFeu(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.couches = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.sortie = nn.Linear(64, len(NAMES))

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return self.sortie(self.couches(batch).flatten(1))


def collect_all() -> list[dict]:
    boxes = []
    labels = [
        path
        for path in COLOR_ROOT.rglob("*.txt")
        if path.name.lower() != "classes.txt" and "labels" in path.parts
    ]
    for label in labels:
        image = hsv.find_image(label)
        if image is None:
            continue
        from PIL import Image

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
            box = hsv.yolo_to_pixels(" ".join(parts[1:]), width, height)
            if box is None:
                continue
            x1, y1, x2, y2 = box
            area = max(0, x2 - x1) * max(0, y2 - y1) / max(1, width * height)
            boxes.append(
                {
                    "image": image,
                    "true": TRUE_OF.get(class_id, "autre"),
                    "box": box,
                    "area": area,
                    "width": width,
                    "height": height,
                }
            )
    return boxes


def assign_remaining(images: list[Path], known: dict[Path, str]) -> None:
    fresh = [path for path in images if path not in known]
    if not fresh:
        return
    extra, _sizes = hsv.assign_images(fresh)
    known.update(extra)


def crop_tensor(item: dict) -> np.ndarray | None:
    crop = hsv.crop_bgr(item)
    if crop is None or crop.size == 0:
        return None
    resized = cv2.resize(crop, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    return np.transpose(rgb.astype(np.float32) / 255.0, (2, 0, 1))


def hsv_color(crop_bgr: np.ndarray | None, config: dict) -> str:
    if crop_bgr is None or crop_bgr.size == 0:
        return "inconnu"
    image = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    total = int(image.shape[0] * image.shape[1])
    if total == 0:
        return "inconnu"
    scores = {name: int(_mask(image, config[name]).sum()) for name in ("rouge", "orange", "vert")}
    best = max(scores, key=scores.get)
    if scores[best] / total < float(config["min_ratio"]):
        return "inconnu"
    return best


def batches(rows: list[dict], augment: bool, generator: torch.Generator):
    order = torch.randperm(len(rows), generator=generator).tolist()
    for start in range(0, len(order), BATCH):
        chosen = [rows[index] for index in order[start : start + BATCH]]
        images = np.stack([row["tensor"] for row in chosen])
        if augment:
            flip = torch.rand(len(chosen), generator=generator).numpy() > 0.5
            images[flip] = np.flip(images[flip], axis=3).copy()
        yield (
            torch.from_numpy(np.ascontiguousarray(images)),
            torch.tensor([INDEX[row["true"]] for row in chosen], dtype=torch.long),
        )


def predict_all(model: nn.Module, rows: list[dict]) -> list[str]:
    model.eval()
    found = []
    with torch.no_grad():
        for start in range(0, len(rows), BATCH):
            chunk = rows[start : start + BATCH]
            batch = torch.from_numpy(np.stack([row["tensor"] for row in chunk]))
            classes = model(batch).argmax(dim=1).tolist()
            found.extend(NAMES[index] for index in classes)
    return found


def matrix(rows: list[dict], key: str, labels: tuple[str, ...]) -> dict[str, Counter]:
    table = {true: Counter() for true in labels}
    for row in rows:
        if row["true"] in table:
            table[row["true"]][row[key]] += 1
    return table


def accuracy(rows: list[dict], key: str) -> tuple[float, int, int]:
    if not rows:
        return 0.0, 0, 0
    hits = sum(row["true"] == row[key] for row in rows)
    return hits / len(rows), hits, len(rows)


def write_table(table: dict[str, Counter], labels: tuple[str, ...], columns: tuple[str, ...]) -> list[str]:
    lines = ["| Vrai \\ prédit | " + " | ".join(columns) + " |", "| --- | " + " | ".join("---" for _ in columns) + " |"]
    for true in labels:
        lines.append("| " + true + " | " + " | ".join(str(table[true][pred]) for pred in columns) + " |")
    return lines


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    started = time.monotonic()
    torch.manual_seed(SEED)
    boxes = collect_all()
    color_images = sorted({item["image"] for item in boxes if item["true"] != "autre"}, key=str)
    assignment, _sizes = hsv.assign_images(color_images)
    all_images = sorted({item["image"] for item in boxes}, key=str)
    assign_remaining(all_images, assignment)
    usable = []
    for item in boxes:
        tensor = crop_tensor(item)
        if tensor is None:
            continue
        item["tensor"] = tensor
        item["split"] = assignment[item["image"]]
        usable.append(item)
    train = [item for item in usable if item["split"] == "ajustement"]
    evaluation = [item for item in usable if item["split"] == "evaluation"]
    counts = Counter(item["true"] for item in train)
    weights = torch.tensor(
        [sum(counts.values()) / (len(NAMES) * max(1, counts[name])) for name in NAMES],
        dtype=torch.float32,
    )
    model = PetitFeu()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    generator = torch.Generator().manual_seed(SEED)
    epochs_done = 0
    for epoch in range(EPOCHS):
        if time.monotonic() - started > LIMIT_S - 90:
            break
        model.train()
        total_loss = 0.0
        seen = 0
        for inputs, targets in batches(train, augment=True, generator=generator):
            optimizer.zero_grad()
            loss = loss_fn(model(inputs), targets)
            loss.backward()
            optimizer.step()
            total_loss += float(loss) * len(targets)
            seen += len(targets)
        epochs_done += 1
        print(f"époque {epoch + 1} perte {total_loss / max(1, seen):.4f}")
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state": model.state_dict(), "names": NAMES, "size": SIZE}, MODEL_PATH)

    predicted = predict_all(model, evaluation)
    for row, label in zip(evaluation, predicted):
        row["pred"] = label
    colors = [row for row in evaluation if row["true"] in TRUE_OF.values()]
    score, hits, total = accuracy(evaluation, "pred")
    score_color, hits_color, total_color = accuracy(colors, "pred")
    full = matrix(evaluation, "pred", NAMES)
    orange_as_red = full["orange"]["rouge"]

    v1 = load_config(PROJECT / "config.yaml")
    v2 = load_config(PROJECT / "configs" / "hsv_v2.yaml")
    for row in colors:
        crop = hsv.crop_bgr(row)
        row["hsv_v1"] = hsv_color(crop, v1)
        row["hsv_v2"] = hsv_color(crop, v2)
    hsv_v1 = matrix(colors, "hsv_v1", ("rouge", "orange", "vert"))
    hsv_v2 = matrix(colors, "hsv_v2", ("rouge", "orange", "vert"))
    cnn_color = matrix(colors, "pred", ("rouge", "orange", "vert"))
    columns = ("rouge", "orange", "vert", "inconnu", "autre")
    for table in (hsv_v1, hsv_v2, cnn_color):
        for true in table:
            for name in columns:
                table[true].setdefault(name, 0)

    elapsed = time.monotonic() - started
    lines = [
        "# CNN de l'état du feu",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Modèle de zéro, {SIZE}×{SIZE}, CPU, {epochs_done} époques, {elapsed / 60:.1f} min (plafond 15).",
        "- Ajustement 70 % / évaluation 30 %. Les images déjà réparties par `06_eval_hsv.py` gardent leur côté. Graine 42.",
        f"- Pondération de la perte : {', '.join(f'{name} {weights[index]:.2f}' for index, name in enumerate(NAMES))}.",
        f"- Effectifs d'ajustement : {', '.join(f'{name} {counts[name]}' for name in NAMES)}.",
        "",
        "## Évaluation, quatre classes",
        "",
        f"- Précision globale : {score:.1%} ({hits} / {total}).",
        f"- Orange lu comme rouge : {orange_as_red}.",
        "",
        *write_table(full, NAMES, NAMES),
        "",
        "## Couleurs seulement, face au HSV",
        "",
        "Mêmes boîtes rouge, orange et vert de l'évaluation. HSV v1 est `config.yaml`, HSV v2 est `configs/hsv_v2.yaml`.",
        "",
        f"- CNN : {score_color:.1%} ({hits_color} / {total_color}), orange lu comme rouge {cnn_color['orange']['rouge']}.",
        f"- HSV v1 : {accuracy(colors, 'hsv_v1')[0]:.1%}, orange lu comme rouge {hsv_v1['orange']['rouge']}.",
        f"- HSV v2 : {accuracy(colors, 'hsv_v2')[0]:.1%}, orange lu comme rouge {hsv_v2['orange']['rouge']}.",
        "",
        "### CNN",
        "",
        *write_table(cnn_color, ("rouge", "orange", "vert"), columns),
        "",
        "### HSV v1",
        "",
        *write_table(hsv_v1, ("rouge", "orange", "vert"), columns),
        "",
        "### HSV v2",
        "",
        *write_table(hsv_v2, ("rouge", "orange", "vert"), columns),
        "",
        f"Poids : `{MODEL_PATH.relative_to(PROJECT).as_posix()}`.",
        "",
    ]
    report = REPORTS / "cnn_feu.md"
    report.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(report)
    print(f"cnn {score:.1%} couleurs {score_color:.1%} orange->rouge {orange_as_red}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
