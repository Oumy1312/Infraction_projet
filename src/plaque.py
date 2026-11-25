"""Recadrage, redressement et choix de la vue la plus nette d'une plaque."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def yolo_box_to_pixels(cx: float, cy: float, width: float, height: float, image_width: int, image_height: int) -> tuple[int, int, int, int]:
    x1 = int(round((cx - width / 2) * image_width))
    y1 = int(round((cy - height / 2) * image_height))
    x2 = int(round((cx + width / 2) * image_width))
    y2 = int(round((cy + height / 2) * image_height))
    return x1, y1, x2, y2


def crop_box(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = box
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(width, int(x2)), min(height, int(y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("cadre de plaque vide")
    return image[y1:y2, x1:x2].copy()


def warp_quad(image: np.ndarray, points: np.ndarray, output_width: int = 240, output_height: int = 80) -> np.ndarray:
    """points : quatre coins, ordre haut-gauche, haut-droit, bas-droit, bas-gauche."""
    source = np.asarray(points, dtype=np.float32)
    if source.shape != (4, 2):
        raise ValueError("quatre coins sont requis")
    destination = np.array(
        [[0, 0], [output_width - 1, 0], [output_width - 1, output_height - 1], [0, output_height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(source, destination)
    return cv2.warpPerspective(image, matrix, (output_width, output_height))


def rectify(image: np.ndarray, frame) -> np.ndarray:
    """frame est un rectangle xyxy ou quatre coins."""
    array = np.asarray(frame, dtype=np.float32)
    if array.shape == (4,):
        return crop_box(image, tuple(int(value) for value in array))
    if array.shape == (4, 2):
        return warp_quad(image, array)
    raise ValueError("cadre non reconnu")


def sharpness(image: np.ndarray) -> float:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def select_sharpest(images: list[np.ndarray]) -> int:
    if not images:
        raise ValueError("aucune image de plaque")
    scores = [sharpness(image) for image in images]
    return int(np.argmax(scores))


def read_bgr(path: Path | str) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(path)
    return image
