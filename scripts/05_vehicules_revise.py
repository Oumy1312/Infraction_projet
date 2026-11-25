#!/usr/bin/env python3
"""Révision des véhicules, sans toucher aux feux ni aux plaques.

- van (classe 5) devient car (classe 0) dans les labels.
- Les images qui ne contiennent que des vans reviennent dans le jeu.
- Toute image qui contient un threewheel (classe 1) sort du jeu.
  Ses autres boîtes ne sont pas gardées. La copie dans vehicles_exclus reste.
- Nouveau train/val/test 70/20/10, graine 42. Les pHash à distance <= 5
  et les MD5 identiques restent dans le même sous-ensemble.

    python scripts/05_vehicules_revise.py
"""

from __future__ import annotations

import hashlib
import random
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import imagehash
import yaml
from PIL import Image, UnidentifiedImageError
from tqdm import tqdm

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw" / "vehicles"
INTERIM = PROJECT / "data" / "interim" / "vehicles"
EXCLUS = PROJECT / "data" / "raw" / "vehicles_exclus"
PROCESSED = PROJECT / "data" / "processed" / "vehicles"
REPORTS = PROJECT / "reports"
CONFIGS = PROJECT / "configs"
SEED = 42
HAMMING_MAX = 5
FRACTIONS = (("train", 0.70), ("val", 0.20), ("test", 0.10))
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
NAMES = ["car", "bus", "truck", "motorcycle"]
# 0 car, 2 bus, 3 truck, 4 motorbike, 5 van -> car
SOURCE_TO_TARGET = {0: 0, 2: 1, 3: 2, 4: 3, 5: 0}
THREEWHEEL = 1
VAN = 5


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


def phash_int(path: Path) -> int | None:
    try:
        with Image.open(path) as image:
            digest = imagehash.phash(image.convert("RGB"))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None
    return int(str(digest), 16)


def file_hash(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_label(path: Path) -> list[tuple[int, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(float(parts[0]))
            rest = " ".join(f"{float(piece):.6f}" for piece in parts[1:])
        except ValueError:
            continue
        rows.append((class_id, rest))
    return rows


def find_image(label: Path) -> Path | None:
    relative = label.relative_to(INTERIM)
    if "labels" not in relative.parts:
        return None
    index = relative.parts.index("labels")
    images_dir = RAW.joinpath(*relative.parts[:index], "images")
    if not images_dir.is_dir():
        return None
    hits = [
        path
        for path in images_dir.iterdir()
        if path.stem == label.stem and path.suffix.lower() in IMAGE_EXTS
    ]
    return hits[0] if hits else None


def exclus_stems(folder: str) -> set[str]:
    root = EXCLUS / folder / "images"
    found = set()
    if not root.is_dir():
        return found
    for path in root.iterdir():
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        stem = path.stem
        if "__" in stem:
            stem = stem.split("__", 1)[1]
        found.add(Path(stem).stem.casefold())
    return found


def ensure_exclus_copy(image: Path, label: Path, rows: list[tuple[int, str]]) -> bool:
    """Copy a threewheel image into vehicles_exclus if it is not already there."""
    dest_dir_images = EXCLUS / "threewheel" / "images"
    dest_dir_labels = EXCLUS / "threewheel" / "labels"
    dest_dir_images.mkdir(parents=True, exist_ok=True)
    dest_dir_labels.mkdir(parents=True, exist_ok=True)
    split_name = image.parent.parent.name
    dest_image = dest_dir_images / f"{split_name}__{image.name}"
    dest_label = dest_dir_labels / f"{split_name}__{label.name}"
    wrote = False
    if not dest_image.exists():
        shutil.copy2(image, dest_image)
        wrote = True
    if not dest_label.exists():
        lines = [f"{class_id} {rest}" for class_id, rest in rows if class_id == THREEWHEEL]
        dest_label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")
        wrote = True
    return wrote


def collect() -> list[dict]:
    items = []
    labels = [path for path in INTERIM.rglob("*.txt") if "labels" in path.parts]
    for label in labels:
        image = find_image(label)
        if image is None or not image.is_file():
            continue
        rows = parse_label(label)
        class_ids = {class_id for class_id, _rest in rows}
        items.append(
            {
                "image": image,
                "label": label,
                "rows": rows,
                "classes": class_ids,
            }
        )
    return items


def mapped_lines(rows: list[tuple[int, str]]) -> list[str]:
    kept = []
    for class_id, rest in rows:
        if class_id == THREEWHEEL:
            continue
        target = SOURCE_TO_TARGET.get(class_id)
        if target is None:
            continue
        kept.append(f"{target} {rest}")
    return kept


def assign(records: list[dict], hashes: list[int | None], md5s: list[str]) -> dict[int, str]:
    union = UnionFind(len(records))
    by_hash: dict[str, int] = {}
    for index, digest in enumerate(md5s):
        if digest in by_hash:
            union.union(index, by_hash[digest])
        else:
            by_hash[digest] = index
    for left in range(len(records)):
        left_hash = hashes[left]
        if left_hash is None:
            continue
        for right in range(left + 1, len(records)):
            right_hash = hashes[right]
            if right_hash is None:
                continue
            if (left_hash ^ right_hash).bit_count() <= HAMMING_MAX:
                union.union(left, right)
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        groups[union.find(index)].append(index)
    sizes = sorted((len(group) for group in groups.values()), reverse=True)
    print(f"Groupes : {len(sizes)}, plus gros : {sizes[:8]}", flush=True)
    order = list(groups.values())
    random.Random(SEED).shuffle(order)
    order.sort(key=len, reverse=True)
    total = len(records)
    targets = {name: fraction * total for name, fraction in FRACTIONS}
    counts = {name: 0 for name, _fraction in FRACTIONS}
    assignment: dict[int, str] = {}
    for group in order:
        def score(name: str, group_size: int = len(group)) -> tuple[float, float]:
            after = counts[name] + group_size
            overflow = max(0.0, after - targets[name])
            return (overflow, abs(targets[name] - after))

        choice = min(counts, key=score)
        for index in group:
            assignment[index] = choice
        counts[choice] += len(group)
    return assignment, sizes


def cross_pairs(splits: list[str], hashes: list[int | None]) -> Counter[tuple[str, str]]:
    found: Counter[tuple[str, str]] = Counter()
    for left in range(len(splits)):
        if hashes[left] is None:
            continue
        for right in range(left + 1, len(splits)):
            if hashes[right] is None or splits[right] == splits[left]:
                continue
            if (hashes[left] ^ hashes[right]).bit_count() <= HAMMING_MAX:
                found[tuple(sorted((splits[left], splits[right])))] += 1
    return found


def reset_splits() -> None:
    for name, _fraction in FRACTIONS:
        folder = PROCESSED / name
        if folder.exists():
            shutil.rmtree(folder)
        (folder / "images").mkdir(parents=True, exist_ok=True)
        (folder / "labels").mkdir(parents=True, exist_ok=True)


def write_yaml() -> None:
    payload = {
        "path": ".",
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "names": {index: name for index, name in enumerate(NAMES)},
    }
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "data.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


def update_config() -> None:
    payload = {
        "source_names": ["car", "threewheel", "bus", "truck", "motorbike", "van"],
        "keep": {"car": 0, "bus": 1, "truck": 2, "motorcycle": 3},
        "source_to_target": {"0": 0, "2": 1, "3": 2, "4": 3, "5": 0},
        "van_to_car": True,
        "excluded_if_present": {"threewheel": 1},
        "target_names": NAMES,
        "note": "Une image qui contient threewheel est retirée entière. van devient car.",
    }
    CONFIGS.mkdir(parents=True, exist_ok=True)
    (CONFIGS / "classes_vehicles.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    items = collect()
    kept = []
    excluded = []
    van_only = []
    van_boxes_in_kept = 0
    van_only_boxes = 0
    van_mixed_boxes = 0
    van_images_with_other = 0
    for item in items:
        classes = item["classes"]
        if THREEWHEEL in classes:
            excluded.append(item)
            continue
        lines = mapped_lines(item["rows"])
        if not lines:
            continue
        item["lines"] = lines
        kept.append(item)
        van_boxes = sum(1 for class_id, _rest in item["rows"] if class_id == VAN)
        if van_boxes:
            others = classes - {VAN}
            if not others:
                van_only.append(item)
                van_only_boxes += van_boxes
            else:
                van_images_with_other += 1
                van_mixed_boxes += van_boxes
            van_boxes_in_kept += van_boxes

    removed_from_previous = [
        item for item in excluded if item["classes"] & {0, 2, 3, 4}
    ]
    copied_missing = 0
    known_exclus = exclus_stems("threewheel")
    for item in excluded:
        if item["image"].stem.casefold() not in known_exclus:
            if ensure_exclus_copy(item["image"], item["label"], item["rows"]):
                copied_missing += 1

    print(f"Images brutes : {len(items)}", flush=True)
    print(f"Retirées (threewheel) : {len(excluded)}", flush=True)
    print(f"Dont déjà dans le jeu traité : {len(removed_from_previous)}", flush=True)
    print(f"Van seulement : {len(van_only)}", flush=True)
    print(f"Gardées : {len(kept)}", flush=True)
    if not kept:
        raise SystemExit("Aucune image gardée. Le jeu traité n'est pas réécrit.")

    hashes = [
        phash_int(item["image"])
        for item in tqdm(kept, desc="pHash véhicules", unit="img")
    ]
    md5s = [file_hash(item["image"]) for item in kept]
    assignment, sizes = assign(kept, hashes, md5s)
    splits = [assignment[index] for index in range(len(kept))]
    leaks = cross_pairs(splits, hashes)
    if leaks:
        raise SystemExit(f"Fuites pHash, rien n'est écrit : {dict(leaks)}")

    stems = Counter(item["image"].stem.casefold() for item in kept)
    reset_splits()
    written_boxes: Counter[tuple[str, int]] = Counter()
    written_images: Counter[str] = Counter()
    for index, item in enumerate(kept):
        split = assignment[index]
        image = item["image"]
        name = image.name
        if stems[image.stem.casefold()] > 1:
            name = f"{image.parent.parent.name}__{image.name}"
        dest_image = PROCESSED / split / "images" / name
        dest_label = PROCESSED / split / "labels" / f"{Path(name).stem}.txt"
        shutil.copy2(image, dest_image)
        dest_label.write_text("\n".join(item["lines"]) + "\n", encoding="utf-8", newline="\n")
        written_images[split] += 1
        for line in item["lines"]:
            written_boxes[(split, int(line.split()[0]))] += 1
    write_yaml()
    update_config()

    total = len(kept)
    lines = [
        "# Véhicules révisés",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Les feux et les plaques n'ont pas été redécoupés.",
        "- `van` (classe d'origine 5) est réécrit `car` (classe 0).",
        "- Toute image qui contient au moins une boîte `threewheel` est retirée du jeu, autres boîtes comprises. Elle reste dans `data/raw/vehicles_exclus/threewheel/`.",
        "- Découpage 70/20/10, graine 42. Doublons MD5 et pHash (distance de Hamming <= 5) dans le même sous-ensemble.",
        "",
        "## Effectifs",
        "",
        f"- Images lues dans `data/interim/vehicles` : {len(items)}.",
        f"- Images retirées parce qu'elles contiennent un threewheel : {len(excluded)}.",
        f"- Parmi elles, présentes dans l'ancien jeu traité : {len(removed_from_previous)}.",
        f"- Images van seulement, remises dans le jeu : {len(van_only)} images, {van_only_boxes} boîtes, toutes devenues car.",
        f"- Images gardées qui avaient déjà une autre classe et des boîtes van : {van_images_with_other} images, {van_mixed_boxes} boîtes van devenues car.",
        f"- Boîtes van au total réécrites en car : {van_boxes_in_kept}. Celles qui partageaient une image avec un threewheel sont sorties avec cette image.",
        f"- Copies threewheel manquantes ajoutées dans vehicles_exclus : {copied_missing}.",
        f"- Images écrites : {total}.",
        "",
        "## Découpage",
        "",
        f"- Groupes de quasi-doublons : {len(sizes)}. Plus gros : {', '.join(str(size) for size in sizes[:8])}.",
        "- Paires pHash entre sous-ensembles après placement : aucune.",
        "",
        "| Sous-ensemble | Images | Part |",
        "| --- | --- | --- |",
    ]
    for name, _fraction in FRACTIONS:
        count = written_images[name]
        lines.append(f"| {name} | {count} | {count / total:.1%} |")
    lines += [
        "",
        "## Annotations",
        "",
        "| Classe | train | val | test | total |",
        "| --- | --- | --- | --- | --- |",
    ]
    for index, name in enumerate(NAMES):
        per_split = [written_boxes[(split, index)] for split, _fraction in FRACTIONS]
        lines.append(
            f"| {name} | {per_split[0]} | {per_split[1]} | {per_split[2]} | {sum(per_split)} |"
        )
    lines += [
        "",
        "Les images threewheel seules (celles qui ne sont pas revenues) restent dans `data/raw/vehicles_exclus/threewheel/`. Rien n'a été supprimé de ce dossier.",
        "",
    ]
    report = REPORTS / "vehicules_revise.md"
    report.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(report)
    print(dict(written_images))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
