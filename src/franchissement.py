"""Franchissement d'une ligne d'arrêt.

Une observation est une image : couleur du feu et boîtes suivies.
Le point de référence est le milieu du bord bas de la boîte.
Une infraction est un franchissement pendant que le feu est rouge.
Un franchissement déjà compté (vert, orange ou rouge) ne l'est pas une seconde fois.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopLine:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Detection:
    track_id: int
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class Observation:
    index: int
    color: str
    detections: tuple[Detection, ...]


def bottom_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, _y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


def _orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def segments_cross(
    start: tuple[float, float],
    end: tuple[float, float],
    line: StopLine,
) -> bool:
    o1 = _orient(start[0], start[1], end[0], end[1], line.x1, line.y1)
    o2 = _orient(start[0], start[1], end[0], end[1], line.x2, line.y2)
    o3 = _orient(line.x1, line.y1, line.x2, line.y2, start[0], start[1])
    o4 = _orient(line.x1, line.y1, line.x2, line.y2, end[0], end[1])
    return o1 * o2 < 0 and o3 * o4 < 0


def find_infractions(observations: list[Observation], stop_line: StopLine) -> list[dict]:
    previous: dict[int, tuple[float, float]] = {}
    already_crossed: set[int] = set()
    events = []
    for observation in observations:
        for detection in observation.detections:
            point = bottom_center(detection.bbox)
            last = previous.get(detection.track_id)
            if (
                last is not None
                and detection.track_id not in already_crossed
                and segments_cross(last, point, stop_line)
            ):
                already_crossed.add(detection.track_id)
                if observation.color == "rouge":
                    events.append(
                        {
                            "track_id": detection.track_id,
                            "index": observation.index,
                            "color": observation.color,
                            "x": point[0],
                            "y": point[1],
                        }
                    )
            previous[detection.track_id] = point
    return events
