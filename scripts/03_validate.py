#!/usr/bin/env python3
"""Contrôle data/interim et les images de data/raw.

Corrige dans data/interim les boîtes qui dépassent légèrement de l'image
(coordonnées dans [-0,02 ; 1,02]) en les ramenant à [0, 1].
Le reste est listé, pas modifié. data/raw n'est pas modifié.

    python scripts/03_validate.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError


def load(name: str, filename: str):
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Import impossible : {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REORG = load("reorg_valid", "01_reorganize.py")
PROJECT = REORG.PROJECT_ROOT
RAW = PROJECT / "data" / "raw"
INTERIM = PROJECT / "data" / "interim"
REPORTS = PROJECT / "reports"
DATASETS = ("vehicles", "traffic_lights", "plates_detection", "_incertains")
SLIGHT = 0.02
SMALL_AREA = 0.001


def pair_key(path: Path, root: Path, folder_name: str) -> tuple[str, str] | None:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return None
    if folder_name not in parts:
        return None
    index = parts.index(folder_name)
    head = "/".join(parts[:index])
    tail = Path(*parts[index + 1:]).with_suffix("").as_posix().casefold()
    return head, tail


def build_indexes() -> tuple[dict[tuple[str, str], Path], dict[str, list[Path]]]:
    images: dict[tuple[str, str], Path] = {}
    by_dataset: dict[str, list[Path]] = defaultdict(list)
    for name in DATASETS:
        root = RAW / name
        if not root.is_dir():
            continue
        for path in REORG.walk_files(root):
            if not REORG.is_image(path):
                continue
            key = pair_key(path, RAW, "images")
            if key is None:
                continue
            images[key] = path
            by_dataset[name].append(path)
    return images, by_dataset


def parse_box(line: str) -> tuple[int, float, float, float, float] | None:
    parts = line.split()
    if len(parts) != 5:
        return None
    try:
        class_id = int(float(parts[0]))
        cx, cy, width, height = (float(piece) for piece in parts[1:])
    except ValueError:
        return None
    return class_id, cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2


def to_line(class_id: int, x1: float, y1: float, x2: float, y2: float) -> str | None:
    width = x2 - x1
    height = y2 - y1
    if width <= 1e-8 or height <= 1e-8:
        return None
    return f"{class_id} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {width:.6f} {height:.6f}"


def file_hash(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    labels = [
        path for name in DATASETS for path in REORG.walk_files(INTERIM / name)
        if REORG.is_label_file(path)
    ] if INTERIM.is_dir() else []
    image_index, images_by_dataset = build_indexes()
    print(f"Labels : {len(labels)}  images indexées : {len(image_index)}", flush=True)
    clipped = 0
    dropped_zero = 0
    severe: list[str] = []
    empty: list[str] = []
    unreadable: list[str] = []
    label_without_image: list[str] = []
    bad_line: list[str] = []
    class_counts: dict[str, Counter[int]] = defaultdict(Counter)
    areas: dict[str, list[float]] = defaultdict(list)
    small_flags: list[str] = []
    images_seen: dict[str, list[Path]] = defaultdict(list)
    label_stems: dict[str, set[str]] = defaultdict(set)

    for label in labels:
        dataset = label.relative_to(INTERIM).parts[0]
        key = pair_key(label, INTERIM, "labels")
        image = image_index.get(key) if key is not None else None
        if image is None:
            label_without_image.append(label.relative_to(PROJECT).as_posix())
        else:
            images_seen[dataset].append(image)
            label_stems[dataset].add(key[1] if key else image.stem.casefold())
            try:
                with Image.open(image) as opened:
                    opened.verify()
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                unreadable.append(image.relative_to(PROJECT).as_posix())
        raw = label.read_text(encoding="utf-8", errors="replace")
        rewritten: list[str] = []
        changed = False
        kept = 0
        for line in raw.splitlines():
            if not line.strip():
                continue
            parsed = parse_box(line)
            if parsed is None:
                bad_line.append(f"{label.relative_to(PROJECT).as_posix()} : {line[:80]}")
                continue
            class_id, x1, y1, x2, y2 = parsed
            coords = (x1, y1, x2, y2)
            outside = [value for value in coords if value < 0 or value > 1]
            if outside and any(value < -SLIGHT or value > 1 + SLIGHT for value in coords):
                severe.append(f"{label.relative_to(PROJECT).as_posix()} {line}")
                rewritten.append(line.strip())
                kept += 1
                class_counts[dataset][class_id] += 1
                continue
            if outside:
                x1, x2 = sorted((min(1.0, max(0.0, x1)), min(1.0, max(0.0, x2))))
                y1, y2 = sorted((min(1.0, max(0.0, y1)), min(1.0, max(0.0, y2))))
                changed = True
                clipped += 1
            text = to_line(class_id, x1, y1, x2, y2)
            if text is None:
                dropped_zero += 1
                changed = True
                small_flags.append(f"taille nulle {label.relative_to(PROJECT).as_posix()} classe {class_id}")
                continue
            rewritten.append(text)
            kept += 1
            class_counts[dataset][class_id] += 1
            width = x2 - x1
            height = y2 - y1
            area = width * height
            areas[dataset].append(area)
            if dataset == "vehicles" and class_id == 4 and area < SMALL_AREA:
                small_flags.append(f"moto très petite aire={area:.5f} {label.relative_to(PROJECT).as_posix()}")
            if dataset == "plates_detection" and area < SMALL_AREA:
                small_flags.append(f"plaque très petite aire={area:.5f} {label.relative_to(PROJECT).as_posix()}")
        if kept == 0:
            empty.append(label.relative_to(PROJECT).as_posix())
        if changed:
            body = "\n".join(rewritten) + ("\n" if rewritten else "")
            label.write_text(body, encoding="utf-8", newline="\n")

    image_without_label: list[str] = []
    hashes: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    print("Hash des images…", flush=True)
    for name in DATASETS:
        for path in images_by_dataset.get(name, []):
            key = pair_key(path, RAW, "images")
            if key is None or key[1] not in label_stems[name]:
                image_without_label.append(path.relative_to(PROJECT).as_posix())
            digest = file_hash(path)
            hashes[name][digest].append(path.relative_to(PROJECT).as_posix())

    duplicate_groups = {
        name: [paths for paths in grouped.values() if len(paths) > 1]
        for name, grouped in hashes.items()
    }

    lines = [
        "# Qualité des données",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Lecture de `data/interim` pour les labels et de `data/raw` pour les images.",
        f"- Correction automatique : une boîte dont une coordonnée sort de [0, 1] mais reste dans [-{SLIGHT:.2f}, {1 + SLIGHT:.2f}] est ramenée dans [0, 1]. Une boîte de taille nulle est retirée.",
        "- Au-delà de cette tolérance, la boîte est listée et laissée telle quelle.",
        "",
        f"- Labels lus : {len(labels)}.",
        f"- Boîtes rognées : {clipped}.",
        f"- Boîtes de taille nulle retirées : {dropped_zero}.",
        f"- Boîtes hors tolérance, non corrigées : {len(severe)}.",
        f"- Labels vides après contrôle : {len(empty)}.",
        f"- Images illisibles : {len(unreadable)}.",
        f"- Labels sans image : {len(label_without_image)}.",
        f"- Images sans label : {len(image_without_label)}.",
        f"- Lignes de label illisibles : {len(bad_line)}.",
        "",
        "## Annotations par classe",
        "",
        "Identifiants encore ceux des fichiers d'origine. Le mapping véhicules est appliqué plus tard, au découpage.",
        "",
    ]
    for name in DATASETS:
        counts = class_counts.get(name)
        if not counts:
            lines.append(f"- {name} : aucune annotation.")
            continue
        detail = ", ".join(f"{class_id} → {counts[class_id]}" for class_id in sorted(counts))
        lines.append(f"- {name} : {sum(counts.values())} boîtes ({detail}).")
    lines += ["", "## Taille des boîtes (aire relative)", ""]
    for name in DATASETS:
        values = areas.get(name, [])
        if not values:
            continue
        lines.append(
            f"- {name} : n={len(values)}, min={min(values):.5f}, p10={percentile(values, 0.10):.5f}, "
            f"médiane={percentile(values, 0.50):.5f}, p90={percentile(values, 0.90):.5f}."
        )
    moto_small = [item for item in small_flags if item.startswith("moto")]
    plate_small = [item for item in small_flags if item.startswith("plaque")]
    lines += [
        "",
        f"Seuil « très petite » : aire relative < {SMALL_AREA}. Ces boîtes sont conservées.",
        "",
        f"- Motos (classe 4 d'origine, motorbike) sous le seuil : {len(moto_small)}.",
        f"- Plaques sous le seuil : {len(plate_small)}.",
        "",
        "## Doublons exacts (MD5)",
        "",
    ]
    any_dup = False
    for name in DATASETS:
        groups = duplicate_groups.get(name, [])
        if not groups:
            lines.append(f"- {name} : aucun doublon exact.")
            continue
        any_dup = True
        lines.append(f"- {name} : {len(groups)} groupe(s) de fichiers identiques.")
        for group in groups[:15]:
            lines.append(f"  - {group[0]} et {len(group) - 1} autre(s)")
    if not any_dup:
        lines.append("- Aucun fichier image identique à l'octet près dans un même jeu.")
    lines += ["", "## Listes", ""]

    def dump(title: str, items: list[str], limit: int = 30) -> None:
        lines.append(f"### {title}")
        lines.append("")
        if not items:
            lines.append("- Aucun.")
        else:
            for item in items[:limit]:
                lines.append(f"- `{item}`")
            if len(items) > limit:
                lines.append(f"- … {len(items) - limit} de plus.")
        lines.append("")

    dump("Boîtes hors tolérance", severe)
    dump("Labels vides", empty)
    dump("Images illisibles", unreadable)
    dump("Labels sans image", label_without_image)
    dump("Images sans label", image_without_label)
    dump("Lignes illisibles", bad_line)
    dump("Très petites motos et plaques (30 premières)", small_flags)
    expected_empty = [item for item in empty if "traffic_lights" in item]
    if len(expected_empty) != 3:
        lines.append(f"Résultat surprenant : {len(expected_empty)} labels vides dans traffic_lights, 3 images négatives étaient attendues.")
        lines.append("")
    report = REPORTS / "qualite_donnees.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Labels : {len(labels)}")
    print(f"Rognées : {clipped}  nulles : {dropped_zero}  hors tolérance : {len(severe)}")
    print(f"Vides : {len(empty)}  illisibles : {len(unreadable)}")
    print(f"Sans image : {len(label_without_image)}  sans label : {len(image_without_label)}")
    print(f"Motos petites : {len(moto_small)}  plaques petites : {len(plate_small)}")
    print(f"Rapport : {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
