#!/usr/bin/env python3
"""Entraîne le CRNN de zéro sur les plaques synthétiques. Pas de plaque réelle.

    python scripts/14_train_crnn.py --minutes 20
    python scripts/14_train_crnn.py --minutes 0 --epochs 20 --reprise
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.crnn import (  # noqa: E402
    CHECKPOINT_PATH,
    HAUTEUR,
    LARGEUR,
    WEIGHTS_PATH,
    PetitCRNN,
    alphabet_de,
    decoder_glouton,
    preparer_plaque,
)
from src.ocr_plaque import charger_format, normaliser, taux_erreur  # noqa: E402

DATA = PROJECT / "data" / "synthetic" / "plaques"
SEED = 42


def lire_etiquettes() -> list[dict]:
    path = DATA / "etiquettes.csv"
    if not path.is_file():
        raise SystemExit("etiquettes synthétiques absentes. Le CRNN n'utilise pas les plaques réelles.")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def charger_images(part: str) -> tuple[np.ndarray, list[str]]:
    images = []
    texts = []
    folder = DATA / "images"
    fmt = charger_format()
    for row in lire_etiquettes():
        if row.get("part") != part:
            continue
        image = cv2.imread(str(folder / row["image"]))
        if image is None:
            continue
        prepared = preparer_plaque(image)[0]
        images.append(np.clip(prepared * 255.0, 0, 255).astype(np.uint8))
        texts.append(normaliser(row.get("caracteres", ""), fmt))
    if not images:
        raise SystemExit(f"aucune image synthétique pour la part {part}")
    return np.stack(images), texts


def lot(images: np.ndarray, texts: list[str], alphabet: tuple[str, ...], start: int, batch: int, device):
    stop = min(start + batch, len(images))
    view = images[start:stop]
    tensor = torch.from_numpy(view.astype(np.float32) / 255.0).unsqueeze(1).to(device)
    index = {char: position + 1 for position, char in enumerate(alphabet)}
    targets = []
    for text in texts[start:stop]:
        coded = [index[char] for char in text if char in index]
        targets.append(coded or [index[alphabet[0]]])
    lengths = torch.tensor([len(item) for item in targets], dtype=torch.long)
    flat = torch.tensor([symbol for item in targets for symbol in item], dtype=torch.long)
    return tensor, flat.to(device), lengths.to(device)


def evaluer(model, alphabet, images, texts, device) -> tuple[float, float]:
    model.eval()
    exact = 0
    error = 0.0
    with torch.no_grad():
        for start in range(0, len(images), 64):
            view = images[start : start + 64]
            tensor = torch.from_numpy(view.astype(np.float32) / 255.0).unsqueeze(1).to(device)
            predictions = decoder_glouton(model(tensor), alphabet)
            for prediction, reference in zip(predictions, texts[start : start + 64]):
                exact += int(prediction == reference)
                error += taux_erreur(reference, prediction)
    count = max(1, len(texts))
    return exact / count, error / count


def entrainer(minutes: float, epochs: int, reprise: bool) -> None:
    fmt = charger_format()
    alphabet = alphabet_de(fmt)
    torch.manual_seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = PetitCRNN(len(alphabet) + 1).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    start_epoch = 1
    if reprise and CHECKPOINT_PATH.is_file():
        blob = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=False)
        if tuple(blob["alphabet"]) != alphabet:
            raise SystemExit("le point de reprise n'a pas le même alphabet que plaque_format.yaml")
        model.load_state_dict(blob["state"])
        optimizer.load_state_dict(blob["optim"])
        start_epoch = int(blob["epoch"]) + 1
    criterion = nn.CTCLoss(blank=0, zero_infinity=True)
    print("chargement des images synthétiques", flush=True)
    train_x, train_y = charger_images("train")
    eval_x, eval_y = charger_images("eval")
    order = np.arange(len(train_x))
    rng = np.random.default_rng(SEED)
    started = time.monotonic()
    history = []
    done = start_epoch - 1
    for epoch in range(start_epoch, start_epoch + epochs):
        if minutes > 0 and time.monotonic() - started > minutes * 60:
            break
        rng.shuffle(order)
        train_x = train_x[order]
        train_y = [train_y[int(i)] for i in order]
        order = np.arange(len(train_x))
        model.train()
        total = 0.0
        seen = 0
        for start in range(0, len(train_x), 64):
            if minutes > 0 and time.monotonic() - started > minutes * 60:
                break
            batch, target, lengths = lot(train_x, train_y, alphabet, start, 64, device)
            optimizer.zero_grad()
            logits = model(batch)
            log_probs = torch.log_softmax(logits, dim=2).permute(1, 0, 2)
            time_steps = torch.full((batch.shape[0],), log_probs.shape[0], dtype=torch.long, device=device)
            loss = criterion(log_probs, target, time_steps, lengths)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step()
            total += float(loss.detach()) * batch.shape[0]
            seen += batch.shape[0]
        done = epoch
        exact, cer = evaluer(model, alphabet, eval_x, eval_y, device)
        history.append((epoch, total / max(1, seen), exact, cer, time.monotonic() - started))
        CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state": model.state_dict(),
                "optim": optimizer.state_dict(),
                "alphabet": alphabet,
                "epoch": epoch,
                "hauteur": HAUTEUR,
                "largeur": LARGEUR,
            },
            CHECKPOINT_PATH,
        )
        print(
            f"époque {epoch} perte {history[-1][1]:.3f} exacte {exact:.3f} CER {cer:.3f} {history[-1][4]:.0f}s",
            flush=True,
        )
    payload = {
        "state": model.cpu().state_dict(),
        "alphabet": alphabet,
        "epoch": done,
        "hauteur": HAUTEUR,
        "largeur": LARGEUR,
    }
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, WEIGHTS_PATH)
    lines = [
        "# CRNN",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Réseau écrit de zéro : convolutions, BiLSTM, perte CTC. Aucun poids pré-entraîné. Aucune plaque réelle.",
        f"- Entrée : niveaux de gris {HAUTEUR}×{LARGEUR}. Alphabet lu dans `configs/plaque_format.yaml` ({len(alphabet)} caractères, plus le blanc CTC).",
        f"- Appareil : {device.type}. Dernière époque : {done}. Durée de cette session : {(time.monotonic() - started) / 60:.1f} min.",
        f"- Synthétique d'entraînement : {len(train_y)}. Synthétique tenu à part : {len(eval_y)}.",
        "",
        "Les chiffres ci-dessous sont des plaques entières synthétiques tenues à part. Ce n'est pas une précision sur les plaques réelles, ni l'exactitude de la CNN sur des caractères déjà segmentés.",
        "",
        "| Époque | Perte | Plaque entière exacte | CER | Secondes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for epoch, loss, exact, cer, seconds in history:
        lines.append(f"| {epoch} | {loss:.3f} | {100 * exact:.1f} % | {100 * cer:.1f} % | {seconds:.0f} |")
    if not history:
        lines.append("| — | — | — | — | 0 |")
    lines.append("")
    (PROJECT / "reports" / "crnn.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(WEIGHTS_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description="Entraîne le CRNN sur les plaques synthétiques, avec reprise.")
    parser.add_argument("--minutes", type=float, default=20)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--reprise", action="store_true")
    args = parser.parse_args()
    entrainer(args.minutes, args.epochs, args.reprise)


if __name__ == "__main__":
    main()
