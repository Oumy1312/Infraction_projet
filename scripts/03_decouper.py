#!/usr/bin/env python3
"""Découpe train/val/test 70/20/10, graine 42, sans fuite.

Les doublons exacts et les quasi-doublons (dHash, distance ≤ 4) restent
dans le même sous-ensemble. Images et labels vont dans data/processed.
Trois data.yaml utilisent des chemins relatifs.

    python scripts/03_decouper.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import random
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError
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


REORG = load("reorg_split", "01_reorganize.py")
PROJECT = REORG.PROJECT_ROOT
RAW = PROJECT / "data" / "raw"
INTERIM = PROJECT / "data" / "interim"
PROCESSED = PROJECT / "data" / "processed"
REPORTS = PROJECT / "reports"
SEED = 42
FRACTIONS = (("train", 0.70), ("val", 0.20), ("test", 0.10))
HAMMING_MAX = 4
SMALL_AREA = 0.001
VEHICLE_MAP = {0: 0, 2: 1, 3: 2, 4: 3}


def file_hash(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dhash(path: Path) -> int | None:
    try:
        with Image.open(path) as image:
            raw = image.convert("L").resize((9, 8), Image.Resampling.BILINEAR).tobytes()
            pixels = list(raw)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a


def collect(dataset: str) -> list[tuple[Path, Path]]:
    pairs = []
    root = INTERIM / dataset
    raw_root = RAW / dataset
    if not root.is_dir():
        return pairs
    images: dict[tuple[str, str], Path] = {}
    if raw_root.is_dir():
        for path in REORG.walk_files(raw_root):
            key = pair_key(path, RAW, "images")
            if key is not None and key[0].startswith(dataset):
                images[key] = path
    for label in REORG.walk_files(root):
        if not (REORG.is_label_file(label) and "labels" in label.parts):
            continue
        key = pair_key(label, INTERIM, "labels")
        image = images.get(key) if key is not None else None
        if image is not None:
            pairs.append((image, label))
    return pairs


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


def assign_splits(pairs: list[tuple[Path, Path]]) -> tuple[dict[Path, str], int]:
    hashes = [file_hash(image) for image, _label in pairs]
    fingerprints = [dhash(image) for image, _label in pairs]
    union = UnionFind(len(pairs))
    by_hash: dict[str, int] = {}
    for index, digest in enumerate(hashes):
        if digest in by_hash:
            union.union(index, by_hash[digest])
        else:
            by_hash[digest] = index
    linked = 0
    for left in range(len(pairs)):
        left_bits = fingerprints[left]
        if left_bits is None:
            continue
        for right in range(left + 1, len(pairs)):
            right_bits = fingerprints[right]
            if right_bits is None:
                continue
            if (left_bits ^ right_bits).bit_count() <= HAMMING_MAX:
                union.union(left, right)
                linked += 1
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(pairs)):
        groups[union.find(index)].append(index)
    order = sorted(groups.values(), key=lambda group: (-len(group), pairs[group[0]][0].name.lower()))
    picker = random.Random(SEED)
    picker.shuffle(order)
    order.sort(key=lambda group: -len(group))
    total = len(pairs)
    counts = {name: 0 for name, _fraction in FRACTIONS}
    assignment: dict[Path, str] = {}
    for group in order:
        choice = max(counts, key=lambda name: next(fraction for split, fraction in FRACTIONS if split == name) * total - counts[name])
        for index in group:
            assignment[pairs[index][0]] = choice
        counts[choice] += len(group)
    multi = sum(1 for group in groups.values() if len(group) > 1)
    return assignment, multi


def map_lines(dataset: str, label: Path) -> tuple[list[str], int]:
    kept: list[str] = []
    dropped = 0
    for line in label.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(float(parts[0]))
        except ValueError:
            continue
        rest = " ".join(f"{float(piece):.6f}" for piece in parts[1:])
        if dataset == "vehicles":
            if class_id not in VEHICLE_MAP:
                dropped += 1
                continue
            kept.append(f"{VEHICLE_MAP[class_id]} {rest}")
        elif dataset == "traffic_lights":
            kept.append(f"0 {rest}")
        else:
            if class_id != 0:
                dropped += 1
                continue
            kept.append(f"0 {rest}")
    return kept, dropped


def unique_name(path: Path, stems: Counter[str]) -> str:
    if stems[path.stem.casefold()] > 1:
        return f"{path.parent.parent.name}__{path.name}"
    return path.name


def write_yaml(root: Path, names: list[str]) -> None:
    payload = {
        "path": ".",
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "names": {index: name for index, name in enumerate(names)},
    }
    (root / "data.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")


def class_counts(root: Path) -> Counter[tuple[str, int]]:
    counts: Counter[tuple[str, int]] = Counter()
    for split, _fraction in FRACTIONS:
        folder = root / split / "labels"
        if not folder.is_dir():
            continue
        for label in folder.glob("*.txt"):
            for line in label.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                try:
                    counts[(split, int(float(parts[0])))] += 1
                except ValueError:
                    continue
    return counts


def small_boxes(root: Path, class_id: int | None) -> int:
    found = 0
    for label in root.glob("*/labels/*.txt"):
        for line in label.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                current = int(float(parts[0]))
                width = float(parts[3])
                height = float(parts[4])
            except ValueError:
                continue
            if class_id is not None and current != class_id:
                continue
            if width * height < SMALL_AREA:
                found += 1
    return found


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    tasks = {
        "vehicles": ["car", "bus", "truck", "motorcycle"],
        "traffic_lights": ["traffic_light"],
        "plates_detection": ["plate"],
    }
    summary: list[str] = [
        "# Découpage train / val / test",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Graine : {SEED}. Parts visées : 70 % / 20 % / 10 %.",
        f"- Fuite : même MD5, ou dHash à distance ≤ {HAMMING_MAX}, restent ensemble.",
        "- Le découpage d'origine de `vehicle dataset` n'est pas repris.",
        "- Véhicules : van et threewheel retirés des labels. Feux : toutes les classes d'origine deviennent `traffic_light`. Plaques : classe `plate`.",
        "",
    ]
    for dataset, names in tasks.items():
        pairs = collect(dataset)
        print(f"{dataset} : {len(pairs)} paires, regroupement des quasi-doublons…", flush=True)
        stems = Counter(image.stem.casefold() for image, _label in pairs)
        assignment, multi = assign_splits(pairs)
        dropped_boxes = 0
        skipped_only_excluded = 0
        split_counts: Counter[str] = Counter()
        for image, label in pairs:
            lines, dropped = map_lines(dataset, label)
            dropped_boxes += dropped
            if not lines and dataset != "traffic_lights":
                skipped_only_excluded += 1
                continue
            split = assignment[image]
            name = unique_name(image, stems)
            dest_image = PROCESSED / dataset / split / "images" / name
            dest_label = PROCESSED / dataset / split / "labels" / (Path(name).stem + ".txt")
            dest_image.parent.mkdir(parents=True, exist_ok=True)
            dest_label.parent.mkdir(parents=True, exist_ok=True)
            if not dest_image.exists():
                shutil.copy2(image, dest_image)
            dest_label.write_text(("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8", newline="\n")
            split_counts[split] += 1
        write_yaml(PROCESSED / dataset, names)
        total = sum(split_counts.values())
        summary.append(f"## {dataset}")
        summary.append("")
        summary.append(f"- Images retenues : {total}. Groupes de quasi-doublons : {multi}.")
        summary.append(f"- Boîtes retirées par le mapping : {dropped_boxes}.")
        if dataset == "vehicles":
            summary.append(f"- Images composées seulement de classes exclues, hors du jeu : {skipped_only_excluded}.")
        for split, _fraction in FRACTIONS:
            count = split_counts[split]
            share = 0 if total == 0 else 100 * count / total
            summary.append(f"- {split} : {count} images ({share:.1f} %).")
        counts = class_counts(PROCESSED / dataset)
        summary.append("- Annotations :")
        for index, name in enumerate(names):
            per_split = ", ".join(f"{split} {counts[(split, index)]}" for split, _fraction in FRACTIONS)
            summary.append(f"  - {name} : {per_split}.")
            if sum(counts[(split, index)] for split, _fraction in FRACTIONS) == 0:
                summary.append(f"  - Résultat surprenant : la classe {name} est vide.")
        if dataset == "vehicles":
            summary.append(f"- Motos d'aire < {SMALL_AREA} : {small_boxes(PROCESSED / dataset, 3)}.")
        if dataset == "plates_detection":
            summary.append(f"- Plaques d'aire < {SMALL_AREA} : {small_boxes(PROCESSED / dataset, 0)}.")
        if dataset == "traffic_lights":
        empty = sum(1 for path in (PROCESSED / dataset).glob("*/labels/*.txt") if not path.read_text(encoding="utf-8").strip())
            summary.append(f"- Labels vides (images négatives) : {empty}.")
        summary.append("")
        print(f"{dataset} : {dict(split_counts)} exclus_seuls={skipped_only_excluded} groupes={multi}")
    report = REPORTS / "decoupage.md"
    report.write_text("\n".join(summary) + "\n", encoding="utf-8", newline="\n")
    print(f"Rapport : {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
