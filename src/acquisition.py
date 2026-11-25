"""Lecture d'une vidéo, image par image."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class Frame:
    index: int
    time_s: float
    image: np.ndarray


def open_video(path: Path | str):
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise FileNotFoundError(f"Vidéo illisible : {path}")
    return capture


def frames(path: Path | str):
    capture = open_video(path)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    index = 0
    try:
        while True:
            ok, image = capture.read()
            if not ok:
                break
            time_s = index / fps if fps else 0.0
            yield Frame(index=index, time_s=time_s, image=image)
            index += 1
    finally:
        capture.release()
