#!/usr/bin/env python3
"""Mapping des classes véhicules.

Par défaut : car, bus, truck et motorbike sont gardés.
van et threewheel sont exclus du jeu d'entraînement et copiés dans
data/raw/vehicles_exclus, sans être supprimés de data/raw/vehicles.

    python scripts/03_classes.py
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml


def load(name: str, filename: str):
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Import impossible : {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REORG = load("reorg_classes", "01_reorganize.py")
PROJECT = REORG.PROJECT_ROOT
RAW = PROJECT / "data" / "raw" / "vehicles"
EXCLUS = PROJECT / "data" / "raw" / "vehicles_exclus"
REPORTS = PROJECT / "reports"
CONFIGS = PROJECT / "configs"

SOURCE_NAMES = ["car", "threewheel", "bus", "truck", "motorbike", "van"]
KEEP = {0: 0, 2: 1, 3: 2, 4: 3}
KEEP_NAMES = ["car", "bus", "truck", "motorcycle"]
EXCLUDED = {1: "threewheel", 5: "van"}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    classes_path = RAW / "classes.txt"
    declared = []
    if classes_path.is_file():
        declared = [line.strip() for line in classes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    counts: Counter[int] = Counter()
    files_with: dict[int, set[Path]] = {1: set(), 5: set(), -1: set()}
    other_ids: Counter[int] = Counter()
    labels = [path for path in REORG.walk_files(RAW) if REORG.is_label_file(path) and "labels" in path.parts]
    for label in labels:
        for line in label.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                class_id = int(float(parts[0]))
            except ValueError:
                continue
            counts[class_id] += 1
            if class_id in EXCLUDED:
                files_with[class_id].add(label)
            elif class_id not in KEEP:
                other_ids[class_id] += 1
                files_with[-1].add(label)

    copied: Counter[str] = Counter()
    for class_id, folder_name in EXCLUDED.items():
        for label in sorted(files_with[class_id]):
            image = None
            images_dir = label.parent.parent / "images"
            if images_dir.is_dir():
                hits = [path for path in images_dir.iterdir() if path.stem == label.stem and path.suffix.lower() in REORG.IMAGE_EXTS]
                image = hits[0] if hits else None
            kept_lines = []
            for line in label.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.split()
                if not parts:
                    continue
                try:
                    if int(float(parts[0])) == class_id:
                        kept_lines.append(line.strip())
                except ValueError:
                    continue
            split_name = label.parent.parent.name
            dest_label = EXCLUS / folder_name / "labels" / f"{split_name}__{label.name}"
            dest_label.parent.mkdir(parents=True, exist_ok=True)
            if not dest_label.exists():
                dest_label.write_text("\n".join(kept_lines) + "\n", encoding="utf-8", newline="\n")
                copied[folder_name] += 1
            if image is not None:
                dest_image = EXCLUS / folder_name / "images" / f"{split_name}__{image.name}"
                dest_image.parent.mkdir(parents=True, exist_ok=True)
                if not dest_image.exists():
                    shutil.copy2(image, dest_image)

    mapping = {
        "source_names": SOURCE_NAMES,
        "declared_classes_txt": declared,
        "keep": {"car": 0, "bus": 1, "truck": 2, "motorcycle": 3},
        "source_to_target": {0: 0, 2: 1, 3: 2, 4: 3},
        "excluded": {"threewheel": 1, "van": 5},
        "target_names": KEEP_NAMES,
    }
    CONFIGS.mkdir(parents=True, exist_ok=True)
    config_path = CONFIGS / "classes_vehicles.yaml"
    config_path.write_text(yaml.safe_dump(mapping, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")

    surprise = declared != SOURCE_NAMES
    lines = [
        "# Mapping des classes véhicules",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Rien n'est supprimé de `data/raw/vehicles`.",
        "- Choix appliqué par défaut : `van` exclu, `threewheel` exclu.",
        "- Les images qui contiennent ces classes sont copiées dans `data/raw/vehicles_exclus/<classe>/` avec un label réduit à ces boîtes.",
        "- Une image qui contient aussi une voiture, un bus, un camion ou une moto reste dans le jeu d'entraînement, sans les boîtes exclues.",
        "",
        "## classes.txt",
        "",
        "```",
        *declared,
        "```",
        "",
        f"- Correspond au jeu attendu (car, threewheel, bus, truck, motorbike, van) : {'non, à vérifier' if surprise else 'oui'}.",
        "",
        "## Effectifs d'origine",
        "",
        "| Identifiant | Nom d'origine | Boîtes | Décision | Identifiant cible |",
        "| --- | --- | --- | --- | --- |",
    ]
    decisions = {
        0: ("car", "gardé", "0 car"),
        1: ("threewheel", "exclu", "—"),
        2: ("bus", "gardé", "1 bus"),
        3: ("truck", "gardé", "2 truck"),
        4: ("motorbike", "gardé", "3 motorcycle"),
        5: ("van", "exclu", "—"),
    }
    for class_id in range(6):
        name, decision, target = decisions[class_id]
        lines.append(f"| {class_id} | {name} | {counts[class_id]} | {decision} | {target} |")
    for class_id, count in sorted(other_ids.items()):
        lines.append(f"| {class_id} | autre | {count} | exclu | — |")
    lines += [
        "",
        "## Pourquoi ce défaut",
        "",
        "Les classes cibles demandées sont car, bus, truck et motorcycle. `motorbike` est renommé `motorcycle` pour coller à ce vocabulaire. `van` et `threewheel` n'ont pas de classe cible : les fusionner dans car ou truck changerait le sens des boîtes. Ils sont donc mis à part.",
        "",
        "Autre choix possible, non appliqué : fusionner `van` dans `truck` ou dans `car`. Le dire explicitement pour changer le défaut.",
        "",
        "## Copies d'exclusion",
        "",
        f"- Fichiers label threewheel copiés : {len(files_with[1])}.",
        f"- Fichiers label van copiés : {len(files_with[5])}.",
        f"- Nouveaux labels écrits : {dict(copied)}.",
        "",
        "Les feux S2TLD et les feux de classe 0 seule seront, au découpage, une seule classe `traffic_light`. Le détecteur localise le feu ; la couleur rouge, orange ou vert est décidée ensuite par HSV, pas par ces identifiants. Les labels d'origine dans `data/raw` gardent leurs classes.",
        "",
        "Les plaques restent la classe 0, nommée `plate`, dans leur propre `data.yaml`.",
        "",
        f"Fichier machine : `{config_path.relative_to(PROJECT).as_posix()}`.",
        "",
    ]
    if other_ids:
        lines.append(f"Résultat surprenant : {sum(other_ids.values())} boîtes ont un identifiant hors de 0–5. Elles sont exclues et signalées ici.")
        lines.append("")
    report = REPORTS / "classes_mapping.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"classes.txt : {declared}")
    print(f"Comptes : {dict(counts)}")
    print(f"threewheel fichiers : {len(files_with[1])}  van fichiers : {len(files_with[5])}")
    print(f"Rapport : {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
