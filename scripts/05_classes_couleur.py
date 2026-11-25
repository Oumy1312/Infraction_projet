#!/usr/bin/env python3
"""Compte les 13 classes d'origine des feux et propose un regroupement.

Ne supprime et ne réécrit aucun label.

    python scripts/05_classes_couleur.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw" / "traffic_lights"
REPORTS = PROJECT / "reports"
NAMES = [
    "go 0",
    "go_left",
    "go_right",
    "green",
    "off",
    "off 4",
    "red",
    "stop 2",
    "stop_left",
    "wait_on",
    "warn 3",
    "warn_left",
    "yellow",
]
# Proposition, non appliquée. « orange » est le feu ambre.
PROPOSAL = {
    0: ("autre", "Le nom « go » est un état, pas une couleur. Sur les fichiers à 6 chiffres, la classe 0 n'a jamais été une couleur."),
    1: ("autre", "Flèche vers la gauche."),
    2: ("autre", "Flèche vers la droite."),
    3: ("vert", "Le nom est la couleur verte."),
    4: ("autre", "Feu éteint."),
    5: ("autre", "Feu éteint. Le « 4 » est un ancien numéro collé au nom."),
    6: ("rouge", "Le nom est la couleur rouge."),
    7: ("autre", "État « stop », pas une couleur annotée. Ne pas le ranger en rouge sans revoir les images."),
    8: ("autre", "Flèche d'arrêt."),
    9: ("autre", "État d'attente. Le nom ne dit pas orange."),
    10: ("autre", "Avertissement. Souvent proche de l'ambre, mais le nom n'est pas « yellow »."),
    11: ("autre", "Flèche d'avertissement."),
    12: ("orange", "« yellow » est le feu ambre, appelé orange ici."),
}


def six_digit(name: str) -> bool:
    return re.match(r"(\d{6})(?:_jpg)?\.rf\.", name, re.IGNORECASE) is not None or re.match(
        r"(\d{6})\.", name
    ) is not None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    boxes: Counter[int] = Counter()
    files_with: Counter[int] = Counter()
    class0_six = 0
    class0_other = 0
    files_class0_only_six = 0
    labels = [path for path in RAW.rglob("*.txt") if "labels" in path.parts and path.name.lower() != "classes.txt"]
    for label in labels:
        ids = []
        for line in label.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                class_id = int(float(parts[0]))
            except ValueError:
                continue
            ids.append(class_id)
            boxes[class_id] += 1
        for class_id in set(ids):
            files_with[class_id] += 1
        if ids and set(ids) == {0} and six_digit(label.name):
            files_class0_only_six += 1
            class0_six += len(ids)
        else:
            class0_other += sum(1 for class_id in ids if class_id == 0)

    lines = [
        "# Classes de couleur des feux",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Source : `data/raw/traffic_lights`. Aucun label n'a été supprimé ni réécrit.",
        "- La copie `data/interim/feux_couleur/` reste en place pour l'évaluation HSV.",
        "- Le détecteur traité reste à une seule classe `traffic_light`.",
        "",
        "## Treize classes d'origine",
        "",
        "| Id | Nom d'origine | Boîtes | Fichiers | Proposition | Pourquoi |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for class_id, name in enumerate(NAMES):
        target, reason = PROPOSAL[class_id]
        lines.append(
            f"| {class_id} | {name} | {boxes[class_id]} | {files_with[class_id]} | {target} | {reason} |"
        )
    grouped: Counter[str] = Counter()
    for class_id, name in enumerate(NAMES):
        grouped[PROPOSAL[class_id][0]] += boxes[class_id]
    lines += [
        "",
        "## Totaux de la proposition",
        "",
        "Ces totaux comptent toutes les boîtes, y compris la classe 0 des fichiers à 6 chiffres, qui n'est pas une couleur.",
        "",
        "| Groupe | Boîtes |",
        "| --- | --- |",
    ]
    for name in ("rouge", "orange", "vert", "autre"):
        lines.append(f"| {name} | {grouped[name]} |")
    lines += [
        "",
        "## Classe 0 à part",
        "",
        f"- Fichiers à 6 chiffres qui ne contiennent que la classe 0 : {files_class0_only_six}. Boîtes : {class0_six}.",
        f"- Autres boîtes de classe 0 (nom d'origine « go 0 », dans les fichiers S2TLD) : {class0_other}.",
        "- Les 1 211 fichiers à 6 chiffres, s'ils sont dans ce compte, n'ont jamais eu de rouge, d'orange ou de vert. Les laisser en « autre ».",
        "",
        "Seules trois classes portent un nom de couleur : `red` → rouge, `yellow` → orange, `green` → vert. Le reste est un état, une flèche ou un feu éteint. Les ranger dans une couleur serait une supposition.",
        "",
    ]
    report = REPORTS / "classes_couleur.md"
    report.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(report)
    print("boîtes", dict(boxes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
