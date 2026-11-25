"""Réglages de session. N'écrit jamais le config.yaml du projet."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from src.acquisition import Frame

PROJECT = Path(__file__).resolve().parents[1]
PROJECT_CONFIG = (PROJECT / "config.yaml").resolve()


def assert_session_path(path: Path) -> Path:
    destination = Path(path).resolve()
    if destination == PROJECT_CONFIG:
        raise ValueError("le config.yaml du projet ne doit pas être modifié")
    return destination


def session_config(base: dict, stop_line: list[float], feu_zone: list[float], backend: str = "hsv") -> dict:
    payload = yaml.safe_load(yaml.safe_dump(base))
    payload.setdefault("feu", {})
    payload["feu"]["backend"] = backend
    payload.setdefault("scene", {})
    payload["scene"]["stop_line"] = [float(value) for value in stop_line]
    payload["scene"]["feu_zone"] = [float(value) for value in feu_zone]
    return payload


def write_session(path: Path, payload: dict) -> Path:
    destination = assert_session_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return destination


def demo_frames(count: int = 40, fps: float = 10.0) -> list[Frame]:
    """Scène peinte : feu rouge, puis gris, puis vert. Le véhicule descend."""
    frames = []
    for index in range(count):
        image = np.zeros((240, 320, 3), dtype=np.uint8)
        image[:, :] = (30, 30, 30)
        if index < 25:
            color = (0, 0, 220)
        elif index < 30:
            color = (90, 90, 90)
        else:
            color = (0, 180, 0)
        image[12:60, 144:176] = color
        frames.append(Frame(index=index, time_s=index / fps, image=image))
    return frames


def demo_detect(_image, index: int) -> list[dict]:
    bottom = 80 + index * 6
    return [{"xyxy": (140, bottom - 40, 190, bottom), "conf": 0.86, "cls": 0, "track_id": 1, "kind": "vehicle"}]
