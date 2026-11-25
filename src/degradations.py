"""Dégradations d'une plaque. Chaque fonction ne fait qu'un effet."""

from __future__ import annotations

import random

import cv2
import numpy as np


def flou_mouvement(image: np.ndarray, rng: random.Random, longueur: int | None = None) -> np.ndarray:
    size = longueur or rng.choice((5, 7, 9, 11))
    kernel = np.zeros((size, size), dtype=np.float32)
    if rng.random() < 0.5:
        kernel[size // 2, :] = 1.0
    else:
        kernel[:, size // 2] = 1.0
    kernel /= size
    return cv2.filter2D(image, -1, kernel)


def compression_jpeg(image: np.ndarray, rng: random.Random, qualite: int | None = None) -> np.ndarray:
    quality = qualite if qualite is not None else rng.randint(20, 70)
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        return image
    decoded = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return image if decoded is None else decoded


def basse_resolution(image: np.ndarray, rng: random.Random, echelle: float | None = None) -> np.ndarray:
    height, width = image.shape[:2]
    scale = echelle if echelle is not None else rng.uniform(0.25, 0.55)
    small_w = max(8, int(round(width * scale)))
    small_h = max(8, int(round(height * scale)))
    small = cv2.resize(image, (small_w, small_h), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR)


def ombre(image: np.ndarray, rng: random.Random) -> np.ndarray:
    height, width = image.shape[:2]
    dark = rng.uniform(0.35, 0.8)
    if rng.random() < 0.5:
        ramp = np.linspace(dark, 1.0, width, dtype=np.float32)
        if rng.random() < 0.5:
            ramp = ramp[::-1]
        ramp = ramp[None, :, None]
    else:
        ramp = np.linspace(dark, 1.0, height, dtype=np.float32)
        if rng.random() < 0.5:
            ramp = ramp[::-1]
        ramp = ramp[:, None, None]
    return np.clip(image.astype(np.float32) * np.ascontiguousarray(ramp), 0, 255).astype(np.uint8)


def perspective(image: np.ndarray, rng: random.Random, amplitude: float | None = None) -> np.ndarray:
    height, width = image.shape[:2]
    amount = amplitude if amplitude is not None else rng.uniform(0.04, 0.12)
    src = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    jitter = np.array(
        [[rng.uniform(-amount, amount) * width, rng.uniform(-amount, amount) * height] for _ in range(4)],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(src, src + jitter)
    return cv2.warpPerspective(image, transform, (width, height), borderValue=(245, 245, 245))


def bruit_fond(image: np.ndarray, rng: random.Random, sigma: float | None = None) -> np.ndarray:
    scale = sigma if sigma is not None else rng.uniform(6, 18)
    noise = np.random.default_rng(rng.randrange(1, 2**31)).normal(0, scale, image.shape)
    return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def sale_rayee(image: np.ndarray, rng: random.Random) -> np.ndarray:
    height, width = image.shape[:2]
    overlay = image.copy()
    for _ in range(rng.randint(6, 14)):
        center = (rng.randint(0, max(0, width - 1)), rng.randint(0, max(0, height - 1)))
        axes = (rng.randint(6, max(7, width // 6)), rng.randint(2, 8))
        shade = rng.randint(40, 170)
        cv2.ellipse(overlay, center, axes, rng.randint(0, 180), 0, 360, (shade, shade, shade), -1)
    dirty = cv2.addWeighted(image, 0.82, overlay, 0.18, 0)
    for _ in range(rng.randint(2, 6)):
        y = rng.randint(0, max(0, height - 1))
        cv2.line(dirty, (0, y), (width - 1, min(height - 1, y + rng.randint(-3, 3))), (rng.randint(20, 90),) * 3, 1)
    return dirty


EFFETS = {
    "flou de mouvement": flou_mouvement,
    "compression JPEG": compression_jpeg,
    "basse résolution": basse_resolution,
    "ombre": ombre,
    "perspective": perspective,
    "bruit de fond": bruit_fond,
    "plaque sale ou rayée": sale_rayee,
}


def ajuster_photometrie(image: np.ndarray, luminosite: float, contraste: float) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    spread = float(gray.std())
    if spread < 1:
        spread = 1.0
    cible = (gray - float(gray.mean())) / spread * float(contraste) + float(luminosite)
    delta = cible - gray
    return np.clip(image.astype(np.float32) + delta[:, :, None], 0, 255).astype(np.uint8)


def redimensionner(image: np.ndarray, width: int, height: int) -> np.ndarray:
    return cv2.resize(image, (max(8, int(width)), max(8, int(height))), interpolation=cv2.INTER_AREA)
