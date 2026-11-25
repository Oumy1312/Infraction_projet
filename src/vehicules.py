"""Suivi des véhicules avec le ByteTrack d'Ultralytics.

Le fichier de configuration est le nôtre. Aucun poids n'est chargé ici :
le suivi reçoit des boîtes, ou un best.pt déjà produit par l'entraînement.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("YOLO_AUTOINSTALL", "false")

import numpy as np
import yaml

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_TRACKER = PROJECT / "configs" / "bytetrack.yaml"
STOCK_WEIGHTS = {
    "yolov8n.pt",
    "yolov8s.pt",
    "yolov8m.pt",
    "yolov8l.pt",
    "yolov8x.pt",
    "yolo11n.pt",
    "yolo11s.pt",
    "yolo11m.pt",
    "yolo11l.pt",
    "yolo11x.pt",
}


def load_tracker_args(path: Path | str | None = None) -> SimpleNamespace:
    config_path = Path(path) if path else DEFAULT_TRACKER
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("tracker_type") != "bytetrack":
        raise ValueError(f"configuration ByteTrack illisible : {config_path}")
    return SimpleNamespace(**payload)


class _Detections:
    """Boîtes numpy que BYTETracker indexe comme un résultat Ultralytics."""

    def __init__(self, conf: np.ndarray, cls: np.ndarray, xywh: np.ndarray) -> None:
        self.conf = conf
        self.cls = cls
        self.xywh = xywh

    def __len__(self) -> int:
        return int(len(self.conf))

    def __getitem__(self, mask) -> "_Detections":
        return _Detections(self.conf[mask], self.cls[mask], self.xywh[mask])


def new_tracker(path: Path | str | None = None, frame_rate: int = 30):
    from ultralytics.trackers.byte_tracker import BYTETracker

    args = load_tracker_args(path)
    if frame_rate != 30:
        args.track_buffer = max(1, int(args.track_buffer * frame_rate / 30))
    return BYTETracker(args)


def _as_results(detections: list[dict]) -> _Detections:
    if detections:
        xyxy = np.array([item["xyxy"] for item in detections], dtype=np.float32)
        conf = np.array([item["conf"] for item in detections], dtype=np.float32)
        cls = np.array([item["cls"] for item in detections], dtype=np.float32)
    else:
        xyxy = np.zeros((0, 4), dtype=np.float32)
        conf = np.zeros((0,), dtype=np.float32)
        cls = np.zeros((0,), dtype=np.float32)
    xywh = np.zeros_like(xyxy)
    if len(xyxy):
        xywh[:, 0] = (xyxy[:, 0] + xyxy[:, 2]) / 2
        xywh[:, 1] = (xyxy[:, 1] + xyxy[:, 3]) / 2
        xywh[:, 2] = xyxy[:, 2] - xyxy[:, 0]
        xywh[:, 3] = xyxy[:, 3] - xyxy[:, 1]
    return _Detections(conf, cls, xywh)


def _rows(output) -> list[list[float]]:
    if output is None:
        return []
    if isinstance(output, list):
        return [list(map(float, row)) for row in output if row is not None and len(row) >= 5]
    array = np.asarray(output)
    if array.size == 0:
        return []
    if array.ndim == 1:
        array = array.reshape(1, -1)
    return array.tolist()


def update_tracks(tracker, detections: list[dict]) -> list[dict]:
    """detections : xyxy, conf, cls. Retourne les pistes actives."""
    output = tracker.update(_as_results(detections))
    tracks = []
    for row in _rows(output):
        tracks.append(
            {
                "xyxy": (row[0], row[1], row[2], row[3]),
                "track_id": int(row[4]),
                "conf": float(row[5]) if len(row) > 5 else 1.0,
                "cls": int(row[6]) if len(row) > 6 else 0,
            }
        )
    return tracks


def require_trained_weights(model_path: Path | str) -> Path:
    path = Path(model_path)
    if path.name.lower() in STOCK_WEIGHTS or not path.is_file():
        raise FileNotFoundError(
            f"Il faut un best.pt déjà produit, pas un poids à télécharger : {path.name}"
        )
    return path


def track_video(model_path: Path | str, source: Path | str, tracker_path: Path | str | None = None):
    """Ouvre un best.pt existant. N'est pas appelé par les tests."""
    weights = require_trained_weights(model_path)
    config = Path(tracker_path) if tracker_path else DEFAULT_TRACKER
    from ultralytics import YOLO

    model = YOLO(str(weights))
    return model.track(source=str(source), tracker=str(config), persist=True, stream=True)
