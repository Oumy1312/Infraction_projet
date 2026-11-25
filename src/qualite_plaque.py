"""Seuils de docs/critere_qualite_plaque.md. Ils ne sont pas ajustés après les scores."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from src.plaques_reelles import plus_grande_boite

LARGEUR_MIN = 96
HAUTEUR_MIN = 24
LAPLACIEN_MIN = 50.0
MARGE_BORD = 1


def nettete(crop: np.ndarray) -> float:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def qualite_suffisante(crop: np.ndarray, coupee: bool) -> bool:
    if crop is None or crop.size == 0 or coupee:
        return False
    height, width = crop.shape[:2]
    return width >= LARGEUR_MIN and height >= HAUTEUR_MIN and nettete(crop) >= LAPLACIEN_MIN


def vehicule_de(source: str) -> str:
    return "moto" if source == "moped" else "voiture"


def est_coupee(image_path: Path | str) -> bool:
    path = Path(image_path)
    label = path.parent.parent / "labels" / f"{path.stem}.txt"
    image = cv2.imread(str(path))
    if image is None or not label.is_file():
        return False
    height, width = image.shape[:2]
    box = plus_grande_boite(label, width, height)
    if box is None:
        return False
    x1, y1, x2, y2 = box
    return x1 <= MARGE_BORD or y1 <= MARGE_BORD or x2 >= width - MARGE_BORD or y2 >= height - MARGE_BORD
