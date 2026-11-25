"""CRNN : convolution, BiLSTM, CTC. Aucun poids pré-entraîné.

L'alphabet vient de configs/plaque_format.yaml. L'entrée est une plaque
en niveaux de gris, 32 px de haut et 128 px de large.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn

from src.ocr_plaque import classes_de

PROJECT = Path(__file__).resolve().parents[1]
WEIGHTS_PATH = PROJECT / "data" / "models" / "crnn.pt"
CHECKPOINT_PATH = PROJECT / "data" / "models" / "crnn_last.pt"
HAUTEUR = 32
LARGEUR = 128
BLANK = 0


class PetitCRNN(nn.Module):
    def __init__(self, n_symboles: int) -> None:
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d((2, 1), (2, 1)),
            nn.Conv2d(128, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 32)),
        )
        self.lstm = nn.LSTM(128, 128, num_layers=1, bidirectional=True, batch_first=True)
        self.sortie = nn.Linear(256, n_symboles)
        self.sortie.bias.data[0] = -4.0

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        features = self.cnn(batch)
        sequence = features.squeeze(2).permute(0, 2, 1)
        sequence, _ = self.lstm(sequence)
        return self.sortie(sequence)


def alphabet_de(fmt) -> tuple[str, ...]:
    return classes_de(fmt)


def preparer_plaque(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    resized = cv2.resize(gray, (LARGEUR, HAUTEUR), interpolation=cv2.INTER_AREA)
    return (resized.astype(np.float32) / 255.0)[None, :, :]


def coder_cible(texte: str, alphabet: tuple[str, ...]) -> list[int]:
    index = {char: position + 1 for position, char in enumerate(alphabet)}
    return [index[char] for char in texte if char in index]


def reduire_ctc(indices: list[int], alphabet: tuple[str, ...], blank: int = BLANK) -> str:
    characters = []
    previous = None
    for symbol in indices:
        if symbol != previous and symbol != blank:
            position = symbol - 1
            if 0 <= position < len(alphabet):
                characters.append(alphabet[position])
        previous = symbol
    return "".join(characters)


def decoder_glouton(logits: torch.Tensor, alphabet: tuple[str, ...]) -> list[str]:
    chosen = logits.argmax(dim=-1).detach().cpu().tolist()
    return [reduire_ctc(sequence, alphabet) for sequence in chosen]


def charger(path: Path | str | None = None) -> tuple[PetitCRNN, tuple[str, ...]]:
    weights = Path(path) if path else WEIGHTS_PATH
    if not weights.is_file():
        raise FileNotFoundError(f"poids CRNN introuvables : {weights}")
    blob = torch.load(weights, map_location="cpu", weights_only=False)
    alphabet = tuple(blob["alphabet"])
    model = PetitCRNN(len(alphabet) + 1)
    model.load_state_dict(blob["state"])
    model.eval()
    return model, alphabet


def lire(model: PetitCRNN, alphabet: tuple[str, ...], image: np.ndarray) -> str:
    if image is None or image.size == 0:
        return ""
    batch = torch.from_numpy(np.ascontiguousarray(preparer_plaque(image))).unsqueeze(0)
    with torch.no_grad():
        logits = model(batch)
    return decoder_glouton(logits, alphabet)[0]
