#!/usr/bin/env python3
"""Évalue une seule fois les seuils de configs/hsv_v2.yaml.

Le jeu tenu à part est le même que scripts/06_eval_hsv.py (30 %, pHash).
Les seuils ne sont pas retouchés après cette mesure. config.yaml n'est pas lu
pour la décision v2, et n'est pas modifié.

    python scripts/06_eval_hsv_v2.py
"""

from __future__ import annotations

import importlib.util
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.feu import _mask, load_config

SPEC = importlib.util.spec_from_file_location("eval_hsv", PROJECT / "scripts" / "06_eval_hsv.py")
hsv = importlib.util.module_from_spec(SPEC)
sys.modules["eval_hsv"] = hsv
SPEC.loader.exec_module(hsv)

REPORTS = PROJECT / "reports"
V2_PATH = PROJECT / "configs" / "hsv_v2.yaml"
LABELS = ("rouge", "orange", "vert")
PREDICTED = ("rouge", "orange", "vert", "inconnu")
SEED = 42


def diagnose(crop: np.ndarray | None, config: dict) -> tuple[str, bool]:
    """Retourne la couleur et vrai si min_ratio a écarté la boîte."""
    if crop is None or crop.size == 0:
        return "inconnu", False
    image = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    total = image.shape[0] * image.shape[1]
    if total == 0:
        return "inconnu", False
    scores = {name: int(_mask(image, config[name]).sum()) for name in LABELS}
    best = max(scores, key=scores.get)
    rejected = scores[best] / total < float(config["min_ratio"])
    return ("inconnu" if rejected else best), rejected


def matrice(rows: list[dict], key: str) -> dict[str, Counter]:
    matrix = {true: Counter() for true in LABELS}
    for row in rows:
        matrix[row["true"]][row[key]] += 1
    return matrix


def precision(rows: list[dict], key: str) -> tuple[float, int, int]:
    if not rows:
        return 0.0, 0, 0
    hits = sum(row["true"] == row[key] for row in rows)
    return hits / len(rows), hits, len(rows)


def trop_petite(row: dict) -> bool:
    x1, y1, x2, y2 = row["box"]
    side = min(max(0, x2 - x1), max(0, y2 - y1))
    return side < 8 or row["area"] < 0.0004


def jitter(row: dict, rng: random.Random) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = row["box"]
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    shift_x = rng.uniform(0.10, 0.20) * width * rng.choice((-1, 1))
    shift_y = rng.uniform(0.10, 0.20) * height * rng.choice((-1, 1))
    scale_x = 1.0 + rng.uniform(0.10, 0.20) * rng.choice((-1, 1))
    scale_y = 1.0 + rng.uniform(0.10, 0.20) * rng.choice((-1, 1))
    center_x = (x1 + x2) / 2 + shift_x
    center_y = (y1 + y2) / 2 + shift_y
    half_w = width * scale_x / 2
    half_h = height * scale_y / 2
    return (
        int(round(center_x - half_w)),
        int(round(center_y - half_h)),
        int(round(center_x + half_w)),
        int(round(center_y + half_h)),
    )


def table(matrix: dict[str, Counter]) -> list[str]:
    lines = [
        "| Vrai \\ prédit | rouge | orange | vert | inconnu |",
        "| --- | --- | --- | --- | --- |",
    ]
    for true in LABELS:
        lines.append("| " + true + " | " + " | ".join(str(matrix[true][pred]) for pred in PREDICTED) + " |")
    return lines


def pct(value: float) -> str:
    return f"{value:.1%}"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    v1 = load_config(PROJECT / "config.yaml")
    v2 = load_config(V2_PATH)
    boxes = hsv.collect()
    images = sorted({item["image"] for item in boxes}, key=lambda path: str(path))
    assignment, _sizes = hsv.assign_images(images)
    evaluation = []
    for item in boxes:
        if assignment[item["image"]] != "evaluation":
            continue
        crop = hsv.crop_bgr(item)
        pred_v1, _rejected_v1 = diagnose(crop, v1)
        pred_v2, rejected = diagnose(crop, v2)
        evaluation.append({**item, "crop": crop, "v1": pred_v1, "v2": pred_v2, "min_ratio": rejected})

    matrix_v1 = matrice(evaluation, "v1")
    matrix_v2 = matrice(evaluation, "v2")
    score, hits, total = precision(evaluation, "v2")
    kept = [row for row in evaluation if not trop_petite(row)]
    score_kept, hits_kept, total_kept = precision(kept, "v2")
    rejected = sum(row["min_ratio"] for row in evaluation)
    orange_v1 = matrix_v1["orange"]["rouge"]
    orange_v2 = matrix_v2["orange"]["rouge"]

    rng = random.Random(SEED)
    noisy = []
    for row in evaluation:
        moved = jitter(row, rng)
        clone = {**row, "box": moved}
        pred, _rejected = diagnose(hsv.crop_bgr(clone), v2)
        noisy.append({**row, "bruit": pred})
    score_noise, hits_noise, total_noise = precision(noisy, "bruit")
    matrix_noise = matrice(noisy, "bruit")

    lines = [
        "# Évaluation HSV v2",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Seuils lus dans `configs/hsv_v2.yaml`. `config.yaml` n'a pas été modifié.",
        "- Une seule passe sur les 30 % tenus à part (mêmes groupes pHash que `reports/hsv_eval.md`, graine 42). Aucun seuil n'a été repris ensuite.",
        "",
        "## Volume",
        "",
        f"- Évaluation : {total} boîtes.",
        f"- Précision globale v2 : {pct(score)} ({hits} / {total}).",
        f"- v1 sur les mêmes boîtes, pour mémoire : {pct(precision(evaluation, 'v1')[0])} ({precision(evaluation, 'v1')[1]} / {total}).",
        "",
        "## Matrice v2",
        "",
        *table(matrix_v2),
        "",
        f"- Orange lu comme rouge : {orange_v2} (v1 sur les mêmes boîtes : {orange_v1}).",
        "",
        "## Filtre min_ratio et taille",
        "",
        f"- Boîtes écartées par min_ratio : {rejected} / {total} ({pct(rejected / total if total else 0)}).",
        f"- Précision sans filtre de taille : {pct(score)} ({hits} / {total}).",
        f"- Précision avec filtre de taille (côté d'au moins 8 px et aire d'au moins 0,0004) : {pct(score_kept)} ({hits_kept} / {total_kept}).",
        "",
        "## Bruit de détecteur",
        "",
        "- Chaque boîte d'évaluation est décalée et redimensionnée de 10 à 20 % (graine 42), une seule fois, avec les seuils v2.",
        f"- Précision : {pct(score_noise)} ({hits_noise} / {total_noise}).",
        f"- Orange lu comme rouge sous ce bruit : {matrix_noise['orange']['rouge']}.",
        "",
        *table(matrix_noise),
        "",
    ]
    if orange_v2 > orange_v1:
        lines += [
            "## Compromis",
            "",
            f"Orange lu comme rouge augmente : {orange_v1} en v1, {orange_v2} en v2. "
            "La teinte rouge étendue jusqu'à 20 absorbe des lampes orange.",
            "",
            "Compromis proposé, non appliqué : laisser un intervalle « douteux » entre les deux teintes, "
            "par exemple rouge jusqu'à 10, douteux de 11 à 21, orange à partir de 22. "
            "« douteux » ne doit jamais être classé rouge, ni compter comme une infraction.",
            "",
        ]
    else:
        lines += [
            "## Compromis",
            "",
            f"Orange lu comme rouge n'augmente pas ({orange_v1} en v1, {orange_v2} en v2).",
            "",
        ]
    report = REPORTS / "hsv_eval_v2.md"
    report.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(report)
    print(f"v2 {pct(score)} orange->rouge {orange_v2} (v1 {orange_v1}) bruit {pct(score_noise)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
