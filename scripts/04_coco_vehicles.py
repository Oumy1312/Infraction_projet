#!/usr/bin/env python3
"""Télécharge un extrait COCO 2017 (voiture, bus, camion, moto) et l'exporte en YOLO.

Maximum 6 000 images : 4 800 train et 1 200 validation, graine 42.
Rien n'est mélangé à data/processed/vehicles. Aucun entraînement.

    python scripts/04_coco_vehicles.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEST = PROJECT / "data" / "raw" / "vehicles_coco"
REPORTS = PROJECT / "reports"
CLASSES = ["car", "bus", "truck", "motorcycle"]
SEED = 42
LIMITS = {"train": 4800, "validation": 1200}


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def areas_by_class(root: Path) -> dict[int, list[float]]:
    found = {index: [] for index in range(len(CLASSES))}
    labels = root / "labels"
    if not labels.is_dir():
        labels = root
    for path in labels.rglob("*.txt"):
        if path.name.lower() in {"classes.txt", "dataset.yaml"}:
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                class_id = int(float(parts[0]))
                area = float(parts[3]) * float(parts[4])
            except ValueError:
                continue
            if class_id in found:
                found[class_id].append(area)
    return found


def local_vehicle_areas() -> dict[int, list[float]]:
    names = {"car": 0, "bus": 1, "truck": 2, "motorcycle": 3}
    found = {index: [] for index in range(4)}
    root = PROJECT / "data" / "processed" / "vehicles"
    for path in root.glob("*/labels/*.txt"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                class_id = int(float(parts[0]))
                area = float(parts[3]) * float(parts[4])
            except ValueError:
                continue
            if class_id in found:
                found[class_id].append(area)
    return names, found


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    import fiftyone as fo
    import fiftyone.zoo as foz

    DEST.mkdir(parents=True, exist_ok=True)
    fo.config.dataset_zoo_dir = str(DEST / "_zoo")
    for split, limit in LIMITS.items():
        dataset_name = f"infraction_coco_{split}"
        if fo.dataset_exists(dataset_name):
            fo.delete_dataset(dataset_name)
        dataset = foz.load_zoo_dataset(
            "coco-2017",
            split=split,
            label_types=["detections"],
            classes=CLASSES,
            max_samples=limit,
            shuffle=True,
            seed=SEED,
            dataset_name=dataset_name,
        )
        export_dir = DEST / split
        dataset.export(
            export_dir=str(export_dir),
            dataset_type=fo.types.YOLOv5Dataset,
            label_field="ground_truth",
            classes=CLASSES,
        )
        dataset.delete()
        print(split, "exporté", export_dir)

    coco = {}
    images = {}
    for split in LIMITS:
        coco[split] = areas_by_class(DEST / split)
        image_dir = DEST / split / "images"
        images[split] = sum(1 for path in image_dir.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png"}) if image_dir.is_dir() else 0
    _names, local = local_vehicle_areas()
    lines = [
        "# COCO 2017 filtré, non mélangé",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- FiftyOne, graine {SEED}, maximum {sum(LIMITS.values())} images ({LIMITS['train']} train, {LIMITS['validation']} validation).",
        "- Classes exportées, dans cet ordre : car 0, bus 1, truck 2, motorcycle 3. Même mapping que `data/processed/vehicles`.",
        "- Dossier : `data/raw/vehicles_coco/`. Pas fusionné avec les véhicules actuels. Aucun entraînement.",
        "",
        "## Images",
        "",
        f"- train : {images['train']}",
        f"- validation : {images['validation']}",
        "",
        "## Annotations et aire relative",
        "",
        "Aire = largeur × hauteur, normalisée. La médiane des véhicules actuels est donnée en regard.",
        "",
        "| Classe | COCO train | COCO validation | COCO médiane | Véhicules actuels | Médiane actuelle |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for index, name in enumerate(CLASSES):
        coco_values = coco["train"][index] + coco["validation"][index]
        local_values = local[index]
        lines.append(
            f"| {name} | {len(coco['train'][index])} | {len(coco['validation'][index])} | "
            f"{percentile(coco_values, 0.5):.5f} | {len(local_values)} | {percentile(local_values, 0.5):.5f} |"
        )
    lines.append("")
    lines.append("Détail, aire relative (train + validation pour COCO, les trois sous-ensembles pour les véhicules actuels) :")
    lines.append("")
    for index, name in enumerate(CLASSES):
        values = coco["train"][index] + coco["validation"][index]
        local_values = local[index]
        if not values:
            lines.append(f"- {name} : aucune boîte COCO.")
            continue
        lines.append(
            f"- {name} : COCO n={len(values)}, min={min(values):.5f}, p10={percentile(values, 0.10):.5f}, "
            f"médiane={percentile(values, 0.50):.5f}, p90={percentile(values, 0.90):.5f}. "
            f"Actuel n={len(local_values)}, min={min(local_values):.5f}, p10={percentile(local_values, 0.10):.5f}, "
            f"médiane={percentile(local_values, 0.50):.5f}, p90={percentile(local_values, 0.90):.5f}."
        )
    lines.append("")
    report = REPORTS / "vehicles_coco.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
