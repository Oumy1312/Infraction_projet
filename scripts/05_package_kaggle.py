#!/usr/bin/env python3
"""Zippe data/processed pour un dataset Kaggle.

Le zip contient vehicles, traffic_lights et plates_detection,
avec leurs data.yaml. Pas de poids, pas de quarantine.

    python scripts/05_package_kaggle.py
"""

from __future__ import annotations

import sys
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "data" / "processed"
SCENES = PROJECT / "data" / "test_scenes"
DEST = PROJECT / "data" / "kaggle" / "infraction_processed.zip"
REPORTS = PROJECT / "reports"
# Plafond Kaggle d'un dataset. Au-delà de 8 Go l'envoi devient pénible.
COMFORT_BYTES = 8 * (1024 ** 3)
LIMIT_BYTES = 100 * (1024 ** 3)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    if not SOURCE.is_dir():
        raise SystemExit(f"Dossier absent : {SOURCE}")
    files = [path for path in SOURCE.rglob("*") if path.is_file()]
    scenes = [path for path in SCENES.rglob("*") if path.is_file()] if SCENES.is_dir() else []
    raw_size = sum(path.stat().st_size for path in files + scenes)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists():
        DEST.unlink()
    with zipfile.ZipFile(DEST, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            archive.write(path, path.relative_to(SOURCE).as_posix())
        for path in scenes:
            archive.write(path, ("test_scenes" / path.relative_to(SCENES)).as_posix())
    zip_size = DEST.stat().st_size
    if zip_size > LIMIT_BYTES:
        verdict = "trop gros pour un dataset Kaggle (plafond 100 Go)."
    elif zip_size > COMFORT_BYTES:
        verdict = "en dessous du plafond 100 Go, mais lourd à envoyer (plus de 8 Go)."
    else:
        verdict = "Taille acceptable pour un upload Kaggle. Le plafond d'un dataset est 100 Go."
    lines = [
        "# Paquet Kaggle",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Fichiers : {len(files) + len(scenes)}",
        f"- Taille des fichiers : {raw_size / (1024 ** 2):.1f} Mo",
        f"- Taille du zip : {zip_size / (1024 ** 2):.1f} Mo ({zip_size / (1024 ** 3):.2f} Go)",
        f"- Chemin : `{DEST.relative_to(PROJECT).as_posix()}`",
        f"- {verdict}",
        "",
        "La racine du zip est le contenu de `data/processed`, plus `test_scenes/` (images de Marrakech, vide tant qu'elles ne sont pas déposées).",
        "Aucun poids n'est inclus.",
        "",
    ]
    report = REPORTS / "kaggle_paquet.md"
    report.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
