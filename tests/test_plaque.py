from pathlib import Path

import cv2
import numpy as np
import pytest

from src.plaque import crop_box, rectify, select_sharpest, sharpness, warp_quad, yolo_box_to_pixels

ROOT = Path(__file__).resolve().parents[1]
PLATES = ROOT / "data" / "processed" / "plates_detection"


def _one_plate():
    images = PLATES / "train" / "images"
    for image in sorted(images.iterdir()):
        label = PLATES / "train" / "labels" / f"{image.stem}.txt"
        if label.is_file() and label.read_text(encoding="utf-8").strip():
            return image, label
    pytest.skip("aucune plaque annotée")


def test_crop_from_processed_plate():
    image_path, label_path = _one_plate()
    image = cv2.imread(str(image_path))
    assert image is not None
    parts = label_path.read_text(encoding="utf-8").split()
    box = yolo_box_to_pixels(float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]), image.shape[1], image.shape[0])
    crop = crop_box(image, box)
    assert crop.size > 0
    assert crop.shape[0] <= image.shape[0]
    assert crop.shape[1] <= image.shape[1]


def test_sharpest_keeps_the_real_crop():
    image_path, label_path = _one_plate()
    image = cv2.imread(str(image_path))
    parts = label_path.read_text(encoding="utf-8").split()
    box = yolo_box_to_pixels(float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]), image.shape[1], image.shape[0])
    crop = crop_box(image, box)
    blurred = cv2.GaussianBlur(crop, (31, 31), 0)
    assert sharpness(crop) > sharpness(blurred)
    assert select_sharpest([blurred, crop]) == 1


def test_warp_quad_size():
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    image[20:80, 30:170] = (0, 0, 255)
    points = np.array([[30, 20], [169, 20], [169, 79], [30, 79]], dtype=np.float32)
    plate = warp_quad(image, points, output_width=120, output_height=40)
    assert plate.shape[:2] == (40, 120)
    assert rectify(image, points).shape[0] > 0
