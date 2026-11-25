"""Enchaîne acquisition, couleur du feu, suivi, franchissement et preuve."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from src.feu import (
    DEFAULT_M_S,
    DEFAULT_N_S,
    LisseurFeu,
    backend_depuis,
    classify_bgr,
    classify_box,
    fusionner,
    load_config,
    rouge_confirme_avant,
)
from src.feu_cnn import charger, predire
from src.franchissement import Detection, Observation, StopLine, find_infractions
from src.plaque import rectify, select_sharpest
from src.preuve import connect, record, write_pdf
from src.vehicules import update_tracks

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT / "config.yaml"
HSV_V3 = PROJECT / "configs" / "hsv_v3.yaml"
_CNN = None


def load_project_config(path: Path | str | None = None) -> dict:
    config_path = Path(path) if path else DEFAULT_CONFIG
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"config illisible : {config_path}")
    return payload


def stop_line_from_config(config: dict, width: int | None = None, height: int | None = None) -> StopLine:
    x1, y1, x2, y2 = config["scene"]["stop_line"]
    if width and height and max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1:
        return StopLine(x1 * width, y1 * height, x2 * width, y2 * height)
    return StopLine(float(x1), float(y1), float(x2), float(y2))


def light_zone(config: dict, width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = config["scene"]["feu_zone"]
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1:
        return int(x1 * width), int(y1 * height), int(x2 * width), int(y2 * height)
    return int(x1), int(y1), int(x2), int(y2)


def apply_orange_tolerance(observations: list[Observation], times: list[float], tolerance_s: float) -> list[Observation]:
    """Un orange qui suit un rouge de moins de tolerance_s secondes compte comme un rouge."""
    last_red = None
    adjusted = []
    for observation, instant in zip(observations, times):
        color = observation.color
        if color == "rouge":
            last_red = instant
        elif color == "orange" and last_red is not None and instant - last_red <= tolerance_s:
            color = "rouge"
        adjusted.append(replace(observation, color=color))
    return adjusted


def decide(observations: list[Observation], times: list[float], config: dict, width: int | None = None, height: int | None = None) -> list[dict]:
    tolerance = float(config["scene"]["orange_tolerance_s"])
    adjusted = apply_orange_tolerance(observations, times, tolerance)
    return find_infractions(adjusted, stop_line_from_config(config, width, height))


def cadence_traitee(times: list[float], default: float = 30.0) -> float:
    deltas = [right - left for left, right in zip(times, times[1:]) if right > left]
    if not deltas:
        return default
    return 1.0 / (sum(deltas) / len(deltas))


def lisseur_pour(scene: dict, fps: float) -> LisseurFeu:
    if "vote_n_s" in scene or "confirm_m_s" in scene:
        return LisseurFeu.depuis_secondes(
            float(scene.get("vote_n_s", DEFAULT_N_S)),
            float(scene.get("confirm_m_s", DEFAULT_M_S)),
            fps,
        )
    if "vote_n" in scene or "confirm_m" in scene:
        return LisseurFeu(int(scene.get("vote_n", 5)), int(scene.get("confirm_m", 3)))
    return LisseurFeu.depuis_secondes(DEFAULT_N_S, DEFAULT_M_S, fps)


def _cnn():
    global _CNN
    if _CNN is None:
        _CNN = charger()
    return _CNN


def _crop_zone(frame_bgr, config: dict):
    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = light_zone(config, width, height)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame_bgr[y1:y2, x1:x2]


def color_of_frame(frame_bgr, config: dict) -> str:
    """hsv lit config.yaml. cnn et fusion n'utilisent le réseau que si ce backend est choisi."""
    backend = backend_depuis(config.get("feu", {}))
    if backend == "hsv":
        height, width = frame_bgr.shape[:2]
        return classify_box(frame_bgr, light_zone(config, width, height), config["feu"])
    crop = _crop_zone(frame_bgr, config)
    if crop is None:
        return "inconnu"
    if backend == "cnn":
        label, _score = predire(_cnn(), crop)
        return label
    hsv_label = classify_bgr(crop, load_config(HSV_V3))
    cnn_label, _score = predire(_cnn(), crop)
    return fusionner(hsv_label, cnn_label)


def write_proofs(events: list[dict], database: Path | str, pdf_dir: Path | str) -> list[Path]:
    folder = Path(pdf_dir)
    folder.mkdir(parents=True, exist_ok=True)
    connection = connect(database)
    written = []
    try:
        for event in events:
            record(
                connection,
                frame_index=int(event["index"]),
                track_id=int(event["track_id"]),
                color=str(event["color"]),
                note="franchissement",
            )
            pdf = write_pdf(
                folder / f"preuve_{event['track_id']}_{event['index']}.pdf",
                "Preuve d'infraction",
                [
                    f"Piste {event['track_id']}",
                    f"Image {event['index']}",
                    f"Couleur retenue : {event['color']}",
                ],
            )
            written.append(pdf)
    finally:
        connection.close()
    return written


def run(video_frames, detect, config: dict, tracker=None) -> dict:
    """Enchaîne couleur du feu, suivi, franchissement et choix de la plaque la plus nette.

    detect(image) renvoie des dicts xyxy, conf, cls, et kind « vehicle » ou « plate ».
    Sans tracker, chaque véhicule doit déjà porter track_id.
    """
    raw_colors = []
    times = []
    kept_boxes = []
    plates = []
    width = height = None
    scene = config.get("scene", {})
    for frame in video_frames:
        image = frame.image
        if width is None:
            height, width = image.shape[:2]
        raw_colors.append(color_of_frame(image, config))
        found = list(detect(image))
        vehicles = [item for item in found if item.get("kind", "vehicle") != "plate"]
        if tracker is not None:
            boxes = [(track["track_id"], track["xyxy"]) for track in update_tracks(tracker, vehicles)]
        else:
            boxes = [(int(item["track_id"]), tuple(item["xyxy"])) for item in vehicles]
        kept_boxes.append(boxes)
        times.append(frame.time_s)
        for item in found:
            if item.get("kind") == "plate":
                plates.append(rectify(image, item["xyxy"]))
    fps = cadence_traitee(times)
    lisseur = lisseur_pour(scene, fps)
    colors = [lisseur.ajouter(color) for color in raw_colors]
    observations = [
        observation(index, color, boxes)
        for index, (color, boxes) in enumerate(zip(colors, kept_boxes))
    ]
    events = [
        event
        for event in decide(observations, times, config, width, height)
        if rouge_confirme_avant(lisseur.etats, int(event["index"]), lisseur.m)
    ]
    return {
        "events": events,
        "etats": list(lisseur.etats),
        "fps": fps,
        "lisseur_n": lisseur.n,
        "lisseur_m": lisseur.m,
        "plate_index": select_sharpest(plates) if plates else None,
        "plates": plates,
    }


def observation(index: int, color: str, tracks: list[tuple[int, tuple[float, float, float, float]]]) -> Observation:
    return Observation(index, color, tuple(Detection(track_id, bbox) for track_id, bbox in tracks))
