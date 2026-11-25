#!/usr/bin/env python3
"""Compare les infractions du pipeline au CSV de vérité.

Une vérité compte comme infraction si feu_rouge_oui_non vaut oui.
Une détection est juste si son temps tombe dans [début - tolérance, fin + tolérance]
de la même vidéo. L'association est une à une.

    python scripts/09_eval_pipeline.py --verite data/test_scenes/infractions_verite.csv --detections events.json --tolerance 1
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _oui(value: str) -> bool:
    return str(value).strip().lower() in {"oui", "yes", "1", "true", "vrai"}


def lire_verite(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    parsed = []
    for row in rows:
        parsed.append(
            {
                "video": row["video"],
                "debut": float(row["temps_debut_s"]),
                "fin": float(row["temps_fin_s"]),
                "vehicule": row.get("vehicule", ""),
                "infraction": _oui(row["feu_rouge_oui_non"]),
                "remarque": row.get("remarque", ""),
            }
        )
    return parsed


def evaluer(detections: list[dict], verite: list[dict], tolerance_s: float) -> dict:
    """detections : video, temps_s. Retourne précision, rappel et faux positifs."""
    truths = [row for row in verite if row["infraction"]]
    used = set()
    matched = 0
    false_positives = []
    for detection in detections:
        hit = None
        for index, truth in enumerate(truths):
            if index in used or truth["video"] != detection["video"]:
                continue
            if truth["debut"] - tolerance_s <= float(detection["temps_s"]) <= truth["fin"] + tolerance_s:
                hit = index
                break
        if hit is None:
            false_positives.append(detection)
        else:
            used.add(hit)
            matched += 1
    precision = matched / len(detections) if detections else 0.0
    recall = matched / len(truths) if truths else 0.0
    return {
        "precision": precision,
        "rappel": recall,
        "vrais_positifs": matched,
        "detections": len(detections),
        "verites": len(truths),
        "faux_positifs": false_positives,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Évalue les infractions contre un CSV.")
    parser.add_argument("--verite", type=Path, required=True)
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=1.0)
    args = parser.parse_args()
    payload = json.loads(args.detections.read_text(encoding="utf-8"))
    result = evaluer(payload, lire_verite(args.verite), args.tolerance)
    print(f"précision {result['precision']:.1%}  rappel {result['rappel']:.1%}")
    print(f"faux positifs : {len(result['faux_positifs'])}")
    for item in result["faux_positifs"]:
        print(f"- {item['video']} à {item['temps_s']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
