"""Petit réseau de l'état du feu. Les poids viennent d'un entraînement de zéro."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = PROJECT / "data" / "models" / "feu_cnn.pt"
NAMES = ("rouge", "orange", "vert", "autre")
SIZE = 48


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


def preparer(crop_bgr: np.ndarray) -> np.ndarray:
    resized = cv2.resize(crop_bgr, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    return np.transpose(rgb.astype(np.float32) / 255.0, (2, 0, 1))


def charger(path: Path | str | None = None) -> PetitFeu:
    weights = Path(path) if path else DEFAULT_WEIGHTS
    if not weights.is_file():
        raise FileNotFoundError(f"poids CNN introuvables : {weights}")
    blob = torch.load(weights, map_location="cpu", weights_only=False)
    model = PetitFeu()
    model.load_state_dict(blob["state"])
    model.eval()
    return model


def predire(model: PetitFeu, crop_bgr: np.ndarray) -> tuple[str, float]:
    if crop_bgr is None or crop_bgr.size == 0:
        return "autre", 0.0
    batch = torch.from_numpy(np.ascontiguousarray(preparer(crop_bgr))).unsqueeze(0)
    with torch.no_grad():
        scores = torch.softmax(model(batch), dim=1)[0]
    index = int(scores.argmax())
    return NAMES[index], float(scores[index])
