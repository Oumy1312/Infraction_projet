#!/usr/bin/env python3
"""Extrait des images à pas régulier pour annoter data/test_scenes.

    python scripts/08_extract_frames.py video.mp4 --every 1.0
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = PROJECT / "data" / "test_scenes" / "images"


def extract(video: Path, dest: Path, every_s: float) -> list[Path]:
    if every_s <= 0:
        raise ValueError("le pas doit être positif")
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise FileNotFoundError(f"vidéo illisible : {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    index = 0
    next_time = 0.0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            time_s = index / fps if fps else float(index)
            if time_s + 1e-6 >= next_time:
                name = f"{video.stem}_{index:06d}.jpg"
                path = dest / name
                if not cv2.imwrite(str(path), frame):
                    raise OSError(f"écriture impossible : {path}")
                written.append(path)
                next_time += every_s
            index += 1
    finally:
        capture.release()
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrait des images à intervalle régulier.")
    parser.add_argument("video", type=Path)
    parser.add_argument("--every", type=float, default=1.0, help="pas en secondes")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = parser.parse_args()
    written = extract(args.video, args.dest, args.every)
    print(f"{len(written)} images dans {args.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
