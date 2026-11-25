#!/usr/bin/env python3
"""Planche de 40 plaques réelles. Le texte n'est pas lu.

    python scripts/11_planche_plaques.py
"""

from __future__ import annotations

import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.plaques_reelles import ecrire_planche, lister, nettete, recadrer  # noqa: E402

SEED = 42
QUOTAS = (
    ("moped", 5),
    ("marokko", 4),
    ("maroc", 3),
    ("IMG", 6),
    ("id_numerique", 5),
    ("PHOTO", 3),
    ("VID", 3),
    ("y", 2),
    ("serie_T", 2),
    ("telechargement", 2),
    ("auto-ecole", 2),
    ("unnamed", 2),
    ("autre", 1),
)
MIN_WIDTH = 100
MIN_HEIGHT = 32
MIN_SHARP = 80.0


def choisir(rows: list[dict]) -> tuple[list[dict], str]:
    note = f"largeur ≥ {MIN_WIDTH} px, hauteur ≥ {MIN_HEIGHT} px, variance du Laplacien ≥ {MIN_SHARP:.0f}"
    readable = [
        row
        for row in rows
        if row["crop"].shape[1] >= MIN_WIDTH and row["crop"].shape[0] >= MIN_HEIGHT and row["sharp"] >= MIN_SHARP
    ]
    pool = readable
    if len(pool) < 40:
        pool = [row for row in rows if row["crop"].shape[1] >= 70 and row["crop"].shape[0] >= 24]
        note = "seuil assoupli, moins de 40 images au seuil initial : largeur ≥ 70 px et hauteur ≥ 24 px"
    rng = random.Random(SEED)
    by_source: dict[str, list[dict]] = {}
    for row in pool:
        by_source.setdefault(row["source"], []).append(row)
    for group in by_source.values():
        rng.shuffle(group)
        group.sort(key=lambda item: item["sharp"], reverse=True)
    chosen = []
    used = set()
    for source, quota in QUOTAS:
        for row in by_source.get(source, [])[:quota]:
            if len(chosen) >= 40:
                break
            chosen.append(row)
            used.add(id(row))
    if len(chosen) < 40:
        rest = [row for row in pool if id(row) not in used]
        rest.sort(key=lambda item: item["sharp"], reverse=True)
        chosen.extend(rest[: 40 - len(chosen)])
    return chosen[:40], note


def main() -> None:
    measured = []
    for item in lister():
        crop = recadrer(item)
        if crop is None:
            continue
        measured.append({**item, "crop": crop, "sharp": nettete(crop)})
    chosen, note = choisir(measured)
    cases = [{"crop": row["crop"], "caption": row["source"]} for row in chosen]
    destination = PROJECT / "reports" / "planche_plaques_reelles.jpg"
    ecrire_planche(cases, destination, "Plaques réelles. Légende = source du fichier, pas une lecture.", columns=5)
    counts = Counter(row["source"] for row in chosen)
    lines = [
        "# Planche de plaques réelles",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Aucun caractère n'a été lu. Le format n'est pas déduit de ces images.",
        f"- Critère de netteté retenu : {note}.",
        "- La source est le préfixe du nom de fichier (IMG, moped, marokko, id numérique, PHOTO, VID, etc.).",
        "- `moped` est la seule famille dont le nom indique un deux-roues. Les autres familles ne sont pas classées voiture ou moto.",
        f"- Images recadrées : {len(chosen)}. Fichier : `reports/planche_plaques_reelles.jpg`.",
        "",
        "| Source | Images sur la planche |",
        "| --- | --- |",
    ]
    for source, count in sorted(counts.items()):
        lines.append(f"| {source} | {count} |")
    lines.append("")
    (PROJECT / "reports" / "planche_plaques.md").write_text("\n".join(lines), encoding="utf-8")
    print(destination)
    print(dict(counts))


if __name__ == "__main__":
    main()
