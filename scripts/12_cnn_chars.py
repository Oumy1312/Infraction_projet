#!/usr/bin/env python3
"""CNN de caractères, de zéro, sur les segments synthétiques.

Limite par défaut : 20 minutes de CPU. Aucun YOLO.

    python scripts/12_cnn_chars.py
    python scripts/12_cnn_chars.py --minutes 0 --epochs 15
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from torch import nn

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.ocr_plaque import SIZE, WEIGHTS_PATH, PetitCaractere, charger_format, classes_de  # noqa: E402

DATA = PROJECT / "data" / "synthetic" / "plaques"
SEED = 42


def charger_npz(path: Path) -> tuple[np.ndarray, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(f"caractères introuvables : {path}. Lancer scripts/04_synth_plates.py d'abord.")
    blob = np.load(path)
    return blob["images"], blob["labels"]


def lot(images: np.ndarray, labels: np.ndarray, start: int, batch: int, device: torch.device):
    stop = min(start + batch, len(images))
    view = images[start:stop]
    tensor = torch.from_numpy(view.astype(np.float32) / 255.0).unsqueeze(1)
    target = torch.from_numpy(labels[start:stop].astype(np.int64))
    return tensor.to(device), target.to(device)


def exactitude(model: nn.Module, images: np.ndarray, labels: np.ndarray, device: torch.device, limit: int = 4000) -> float:
    if len(images) == 0:
        return 0.0
    model.eval()
    take = min(limit, len(images))
    correct = 0
    with torch.no_grad():
        for start in range(0, take, 256):
            batch, target = lot(images, labels, start, 256, device)
            predicted = model(batch).argmax(dim=1)
            correct += int((predicted == target).sum())
    return correct / take


def entrainer(minutes: float, epochs: int) -> None:
    fmt = charger_format()
    names = classes_de(fmt)
    train_x, train_y = charger_npz(DATA / "chars_train.npz")
    eval_path = DATA / "chars_eval.npz"
    eval_x, eval_y = charger_npz(eval_path) if eval_path.is_file() else (np.zeros((0, SIZE, SIZE), np.uint8), np.zeros((0,), np.int64))
    torch.manual_seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = PetitCaractere(len(names)).to(device)
    counts = np.bincount(train_y, minlength=len(names)).astype(np.float32)
    weights = counts.sum() / np.maximum(counts, 1.0)
    weights = weights / weights.mean()
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(weights, device=device))
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    order = np.arange(len(train_x))
    rng = np.random.default_rng(SEED)
    started = time.monotonic()
    done = 0
    history = []
    for epoch in range(1, epochs + 1):
        if minutes > 0 and time.monotonic() - started > minutes * 60:
            break
        rng.shuffle(order)
        train_x = train_x[order]
        train_y = train_y[order]
        order = np.arange(len(train_x))
        model.train()
        total = 0.0
        seen = 0
        for start in range(0, len(train_x), 256):
            if minutes > 0 and time.monotonic() - started > minutes * 60:
                break
            batch, target = lot(train_x, train_y, start, 256, device)
            optimizer.zero_grad()
            loss = criterion(model(batch), target)
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(target)
            seen += len(target)
        done = epoch
        acc = exactitude(model, eval_x, eval_y, device)
        history.append((epoch, total / max(1, seen), acc, time.monotonic() - started))
        print(f"époque {epoch} perte {history[-1][1]:.4f} eval {acc:.3f} {history[-1][3]:.0f}s", flush=True)
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state": model.cpu().state_dict(), "noms": names, "taille": SIZE}, WEIGHTS_PATH)
    elapsed = time.monotonic() - started
    lines = [
        "# CNN des caractères",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Réseau écrit de zéro. Aucun poids extérieur, aucun YOLO.",
        f"- Appareil : {device.type}. Époques terminées : {done}/{epochs}. Durée : {elapsed / 60:.1f} min. Limite demandée : {minutes if minutes > 0 else 'aucune'} min.",
        f"- Caractères d'entraînement : {len(train_y)}. Caractères de la part tenue à part : {len(eval_y)}.",
        f"- Classes ({len(names)}) lues dans `configs/plaque_format.yaml`, statut À VALIDER.",
        f"- Poids : `{WEIGHTS_PATH.relative_to(PROJECT)}`.",
        "",
        "L'exactitude ci-dessous porte sur des caractères déjà segmentés, appariés de gauche à droite parce que le nombre de contours égalait le texte posé. Ce n'est pas une lecture de plaque réelle.",
        "",
        "| Époque | Perte | Exactitude sur la part tenue à part | Secondes |",
        "| --- | --- | --- | --- |",
    ]
    for epoch, loss, acc, seconds in history:
        lines.append(f"| {epoch} | {loss:.4f} | {100 * acc:.1f} % | {seconds:.0f} |")
    if not history:
        lines.append("| — | — | — | 0 |")
    lines.append("")
    (PROJECT / "reports" / "ocr_chars.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(WEIGHTS_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description="Entraîne la CNN de caractères sur CPU, avec une limite de temps.")
    parser.add_argument("--minutes", type=float, default=20)
    parser.add_argument("--epochs", type=int, default=12)
    args = parser.parse_args()
    entrainer(args.minutes, args.epochs)


if __name__ == "__main__":
    main()
