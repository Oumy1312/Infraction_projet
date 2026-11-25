"""Découpe des caractères d'une plaque par contours. Pas de vérité terrain ici."""

from __future__ import annotations

import random
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]


def _gris(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _boites(binary: np.ndarray) -> list[tuple[int, int, int, int]]:
    height, width = binary.shape[:2]
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, box_w, box_h = cv2.boundingRect(contour)
        if box_h < 0.35 * height or box_h > 0.98 * height:
            continue
        if box_w < 0.012 * width or box_w > 0.40 * width:
            continue
        if box_w / max(box_h, 1) < 0.12:
            continue
        if box_w * box_h < 30:
            continue
        if (x <= 3 or x + box_w >= width - 3) and box_w < 0.08 * width:
            continue
        boxes.append((x, y, box_w, box_h))
    if not boxes:
        return []
    median_h = float(np.median([box[3] for box in boxes]))
    median_y = float(np.median([box[1] + box[3] / 2 for box in boxes]))
    kept = []
    for box in boxes:
        center = box[1] + box[3] / 2
        if abs(center - median_y) > 0.55 * median_h:
            continue
        if box[3] < 0.50 * median_h or box[3] > 1.9 * median_h:
            continue
        kept.append(box)
    kept.sort(key=lambda box: box[0])
    kept = _rattacher_points(kept)
    merged: list[tuple[int, int, int, int]] = []
    for box in kept:
        if merged and box[0] < merged[-1][0] + merged[-1][2] * 0.45:
            x, y, box_w, box_h = merged[-1]
            right = max(x + box_w, box[0] + box[2])
            top = min(y, box[1])
            bottom = max(y + box_h, box[1] + box[3])
            merged[-1] = (x, top, right - x, bottom - top)
        else:
            merged.append(box)
    return merged


def _union(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x = min(left[0], right[0])
    y = min(left[1], right[1])
    right_edge = max(left[0] + left[2], right[0] + right[2])
    bottom = max(left[1] + left[3], right[1] + right[3])
    return (x, y, right_edge - x, bottom - y)


def _rattacher_points(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Un point ou un fragment étroit rejoint le caractère dont il partage l'abscisse."""
    if len(boxes) < 2:
        return boxes
    heights = [box[3] for box in boxes]
    median_h = float(np.median(heights))
    large = [index for index, height in enumerate(heights) if height >= 0.62 * median_h]
    small = [index for index, height in enumerate(heights) if height < 0.62 * median_h]
    if not large or not small:
        return boxes
    groups = {index: boxes[index] for index in large}
    for index in small:
        x, y, width, height = boxes[index]
        best = None
        best_overlap = 0
        for other in large:
            ox, oy, owidth, oheight = boxes[other]
            overlap = min(x + width, ox + owidth) - max(x, ox)
            gap = max(0, max(x, ox) - min(x + width, ox + owidth))
            if overlap > best_overlap or (best is None and gap < 0.8 * width and overlap >= 0):
                if overlap > 0 or gap < 0.8 * width:
                    best = other
                    best_overlap = max(overlap, 0)
        if best is not None:
            groups[best] = _union(groups[best], boxes[index])
    return [groups[index] for index in large]


def _binaires(gray: np.ndarray) -> list[np.ndarray]:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 8
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))
    return [cv2.dilate(otsu, kernel, iterations=1), cv2.dilate(adaptive, kernel, iterations=1)]


def segmenter(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Boîtes (x, y, largeur, hauteur), de gauche à droite, dans l'image d'origine."""
    if image is None or image.size == 0:
        return []
    gray = _gris(image)
    scale = 1.0
    if gray.shape[0] < 70:
        scale = 70 / max(1, gray.shape[0])
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    found: list[tuple[int, int, int, int]] = []
    for binary in _binaires(gray):
        boxes = _boites(binary)
        if len(boxes) > len(found):
            found = boxes
    if scale == 1.0:
        return found
    return [
        (int(round(x / scale)), int(round(y / scale)), max(1, int(round(w / scale))), max(1, int(round(h / scale))))
        for x, y, w, h in found
    ]


def mesurer(n: int = 100, seed: int = 42) -> dict:
    from src.ocr_plaque import bornes_caracteres, charger_format, plausible
    from src.plaques_reelles import lister, recadrer

    fmt = charger_format()
    low, high = bornes_caracteres(fmt)
    by_source: dict[str, list[dict]] = {}
    for item in lister():
        by_source.setdefault(item["source"], []).append(item)
    rng = random.Random(seed)
    chosen = []
    sources = sorted(by_source)
    while len(chosen) < n and any(by_source.values()):
        for source in sources:
            pool = by_source.get(source) or []
            if not pool or len(chosen) >= n:
                continue
            pick = pool.pop(rng.randrange(len(pool)))
            crop = recadrer(pick)
            if crop is None or crop.shape[0] < 16 or crop.shape[1] < 40:
                continue
            chosen.append({**pick, "crop": crop})
    rows = []
    for item in chosen:
        count = len(segmenter(item["crop"]))
        rows.append(
            {
                "source": item["source"],
                "nom": item["nom"],
                "crop": item["crop"],
                "compte": count,
                "plausible": plausible(count, fmt),
            }
        )
    return {"rows": rows, "low": low, "high": high, "fmt": fmt}


def main() -> None:
    if str(PROJECT) not in sys.path:
        sys.path.insert(0, str(PROJECT))
    from src.plaques_reelles import ecrire_planche

    measured = mesurer(100, 42)
    rows = measured["rows"]
    ok = sum(1 for row in rows if row["plausible"])
    report = PROJECT / "reports" / "segmentation_reelle.md"
    lines = [
        "# Segmentation sur plaques réelles",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Plaques testées : {len(rows)}.",
        f"- Intervalle jugé plausible, déduit de `configs/plaque_format.yaml` (statut À VALIDER) : {measured['low']} à {measured['high']} caractères.",
        "- Ce taux n'est pas une précision : aucune transcription de ces plaques n'existe.",
        "",
        f"- Plaques dont le nombre de contours retenus tombe dans l'intervalle : {ok}/{len(rows)} ({100 * ok / max(1, len(rows)):.1f} %).",
        "",
        "| Source | Testées | Dans l'intervalle |",
        "| --- | --- | --- |",
    ]
    sources = sorted({row["source"] for row in rows})
    for source in sources:
        group = [row for row in rows if row["source"] == source]
        inside = sum(1 for row in group if row["plausible"])
        lines.append(f"| {source} | {len(group)} | {inside} |")
    failures = [row for row in rows if not row["plausible"]]
    lines.extend(
        [
            "",
            f"Hors intervalle : {len(failures)}. La planche en montre {min(30, len(failures))}.",
            "La légende est le nombre de caractères trouvés, pas une lecture.",
            "",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sheet = [
        {"crop": row["crop"], "caption": f"{row['source']} · {row['compte']} caractères"}
        for row in failures[:30]
    ]
    destination = PROJECT / "reports" / "planche_segmentation_echecs.jpg"
    if sheet:
        ecrire_planche(sheet, destination, "Hors intervalle plausible. Compte trouvé, sans transcription.", columns=5)
    print(f"{ok}/{len(rows)} dans l'intervalle {measured['low']}-{measured['high']}")
    print(report)


if __name__ == "__main__":
    main()
