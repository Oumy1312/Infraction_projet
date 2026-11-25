#!/usr/bin/env python3
"""Contrôles avant entraînement. Ne lance aucun entraînement.

pHash (imagehash) sur data/processed. Les paires à distance <= 5 dans des
sous-ensembles différents sont listées. Pour les feux, les numéros à 6 chiffres
écartés d'au plus 2 restent dans le même sous-ensemble, puis le découpage
70/20/10 est refait (graine 42).

Les labels de couleur d'origine sont copiés dans data/interim/feux_couleur/.
Van et threewheel ne sont pas réécrits.

    python scripts/04_controles_pre_train.py
"""

from __future__ import annotations

import os
import random
import re
import shutil
import sys
import heapq
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import imagehash
from PIL import Image, ImageDraw, UnidentifiedImageError
from tqdm import tqdm

PROJECT = Path(__file__).resolve().parents[1]
PROCESSED = PROJECT / "data" / "processed"
RAW = PROJECT / "data" / "raw"
INTERIM = PROJECT / "data" / "interim"
REPORTS = PROJECT / "reports"
DATASETS = ("vehicles", "traffic_lights", "plates_detection")
SEED = 42
HAMMING_MAX = 5
PROCHE_GAP = 2
FRACTIONS = (("train", 0.70), ("val", 0.20), ("test", 0.10))
SPLITS = ("train", "val", "test")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
LIGHT_NAMES = [
    "go 0", "go_left", "go_right", "green", "off", "off 4", "red",
    "stop 2", "stop_left", "wait_on", "warn 3", "warn_left", "yellow",
]
VEHICLE_NAMES = ["car", "threewheel", "bus", "truck", "motorbike", "van"]


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


def six_digit(name: str) -> int | None:
    match = re.match(r"(\d{6})(?:_jpg)?\.rf\.", name, re.IGNORECASE)
    if match is None:
        match = re.match(r"(\d{6})\.", name)
    if match is None:
        return None
    return int(match.group(1))


def list_images(dataset: str) -> list[tuple[Path, str]]:
    rows = []
    root = PROCESSED / dataset
    for split in SPLITS:
        folder = root / split / "images"
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                rows.append((path, split))
    return rows


def label_path(image: Path) -> Path:
    return image.parent.parent / "labels" / f"{image.stem}.txt"


def split_counts(dataset: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for split in SPLITS:
        folder = PROCESSED / dataset / split / "images"
        if folder.is_dir():
            counts[split] = sum(1 for path in folder.iterdir() if path.suffix.lower() in IMAGE_EXTS)
    return counts


def cross_pairs(rows: list[tuple[Path, str]], hashes: list[int | None]) -> tuple[Counter[tuple[str, str]], list[tuple[int, int, int]]]:
    by_split: Counter[tuple[str, str]] = Counter()
    closest: list[tuple[int, int, int]] = []
    total = len(rows)
    for left in range(total):
        left_hash = hashes[left]
        if left_hash is None:
            continue
        left_split = rows[left][1]
        for right in range(left + 1, total):
            right_hash = hashes[right]
            if right_hash is None or rows[right][1] == left_split:
                continue
            distance = (left_hash ^ right_hash).bit_count()
            if distance > HAMMING_MAX:
                continue
            pair = tuple(sorted((left_split, rows[right][1])))
            by_split[pair] += 1
            entry = (-distance, left, right)
            if len(closest) < 80:
                heapq.heappush(closest, entry)
            elif -closest[0][0] > distance:
                heapq.heapreplace(closest, entry)
    return by_split, sorted((-distance, left, right) for distance, left, right in closest)


def consecutive_cross(rows: list[tuple[Path, str]]) -> Counter[tuple[str, str]]:
    numbered = []
    for path, split in rows:
        value = six_digit(path.name)
        if value is not None:
            numbered.append((value, split))
    numbered.sort()
    counts: Counter[tuple[str, str]] = Counter()
    for (left_id, left_split), (right_id, right_split) in zip(numbered, numbered[1:]):
        if right_id - left_id == 1 and left_split != right_split:
            counts[tuple(sorted((left_split, right_split)))] += 1
    return counts


def assign_lights(rows: list[tuple[Path, str]], hashes: list[int | None]) -> dict[Path, str]:
    union = UnionFind(len(rows))
    for left in range(len(rows)):
        left_hash = hashes[left]
        if left_hash is None:
            continue
        for right in range(left + 1, len(rows)):
            right_hash = hashes[right]
            if right_hash is None:
                continue
            if (left_hash ^ right_hash).bit_count() <= HAMMING_MAX:
                union.union(left, right)
    numbered = [(six_digit(path.name), index) for index, (path, _split) in enumerate(rows)]
    numbered = [(value, index) for value, index in numbered if value is not None]
    numbered.sort()
    for (left_id, left), (right_id, right) in zip(numbered, numbered[1:]):
        if 0 < right_id - left_id <= PROCHE_GAP:
            union.union(left, right)
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        groups[union.find(index)].append(index)
    sizes = sorted((len(group) for group in groups.values()), reverse=True)
    print(f"Groupes : {len(sizes)}, plus gros : {sizes[:8]}", flush=True)
    order = list(groups.values())
    random.Random(SEED).shuffle(order)
    order.sort(key=len, reverse=True)
    total = len(rows)
    targets = {name: fraction * total for name, fraction in FRACTIONS}
    counts = {name: 0 for name, _fraction in FRACTIONS}
    assignment: dict[Path, str] = {}
    for group in order:
        def score(name: str, group_size: int = len(group)) -> tuple[float, float]:
            after = counts[name] + group_size
            overflow = max(0.0, after - targets[name])
            return (overflow, abs(targets[name] - after))

        choice = min(counts, key=score)
        for index in group:
            assignment[rows[index][0]] = choice
        counts[choice] += len(group)
    return assignment


def apply_assignment(rows: list[tuple[Path, str]], assignment: dict[Path, str]) -> int:
    moved = 0
    for image, split in rows:
        target = assignment[image]
        if target == split:
            continue
        dest_image = PROCESSED / "traffic_lights" / target / "images" / image.name
        dest_label = PROCESSED / "traffic_lights" / target / "labels" / f"{image.stem}.txt"
        dest_image.parent.mkdir(parents=True, exist_ok=True)
        dest_label.parent.mkdir(parents=True, exist_ok=True)
        source_label = label_path(image)
        shutil.move(str(image), dest_image)
        if source_label.is_file():
            shutil.move(str(source_label), dest_label)
        moved += 1
    return moved


def draw_sheet(
    examples: list[tuple[str, int, Path, str, Path, str]],
    destination: Path,
    title: str = "Fuites pHash  distance <= 5  sous-ensembles différents",
    subtitle: str = "Avant regroupement. Gauche puis droite.",
) -> None:
    columns = 3
    rows = (len(examples) + columns - 1) // columns
    thumb_w, thumb_h, pad = 220, 150, 8
    cell_w = thumb_w * 2 + 8
    header = 64
    width = pad + columns * (cell_w + pad)
    height = header + max(rows, 1) * (thumb_h + 36 + pad)
    sheet = Image.new("RGB", (width, height), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 10), title, fill=(240, 240, 240))
    draw.text((pad, 32), subtitle, fill=(200, 200, 200))
    for index, (dataset, distance, left, left_split, right, right_split) in enumerate(examples):
        column = index % columns
        row = index // columns
        origin_x = pad + column * (cell_w + pad)
        origin_y = header + row * (thumb_h + 36 + pad)
        for offset, path in ((0, left), (thumb_w + 8, right)):
            try:
                with Image.open(path) as image:
                    frame = image.convert("RGB")
                    frame.thumbnail((thumb_w, thumb_h))
                    canvas = Image.new("RGB", (thumb_w, thumb_h), (32, 32, 32))
                    canvas.paste(frame, ((thumb_w - frame.width) // 2, (thumb_h - frame.height) // 2))
                sheet.paste(canvas, (origin_x + offset, origin_y))
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                draw.rectangle(
                    [origin_x + offset, origin_y, origin_x + offset + thumb_w, origin_y + thumb_h],
                    outline=(180, 60, 60),
                )
        draw.text(
            (origin_x, origin_y + thumb_h + 4),
            f"{dataset}  d={distance}  {left_split}/{right_split}",
            fill=(230, 230, 230),
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, format="JPEG", quality=85)


def copy_color_labels() -> dict[str, int]:
    destination = INTERIM / "feux_couleur"
    copied = {"labels": 0, "images": 0, "liens": 0}
    source = RAW / "traffic_lights"
    for label in source.rglob("*.txt"):
        if "labels" not in label.parts:
            continue
        relative = label.relative_to(source)
        dest = destination / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(label, dest)
            copied["labels"] += 1
        image_dir = label.parent.parent / "images"
        hits = [path for path in image_dir.iterdir() if path.stem == label.stem and path.suffix.lower() in IMAGE_EXTS] if image_dir.is_dir() else []
        if not hits:
            continue
        image = hits[0]
        dest_image = destination / image.relative_to(source)
        if dest_image.exists():
            continue
        dest_image.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(image, dest_image)
            copied["liens"] += 1
        except OSError:
            shutil.copy2(image, dest_image)
            copied["images"] += 1
    names = destination / "classes.txt"
    names.write_text("\n".join(LIGHT_NAMES) + "\n", encoding="utf-8", newline="\n")
    return copied


def raw_label_index() -> dict[str, Path]:
    index = {}
    root = RAW / "vehicles"
    for label in root.rglob("*.txt"):
        if label.name.lower() == "classes.txt" or "labels" not in label.parts:
            continue
        index[label.stem.casefold()] = label
    return index


def box_counts(path: Path) -> Counter[int]:
    counts: Counter[int] = Counter()
    if not path.is_file():
        return counts
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            counts[int(float(parts[0]))] += 1
        except ValueError:
            continue
    return counts


def vehicle_exclusion_report(lines: list[str]) -> None:
    index = raw_label_index()
    kept_images = list_images("vehicles")
    kept_stems = {path.stem.casefold() for path, _split in kept_images}
    van_images = three_images = 0
    van_boxes = three_boxes = 0
    for path, _split in kept_images:
        counts = box_counts(index.get(path.stem.casefold(), Path()))
        if counts[5]:
            van_images += 1
            van_boxes += counts[5]
        if counts[1]:
            three_images += 1
            three_boxes += counts[1]
    excluded_only = 0
    excluded_van = excluded_three = 0
    for stem, label in index.items():
        if stem in kept_stems:
            continue
        counts = box_counts(label)
        if counts[5] or counts[1]:
            excluded_only += 1
        excluded_van += counts[5]
        excluded_three += counts[1]
    lines += [
        "## Van et threewheel",
        "",
        "Rien n'est réécrit. Les boîtes van (classe 5) et threewheel (classe 1) ont été retirées des labels de `data/processed/vehicles` lors du découpage.",
        "",
        f"- Images gardées : {len(kept_images)}.",
        f"- Parmi elles, images qui avaient des boîtes van : {van_images}, soit {van_boxes} boîtes. Ces boîtes ne sont plus dans le label : elles deviennent du fond.",
        f"- Parmi elles, images qui avaient des boîtes threewheel : {three_images}, soit {three_boxes} boîtes. Elles deviennent du fond elles aussi.",
        f"- Images laissées hors du jeu parce qu'elles ne contenaient que ces classes : {excluded_only}. Leurs boîtes van : {excluded_van}. Leurs boîtes threewheel : {excluded_three}. Elles sont dans `data/raw/vehicles_exclus/`.",
        "",
        "Proposition, non appliquée : `van` → `car` dans les labels des images gardées, `threewheel` reste exclu. Les boîtes threewheel des images gardées resteraient alors du fond.",
        "",
    ]


def negative_report(lines: list[str]) -> None:
    empties = []
    for dataset in ("traffic_lights", "vehicles", "plates_detection"):
        root = RAW / dataset
        for label in root.rglob("*.txt"):
            if "labels" not in label.parts or label.name.lower() == "classes.txt":
                continue
            if label.read_text(encoding="utf-8", errors="replace").strip() == "":
                empties.append((dataset, label))
    counts = split_counts("traffic_lights")
    train_n = counts["train"] or 1
    train_empty = 0
    for split in SPLITS:
        folder = PROCESSED / "traffic_lights" / split / "labels"
        if not folder.is_dir():
            continue
        for label in folder.glob("*.txt"):
            if label.read_text(encoding="utf-8").strip() == "":
                train_empty += split == "train"
    # recount properly
    empty_by_split = Counter()
    for split in SPLITS:
        folder = PROCESSED / "traffic_lights" / split / "labels"
        if not folder.is_dir():
            continue
        for label in folder.glob("*.txt"):
            if not label.read_text(encoding="utf-8").strip():
                empty_by_split[split] += 1
    rate = empty_by_split["train"] / counts["train"] if counts["train"] else 0
    needed = {split: int(round(counts[split] * rate)) for split in SPLITS}
    lines += [
        "## Images sans feu",
        "",
        f"- Labels vides dans les jeux bruts : {len(empties)}, tous dans traffic_lights." if empties else "- Aucun label vide.",
        f"- Après découpage, labels vides : train {empty_by_split['train']}, val {empty_by_split['val']}, test {empty_by_split['test']}.",
        f"- Proportion dans train : {empty_by_split['train']} / {counts['train']} = {rate:.4%}.",
        f"- Même proportion arrondie : val {needed['val']} image(s), test {needed['test']} image(s).",
        "",
    ]
    missing_val = max(0, needed["val"] - empty_by_split["val"])
    missing_test = max(0, needed["test"] - empty_by_split["test"])
    if missing_val or missing_test:
        lines.append(
            f"Il manque {missing_val} image vérifiée sans feu pour val et {missing_test} pour test. "
            "Les autres jeux n'annotent pas les feux : une photo de véhicule ou de plaque ne peut pas servir de négatif sans contrôle visuel. Aucune image n'a été ajoutée."
        )
    else:
        lines.append("La proportion est déjà atteinte. Aucune image ajoutée.")
    lines.append("")
    if empties:
        samples = []
        for dataset, label in empties:
            image_dir = label.parent.parent / "images"
            hits = [path for path in image_dir.iterdir() if path.stem == label.stem and path.suffix.lower() in IMAGE_EXTS] if image_dir.is_dir() else []
            if hits:
                samples.append((dataset, 0, hits[0], "vide", hits[0], "vide"))
        if samples:
            draw_sheet(samples[:30], REPORTS / "contact_negatifs.jpg")
            lines.append("Planche des images au label vide : `reports/contact_negatifs.jpg`.")
            lines.append("")


def fmt_counter(counter: Counter[tuple[str, str]]) -> str:
    if not counter:
        return "aucune"
    return ", ".join(f"{a}/{b} {count}" for (a, b), count in sorted(counter.items()))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    before_counts = {dataset: split_counts(dataset) for dataset in DATASETS}
    stored: dict[str, tuple[list[tuple[Path, str]], list[int | None]]] = {}
    leak_before: dict[str, Counter[tuple[str, str]]] = {}
    examples: list[tuple[str, int, Path, str, Path, str]] = []
    for dataset in DATASETS:
        rows = list_images(dataset)
        hashes = [phash_int(path) for path, _split in tqdm(rows, desc=f"pHash {dataset}")]
        stored[dataset] = (rows, hashes)
        counts, best = cross_pairs(rows, hashes)
        leak_before[dataset] = counts
        ranked = sorted(best, key=lambda item: (0 if {rows[item[1]][1], rows[item[2]][1]} == {"train", "test"} else 1, item[0]))
        for distance, left, right in ranked[:40]:
            examples.append((
                dataset, distance, rows[left][0], rows[left][1], rows[right][0], rows[right][1],
            ))
    chosen = []
    seen = set()
    for item in sorted(examples, key=lambda row: (row[0] != "traffic_lights", 0 if {row[3], row[5]} == {"train", "test"} else 1, row[1])):
        key = (item[2], item[4])
        if key in seen:
            continue
        seen.add(key)
        chosen.append(item)
        if len(chosen) == 30:
            break
    sheet = REPORTS / "contact_fuites.jpg"
    if chosen:
        draw_sheet(chosen, sheet)

    light_rows, light_hashes = stored["traffic_lights"]
    consecutive_before = consecutive_cross(light_rows)
    proche_before = Counter()
    numbered = []
    for path, split in light_rows:
        value = six_digit(path.name)
        if value is not None:
            numbered.append((value, split))
    numbered.sort()
    for (left_id, left_split), (right_id, right_split) in zip(numbered, numbered[1:]):
        if 0 < right_id - left_id <= PROCHE_GAP and left_split != right_split:
            proche_before[tuple(sorted((left_split, right_split)))] += 1
    moved = 0
    if consecutive_before.get(("test", "train"), 0):
        assignment = assign_lights(light_rows, light_hashes)
        moved = apply_assignment(light_rows, assignment)
        light_rows = list_images("traffic_lights")
        by_name = {path.name: digest for (path, _split), digest in zip(stored["traffic_lights"][0], light_hashes)}
        light_hashes = [by_name.get(path.name) for path, _split in light_rows]
        stored["traffic_lights"] = (light_rows, light_hashes)
    after_counts = split_counts("traffic_lights")
    leak_after, _best_after = cross_pairs(light_rows, light_hashes)
    consecutive_after = consecutive_cross(light_rows)
    proche_after = Counter()
    numbered = []
    for path, split in light_rows:
        value = six_digit(path.name)
        if value is not None:
            numbered.append((value, split))
    numbered.sort()
    for (left_id, left_split), (right_id, right_split) in zip(numbered, numbered[1:]):
        if 0 < right_id - left_id <= PROCHE_GAP and left_split != right_split:
            proche_after[tuple(sorted((left_split, right_split)))] += 1

    color_copy = copy_color_labels()
    lines = [
        "# Fuites train / val / test",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Hash : pHash imagehash, 64 bits. Quasi-identique : distance de Hamming <= {HAMMING_MAX}.",
        f"- Numéros proches : identifiants à 6 chiffres dont l'écart est de 1 à {PROCHE_GAP}. Un écart de 5 relierait 3 899 feux en deux blocs d'environ 1 950 images, impossibles à répartir en 70/20/10. L'écart 2 laisse des groupes dont le plus gros tient dans train.",
        f"- Graine du nouveau découpage des feux : {SEED}.",
        "",
        "## Avant",
        "",
    ]
    for dataset in DATASETS:
        counts = before_counts[dataset]
        lines.append(
            f"- {dataset} : train {counts['train']}, val {counts['val']}, test {counts['test']}. "
            f"Paires pHash entre sous-ensembles : {fmt_counter(leak_before[dataset])}."
        )
    lines += [
        f"- Feux, numéros consécutifs (écart 1) dans deux sous-ensembles : {fmt_counter(consecutive_before)}.",
        f"- Feux, numéros proches (écart <= {PROCHE_GAP}) dans deux sous-ensembles : {fmt_counter(proche_before)}.",
        "",
        "## Après le regroupement des feux",
        "",
        f"- Images déplacées : {moved}.",
        f"- traffic_lights : train {after_counts['train']}, val {after_counts['val']}, test {after_counts['test']}.",
        f"- Paires pHash entre sous-ensembles : {fmt_counter(leak_after)}.",
        f"- Numéros consécutifs entre sous-ensembles : {fmt_counter(consecutive_after)}.",
        f"- Numéros proches (écart <= {PROCHE_GAP}) entre sous-ensembles : {fmt_counter(proche_after)}.",
        "",
        "Les jeux vehicles et plates_detection n'ont pas été redécoupés. Leurs paires sont dans le tableau Avant.",
        "",
        f"Planche de {len(chosen)} exemples (état avant, priorité aux paires train/test) : `{sheet.relative_to(PROJECT).as_posix()}`.",
        "",
    ]
    report = REPORTS / "fuites.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    control = [
        "# Contrôles avant entraînement",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Source Infraction et quarantine/ non lus pour écriture. Aucun poids. Aucun entraînement.",
        "",
        "## Classes d'origine des feux",
        "",
        "Elles sont encore dans `data/raw/traffic_lights` et dans `data/interim/traffic_lights`. Le détecteur de `data/processed/traffic_lights` reste à une classe `traffic_light`.",
        "",
        "Noms S2TLD, identifiant d'origine :",
        "",
    ]
    for index, name in enumerate(LIGHT_NAMES):
        control.append(f"- {index} : {name}")
    control += [
        "",
        "Rouge = 6, vert = 3, jaune = 12. Les autres noms sont des états (go, stop, off, warn), pas une couleur.",
        "",
        f"Copies dans `data/interim/feux_couleur/` : {color_copy['labels']} labels, {color_copy['liens']} images liées au fichier brut, {color_copy['images']} images copiées. `classes.txt` reprend les 13 noms.",
        "",
        "1 211 fichiers n'ont que la classe 0 et un nom à 6 chiffres. Pour ceux-là, la classe 0 n'est pas « go » : aucune couleur n'a été annotée. Elle ne se retrouve pas dans la source, parce qu'elle n'y a jamais été écrite.",
        "",
    ]
    vehicle_exclusion_report(control)
    negative_report(control)
    control += [
        "## GPU",
        "",
        "Contrôle fait à part dans le rapport de session : `torch.cuda.is_available()` et le notebook Colab si besoin.",
        "",
    ]
    (REPORTS / "controles_pre_train.md").write_text("\n".join(control) + "\n", encoding="utf-8", newline="\n")
    print(f"Fuites avant feux : {dict(leak_before['traffic_lights'])}")
    print(f"Consécutifs avant : {dict(consecutive_before)}")
    print(f"Déplacés : {moved}")
    print(f"Après : {dict(after_counts)}")
    print(f"pHash après : {dict(leak_after)}")
    print(f"Consécutifs après : {dict(consecutive_after)}")
    print(f"Couleur : {color_copy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
