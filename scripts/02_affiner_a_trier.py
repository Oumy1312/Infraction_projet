#!/usr/bin/env python3
"""Mesures sur les fichiers prévus dans _a_trier. Ne copie rien et ne déplace rien.

La conversion polygone → boîte englobante sert uniquement au rapport largeur/hauteur
et à l'aire relative. Les annotations restent inchangées.

    python scripts/02_affiner_a_trier.py
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import yaml
    from PIL import Image, ImageDraw, UnidentifiedImageError
    from tqdm import tqdm
except ImportError as exc:
    print(f"Dépendance manquante : {exc}")
    print("Installez-les avec : python -m pip install -r requirements.txt")
    raise SystemExit(1)


def load_reorg():
    path = Path(__file__).resolve().parent / "01_reorganize.py"
    spec = importlib.util.spec_from_file_location("reorg_step", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Import impossible : {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REORG = load_reorg()
PROJECT_ROOT = REORG.PROJECT_ROOT
DEFAULT_SRC = REORG.DEFAULT_SRC
REPORTS = REORG.REPORTS
RF_MOTIF = REORG.RF_MOTIF


@dataclass
class Box:
    kind: str
    class_id: int
    width: float
    height: float

    @property
    def ratio(self) -> float | None:
        if self.height <= 1e-8:
            return None
        return self.width / self.height

    @property
    def area(self) -> float | None:
        if self.width < 0 or self.height < 0:
            return None
        area = self.width * self.height
        if area <= 0:
            return None
        return area


@dataclass
class Measure:
    image: Path | None
    label: Path
    split: str
    group: str
    prefix: str
    width: int | None
    height: int | None
    format_name: str
    n_lines: int
    classes: set[int]
    boxes: list[Box] = field(default_factory=list)
    ratio: float | None = None
    area: float | None = None
    category: str = "incertain"
    ambiguity: float | None = None
    distance_plates: float | None = None
    distance_lights: float | None = None
    contradiction: str = ""
    revised: str = ""

    @property
    def resolution(self) -> str:
        if self.image is None:
            return "absente"
        if self.width is None or self.height is None:
            return "illisible"
        return f"{self.width}x{self.height}"


def prefix_of(filename: str) -> str:
    lowered = filename.lower()
    position = lowered.find(RF_MOTIF)
    if position >= 0:
        return filename[:position]
    for marker in ("_jpeg.rf.", "_png.rf.", ".rf."):
        other = lowered.find(marker)
        if other >= 0:
            return f"(sans {RF_MOTIF}) {filename[:other]}"
    return f"(sans {RF_MOTIF}) {Path(filename).stem}"


def family_of(prefix: str) -> str:
    name = prefix
    if name.startswith("(sans "):
        pieces = name.split(") ", 1)
        name = pieces[1] if len(pieces) == 2 else name
    low = name.lower()
    if name.isdigit():
        return f"id_{len(name)}_chiffres"
    if "ma-2014-moped" in low:
        return "MA-2014-moped"
    if low.startswith("ma_moped") or low.startswith("ma-moped"):
        return "MA_Moped"
    if "license_plate" in low:
        return "Morocco_license_plate"
    if low.startswith("marokko"):
        return "marokko"
    if low.startswith("morocco"):
        return "morocco"
    if low.startswith("unnamed"):
        return "unnamed"
    if low.startswith("downlo"):
        return "download"
    if low.startswith("auto-ecole"):
        return "auto-ecole"
    if len(name) > 1 and low.startswith("t") and name[1:].isdigit():
        return "T"
    if low.startswith("ma_"):
        return "ma_"
    return name[:40]


REVISED_THRESHOLD = 0.70


def revised_category(item: Measure, threshold: float = REVISED_THRESHOLD) -> str:
    """Seuil sur la médiane du fichier. Au-dessus, le fichier est une plaque."""
    if item.ratio is None:
        return "incertain"
    if item.ratio <= threshold:
        return "traffic_lights"
    return "plates_detection"


def write_histogram(bin_counts: list[int], destination: Path) -> None:
    bins = len(bin_counts)
    bar_w, gap = 16, 3
    left, top, bottom = 64, 48, 70
    plot_h = 360
    width = left + bins * (bar_w + gap) + 24
    height = top + plot_h + bottom
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    title_font = REORG.font(16)
    small = REORG.font(11)
    peak = max(bin_counts) or 1
    draw.text(
        (left, 12),
        "Boîtes de classe 0 dans _a_trier — rapport largeur/hauteur",
        fill=(20, 20, 20),
        font=title_font,
    )
    base = top + plot_h
    draw.line((left, top, left, base), fill=(40, 40, 40))
    draw.line((left, base, width - 12, base), fill=(40, 40, 40))
    for index, count in enumerate(bin_counts):
        x = left + 8 + index * (bar_w + gap)
        bar_h = int(plot_h * count / peak)
        draw.rectangle((x, base - bar_h, x + bar_w, base), fill=(36, 99, 168))
        if index % 5 == 0:
            draw.text((x, base + 6), f"{index / 10:.1f}", fill=(20, 20, 20), font=small)
    draw.text((8, top), str(peak), fill=(20, 20, 20), font=small)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


def median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if value > 0)
    if not clean:
        return None
    middle = len(clean) // 2
    if len(clean) % 2:
        return clean[middle]
    return (clean[middle - 1] + clean[middle]) / 2


def percentile(values: list[float], fraction: float) -> float | None:
    clean = sorted(value for value in values if value > 0)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    rank = (len(clean) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(clean) - 1)
    weight = rank - low
    return clean[low] * (1 - weight) + clean[high] * weight


def parse_boxes(path: Path) -> tuple[int, list[Box]]:
    """Boîte englobante d'un polygone : calcul local, rien n'est écrit."""
    try:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return 0, []
    count = 0
    boxes: list[Box] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        count += 1
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            class_id = int(float(parts[0]))
            values = [float(piece) for piece in parts[1:]]
        except ValueError:
            continue
        if not values or max(abs(value) for value in values) > 1.05:
            continue
        if len(values) == 4:
            boxes.append(Box("boite", class_id, values[2], values[3]))
        elif len(values) >= 6 and len(values) % 2 == 0:
            xs = values[0::2]
            ys = values[1::2]
            boxes.append(Box("polygone", class_id, max(xs) - min(xs), max(ys) - min(ys)))
    return count, boxes


def format_name(boxes: list[Box]) -> str:
    kinds = {box.kind for box in boxes}
    if kinds == {"boite"}:
        return "boite"
    if kinds == {"polygone"}:
        return "polygone"
    if kinds == {"boite", "polygone"}:
        return "mixte"
    return "autre"


def image_size(path: Path | None) -> tuple[int | None, int | None]:
    if path is None or not path.is_file():
        return None, None
    try:
        with Image.open(path) as image:
            return image.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None, None


def fmt(value: float | None, digits: int = 3) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def collect_measures(src: Path) -> tuple[list[Measure], list[float], list[float], list[float], list[float]]:
    plate_ratios: list[float] = []
    plate_areas: list[float] = []
    light_ratios: list[float] = []
    light_areas: list[float] = []
    measures: list[Measure] = []

    dataset = src / "dataset"
    if dataset.is_dir():
        labels = [path for path in REORG.walk_files(dataset) if REORG.is_label_file(path)]
        for path in tqdm(labels, desc="Référence dataset/", unit="fichier"):
            _, boxes = parse_boxes(path)
            for box in boxes:
                if box.ratio is not None and box.area is not None:
                    plate_ratios.append(box.ratio)
                    plate_areas.append(box.area)

    for split in ("train", "valid", "test"):
        labels_dir = src / split / "labels"
        images_dir = src / split / "images"
        if not labels_dir.is_dir():
            continue
        images = REORG.index_images(images_dir)
        label_paths = sorted(
            (path for path in labels_dir.iterdir() if path.is_file() and REORG.is_label_file(path)),
            key=lambda item: item.name.lower(),
        )
        for label in tqdm(label_paths, desc=f"Mesures {split}", unit="fichier"):
            info = REORG.ANALYZE.classify_txt(label)
            category, group, _note = REORG.route_mixed_label(split, info)
            n_lines, boxes = parse_boxes(label)
            if category == "traffic_lights" and info.syntax == "yolo_bbox":
                for box in boxes:
                    if box.ratio is not None and box.area is not None:
                        light_ratios.append(box.ratio)
                        light_areas.append(box.area)
            if category != "_a_trier":
                continue
            if REORG.motif_rf(label):
                group = f"{group}__rf"
            else:
                group = f"{group}__sans_rf"
            matches = images.get(label.stem.casefold(), [])
            image = matches[0] if matches else None
            width, height = image_size(image)
            name = image.name if image is not None else label.name
            ratios = [box.ratio for box in boxes if box.ratio is not None]
            areas = [box.area for box in boxes if box.area is not None]
            measures.append(Measure(
                image=image,
                label=label,
                split=split,
                group=group,
                prefix=prefix_of(name),
                width=width,
                height=height,
                format_name=format_name(boxes),
                n_lines=n_lines,
                classes=set(info.ids),
                boxes=boxes,
                ratio=median([value for value in ratios if value is not None]),
                area=median([value for value in areas if value is not None]),
            ))
    return measures, plate_ratios, plate_areas, light_ratios, light_areas


def assign(measures: list[Measure], low: float) -> None:
    """Seuil unique : le p90 des feux. Au-dessus, le rapport est celui d'une plaque."""
    for item in measures:
        reasons: list[str] = []
        if item.ratio is None or low <= 0:
            item.category = "incertain"
            item.ambiguity = None
            item.contradiction = "géométrie absente"
            continue
        item.ambiguity = math.exp(-abs(math.log(item.ratio / low)))
        if item.ratio <= low and item.format_name == "polygone":
            item.category = "incertain"
            reasons.append("polygone dont le rapport l/h est du côté des feux")
        elif item.ratio <= low:
            item.category = "traffic_lights"
        else:
            item.category = "plates_detection"
        disagree = 0
        usable = 0
        for box in item.boxes:
            if box.ratio is None:
                continue
            usable += 1
            box_side = "traffic_lights" if box.ratio <= low else "plates_detection"
            if item.category in {"plates_detection", "traffic_lights"} and box_side != item.category:
                disagree += 1
        if item.category in {"plates_detection", "traffic_lights"} and usable and disagree * 2 >= usable:
            reasons.append("au moins la moitié des boîtes est de l'autre côté du seuil")
        if item.category == "plates_detection" and any(class_id > 0 for class_id in item.classes):
            reasons.append("classe autre que 0")
        item.contradiction = " ; ".join(reasons)


def describe_dataset(src: Path) -> list[str]:
    root = src / "dataset"
    lines = ["## Contenu de dataset/", ""]
    if not root.is_dir():
        lines.append("- Dossier absent.")
        return lines
    images = [path for path in REORG.walk_files(root) if REORG.is_image(path)]
    labels = [path for path in REORG.walk_files(root) if REORG.is_label_file(path)]
    image_stems = {path.stem.casefold() for path in images}
    label_stems = {path.stem.casefold() for path in labels}
    syntaxes: Counter[str] = Counter()
    class_ids: Counter[int] = Counter()
    for path in labels:
        info = REORG.ANALYZE.classify_txt(path)
        syntaxes[info.syntax] += 1
        class_ids.update(info.ids)
    extensions = Counter(path.suffix.lower() for path in images)
    relative_dirs = sorted({path.parent.relative_to(root).as_posix() for path in images})
    obj_names = REORG.read_class_lines(src / "obj.names")
    cfg_path = src / "yolov4-obj.cfg"
    cfg_classes: list[str] = []
    if cfg_path.is_file():
        text = cfg_path.read_text(encoding="utf-8", errors="replace")
        cfg_classes = re.findall(r"(?m)^\s*classes\s*=\s*(\d+)\s*$", text)
    yaml_path = src / "data (2).yaml"
    yaml_names = ""
    yaml_paths = ""
    if yaml_path.is_file():
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8-sig")) or {}
        except (OSError, yaml.YAMLError):
            data = {}
        if isinstance(data, dict):
            yaml_names = str(data.get("names"))
            yaml_paths = ", ".join(f"{key}={data.get(key)}" for key in ("train", "val", "test"))
    lines += [
        f"- Images : {len(images)} ({', '.join(f'{ext} {count}' for ext, count in sorted(extensions.items())) or 'aucune'}).",
        f"- Labels : {len(labels)}.",
        f"- Images sans label : {len(image_stems - label_stems)}.",
        f"- Labels sans image : {len(label_stems - image_stems)}.",
        f"- Sous-dossiers d'images : {', '.join(relative_dirs) if relative_dirs else 'aucun'}.",
        f"- Format des labels : {', '.join(f'{name} {count}' for name, count in sorted(syntaxes.items())) or 'aucun'}.",
        f"- Classes présentes (identifiants) : {', '.join(str(item) for item in sorted(class_ids)) or 'aucune'}.",
        f"- `obj.names` : {', '.join(obj_names) if obj_names else 'absent'}.",
        f"- `yolov4-obj.cfg` : classes={', '.join(cfg_classes) if cfg_classes else 'illisible ou absent'}. Le fichier de poids n'est pas ouvert.",
        f"- `data (2).yaml` : names={yaml_names or 'absent'} ; chemins {yaml_paths or 'absents'}.",
        "- Ces chemins YAML visent `../train/images`, `../valid/images` et `../test/images`. Ils ne décrivent pas le dossier `dataset/`.",
        "- Correspondance : `dataset/` est le jeu Darknet de plaques (`obj.names` = license_plate, une classe dans le `.cfg`, labels YOLO à une classe). `data (2).yaml` décrit aussi une classe `plate`, mais ses chemins ne pointent pas vers ce dossier.",
        "",
    ]
    return lines


PREDICTED_LABEL = {
    "plates_detection": ("prévu : plaque", (255, 140, 40)),
    "traffic_lights": ("prévu : feu", (40, 190, 70)),
    "incertain": ("prévu : incertain", (240, 180, 0)),
}


def choose_records(records: list[Measure], sample_size: int, seed: int, ranked: bool) -> list[Measure]:
    usable = [item for item in records if item.image is not None and item.image.is_file()]
    if ranked:
        return usable[:sample_size]
    if len(usable) <= sample_size:
        return usable
    return random.Random(seed).sample(usable, sample_size)


def write_contact(
    title: str,
    records: list[Measure],
    sample_size: int,
    seed: int,
    rule_line: str,
    destination: Path,
    ranked: bool,
    use_revised: bool = False,
) -> Path | None:
    chosen = choose_records(records, sample_size, seed, ranked)
    if not chosen:
        return None
    return draw_sheet(title, records, chosen, rule_line, destination, use_revised)


def write_pages(
    title: str,
    records: list[Measure],
    page_size: int,
    rule_line: str,
    stem: Path,
    use_revised: bool = False,
) -> list[Path]:
    usable = [item for item in records if item.image is not None and item.image.is_file()]
    if not usable:
        return []
    paths: list[Path] = []
    chunks = [usable[index:index + page_size] for index in range(0, len(usable), page_size)]
    for page, chosen in enumerate(chunks, start=1):
        suffix = "" if len(chunks) == 1 else f"_p{page:02d}"
        destination = stem.parent / f"{stem.name}{suffix}.jpg"
        drawn = draw_sheet(
            f"{title}   page {page}/{len(chunks)}",
            records,
            chosen,
            rule_line,
            destination,
            use_revised,
        )
        if drawn is not None:
            paths.append(drawn)
    return paths


def draw_sheet(
    title: str,
    records: list[Measure],
    chosen: list[Measure],
    rule_line: str,
    destination: Path,
    use_revised: bool = False,
) -> Path | None:
    if not chosen:
        return None
    columns = 5
    rows = (len(chosen) + columns - 1) // columns
    cell_w, cell_h = 320, 260
    caption_h = 48
    header_h = 96
    pad = 12
    sheet_w = columns * cell_w + (columns + 1) * pad
    sheet_h = header_h + rows * (cell_h + caption_h) + (rows + 1) * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    title_font = REORG.font(16)
    small_font = REORG.font(13)
    header = [
        f"{title}   |   {len(records)} fichiers   |   affichés {len(chosen)}",
        rule_line,
        "Graine 42 pour l'échantillon aléatoire. Polygone dessiné tel quel.",
    ]
    y = 12
    for index, line in enumerate(header):
        draw.text((pad, y), line, fill=(240, 240, 240), font=title_font if index == 0 else small_font)
        y += 26
    for index, item in enumerate(chosen):
        column = index % columns
        row = index // columns
        origin_x = pad + column * (cell_w + pad)
        origin_y = header_h + pad + row * (cell_h + caption_h + pad)
        try:
            with Image.open(item.image) as image:
                annotated = REORG.draw_annotation(image, item.label)
            cell = REORG.fit_cell(annotated, cell_w, cell_h)
            sheet.paste(cell, (origin_x, origin_y))
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            draw.rectangle([origin_x, origin_y, origin_x + cell_w, origin_y + cell_h], outline=(180, 60, 60))
        shown = item.revised if use_revised and item.revised else item.category
        label_text, label_color = PREDICTED_LABEL.get(shown, (shown, (200, 200, 200)))
        draw.rectangle([origin_x, origin_y, origin_x + cell_w, origin_y + 22], fill=label_color)
        draw.text((origin_x + 6, origin_y + 3), label_text, fill=(12, 12, 12), font=small_font)
        caption = item.image.name if item.image else item.label.name
        if len(caption) > 42:
            caption = caption[:18] + "…" + caption[-18:]
        draw.text((origin_x + 4, origin_y + cell_h + 2), caption, fill=(220, 220, 220), font=small_font)
        former = ""
        if use_revised and item.revised and item.revised != item.category:
            former_text = PREDICTED_LABEL.get(item.category, (item.category, (200, 200, 200)))[0]
            former = f"  (était {former_text})"
        draw.text(
            (origin_x + 4, origin_y + cell_h + 20),
            f"{item.format_name}  l/h={fmt(item.ratio, 2)}  aire={fmt(item.area, 4)}  {label_text}{former}",
            fill=(180, 180, 180),
            font=small_font,
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, format="JPEG", quality=85)
    return destination


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    return REORG.markdown_table(headers, rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mesure _a_trier et propose une règle. Ne copie rien.")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--contact", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    src = args.src.expanduser().resolve()
    problem = REORG.guard_paths(src)
    if problem:
        print(problem, file=sys.stderr)
        return 1

    measures, plate_ratios, plate_areas, light_ratios, light_areas = collect_measures(src)
    plate_ratio = median(plate_ratios)
    plate_area = median(plate_areas)
    light_ratio = median(light_ratios)
    light_area = median(light_areas)
    plate_low = percentile(plate_ratios, 0.10)
    light_high = percentile(light_ratios, 0.90)
    if None in (plate_ratio, plate_area, light_ratio, light_area, plate_low, light_high):
        print("Référence plaques ou feux insuffisante pour proposer une règle.", file=sys.stderr)
        return 1
    threshold_low = light_high if plate_low > light_high else light_ratio
    assign(measures, threshold_low)

    by_category = Counter(item.category for item in measures)
    contradictions = [item for item in measures if item.contradiction and item.contradiction != "géométrie absente"]
    ambiguous = sorted(
        (item for item in measures if item.ambiguity is not None),
        key=lambda item: (-(item.ambiguity or 0), REORG.relposix(item.label, src)),
    )

    measure_rows = []
    for item in measures:
        measure_rows.append({
            "source_image": "" if item.image is None else REORG.relposix(item.image, src),
            "source_label": REORG.relposix(item.label, src),
            "prefixe": item.prefix,
            "resolution": item.resolution,
            "format": item.format_name,
            "nb_lignes": item.n_lines,
            "classes": " ".join(str(class_id) for class_id in sorted(item.classes)),
            "rapport_lh_median": fmt(item.ratio, 4),
            "aire_relative_mediane": fmt(item.area, 6),
            "categorie_proposee": item.category,
            "ambiguite": fmt(item.ambiguity, 4),
            "contradiction": item.contradiction,
        })
    REORG.write_csv(
        REPORTS / "a_trier_mesures.csv",
        [
            "source_image", "source_label", "prefixe", "resolution", "format", "nb_lignes",
            "classes", "rapport_lh_median", "aire_relative_mediane", "categorie_proposee",
            "ambiguite", "contradiction",
        ],
        measure_rows,
    )

    grouped: dict[tuple[str, str], list[Measure]] = defaultdict(list)
    for item in measures:
        grouped[(item.prefix, item.resolution)].append(item)
    group_rows = []
    for (prefix, resolution), items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0][0].lower(), pair[0][1])):
        formats = Counter(item.format_name for item in items)
        group_rows.append({
            "prefixe": prefix,
            "resolution": resolution,
            "nb_fichiers": len(items),
            "rapport_lh_median": fmt(median([item.ratio for item in items if item.ratio is not None]), 4),
            "aire_relative_mediane": fmt(median([item.area for item in items if item.area is not None]), 6),
            "nb_boite": formats.get("boite", 0),
            "nb_polygone": formats.get("polygone", 0),
            "nb_mixte": formats.get("mixte", 0),
            "nb_autre": formats.get("autre", 0),
        })
    REORG.write_csv(
        REPORTS / "a_trier_groupes.csv",
        [
            "prefixe", "resolution", "nb_fichiers", "rapport_lh_median", "aire_relative_mediane",
            "nb_boite", "nb_polygone", "nb_mixte", "nb_autre",
        ],
        group_rows,
    )
    REORG.write_csv(
        REPORTS / "a_trier_contradictions.csv",
        ["source_label", "categorie_proposee", "format", "rapport_lh_median", "contradiction"],
        [{
            "source_label": REORG.relposix(item.label, src),
            "categorie_proposee": item.category,
            "format": item.format_name,
            "rapport_lh_median": fmt(item.ratio, 4),
            "contradiction": item.contradiction,
        } for item in contradictions],
    )

    rule_line = (
        f"Règle : boîte et l/h ≤ {threshold_low:.2f} → feux ; l/h > {threshold_low:.2f} → plaques ; "
        "polygone sous le seuil → incertain"
    )
    sheets: list[Path] = []
    for category in ("plates_detection", "traffic_lights", "incertain"):
        subset = [item for item in measures if item.category == category]
        path = write_contact(
            category,
            subset,
            args.contact,
            args.seed,
            rule_line,
            REPORTS / f"contact_regle_{category}.jpg",
            ranked=False,
        )
        if path is not None:
            sheets.append(path)
    ambigus_path = write_contact(
        "10 cas les plus ambigus",
        ambiguous[:10],
        10,
        args.seed,
        rule_line,
        REPORTS / "contact_regle_ambigus.jpg",
        ranked=True,
    )
    if ambigus_path is not None:
        sheets.append(ambigus_path)

    light_area_p90 = percentile(light_areas, 0.90) or light_area
    wide_reference = sum(1 for ratio in light_ratios if ratio > threshold_low)
    horizontal_reference = sum(1 for ratio in light_ratios if ratio >= 1.0)
    band = sorted(
        (item for item in measures if item.ratio is not None and 0.9 <= item.ratio <= 1.3),
        key=lambda item: (item.ratio or 0, REORG.relposix(item.label, src)),
    )
    uncertain_items = [item for item in measures if item.category == "incertain"]
    horizontal_risks = []
    for item in measures:
        if item.category != "plates_detection" or item.ratio is None:
            continue
        small_wide = any(
            box.ratio is not None and box.area is not None
            and threshold_low < box.ratio <= 2.5
            and box.area <= light_area_p90
            for box in item.boxes
        )
        s2tld_name = bool(re.fullmatch(r"\d{1,6}", item.prefix)) or item.prefix.startswith("2020-")
        if small_wide or (s2tld_name and item.ratio <= 2.5):
            horizontal_risks.append(item)
    horizontal_risks.sort(key=lambda item: (item.ratio or 0, REORG.relposix(item.label, src)))

    verif_rule = "Contrôle avant application. Boîtes dessinées, classe prévue affichée. Aucune copie."
    for category in ("plates_detection", "traffic_lights", "incertain"):
        subset = [item for item in measures if item.category == category]
        path = write_contact(
            f"contrôle {category}",
            subset,
            max(args.contact, 40),
            args.seed,
            verif_rule,
            REPORTS / f"contact_verif_{category}.jpg",
            ranked=False,
        )
        if path is not None:
            sheets.append(path)
    sheets.extend(write_pages(
        "l/h entre 0,9 et 1,3",
        band,
        40,
        verif_rule,
        REPORTS / "contact_verif_ratio_09_13",
    ))
    sheets.extend(write_pages(
        "10 incertains",
        uncertain_items,
        40,
        verif_rule,
        REPORTS / "contact_verif_incertains",
    ))
    sheets.extend(write_pages(
        "feux horizontaux possibles classés plaques",
        horizontal_risks,
        40,
        verif_rule,
        REPORTS / "contact_verif_feux_horizontaux",
    ))
    band_low = sorted(
        (item for item in measures if item.ratio is not None and 0.6 <= item.ratio <= 0.9),
        key=lambda item: (item.ratio or 0, REORG.relposix(item.label, src)),
    )
    if len(band_low) <= 60:
        band_low_shown = band_low
        band_low_note = f"toutes les {len(band_low)} images"
    else:
        picker = random.Random(args.seed)
        band_low_shown = sorted(picker.sample(band_low, 60), key=lambda item: (item.ratio or 0, REORG.relposix(item.label, src)))
        band_low_note = f"60 images au hasard sur {len(band_low)}, graine {args.seed}"
    sheets.extend(write_pages(
        f"l/h entre 0,6 et 0,9 ({band_low_note})",
        band_low_shown,
        40,
        verif_rule,
        REPORTS / "contact_verif_ratio_06_09",
    ))

    box_ratios = [
        box.ratio
        for item in measures
        for box in item.boxes
        if box.class_id == 0 and box.ratio is not None
    ]
    hist_bins = 60
    hist_counts = [0] * hist_bins
    above_six = 0
    for ratio in box_ratios:
        if ratio > 6:
            above_six += 1
            continue
        index = 59 if ratio == 6 else int(ratio / 0.1)
        if 0 <= index < hist_bins:
            hist_counts[index] += 1
    hist_path = REPORTS / "hist_ratio.png"
    write_histogram(hist_counts, hist_path)

    file_ratios = sorted(item.ratio for item in measures if item.ratio is not None)
    light_file_max = max((item.ratio for item in measures if item.prefix.isdigit() and len(item.prefix) == 6 and item.ratio is not None), default=None)
    other_file_min = min((item.ratio for item in measures if not (item.prefix.isdigit() and len(item.prefix) == 6) and item.ratio is not None), default=None)

    for item in measures:
        item.revised = revised_category(item)
    revised_counts = Counter(item.revised for item in measures)
    changed = sorted(
        (item for item in measures if item.revised != item.category),
        key=lambda item: (item.category, item.ratio or 0, REORG.relposix(item.label, src)),
    )
    revised_rule = (
        f"Règle révisée, non appliquée. Médiane l/h > {REVISED_THRESHOLD:.2f} → plaque, sinon feu. Aucune copie."
    )
    sheets.extend(write_pages(
        "changent de groupe par rapport à l/h > 1,11",
        changed,
        40,
        revised_rule,
        REPORTS / "contact_rev_changements",
        use_revised=True,
    ))
    for category in ("plates_detection", "traffic_lights", "incertain"):
        subset = [item for item in measures if item.revised == category]
        path = write_contact(
            f"règle révisée {category}",
            subset,
            40,
            args.seed,
            revised_rule,
            REPORTS / f"contact_rev_{category}.jpg",
            ranked=False,
            use_revised=True,
        )
        if path is not None:
            sheets.append(path)

    families: dict[str, list[Measure]] = defaultdict(list)
    for item in measures:
        families[family_of(item.prefix)].append(item)
    family_rows = []
    for family, items in sorted(families.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        ratios = [item.ratio for item in items if item.ratio is not None]
        counts = Counter(item.category for item in items)
        total = len(items)
        present = [name for name in ("plates_detection", "traffic_lights", "incertain") if counts[name]]
        if present == ["plates_detection"]:
            purity = "uniquement plaques"
        elif present == ["traffic_lights"]:
            purity = "uniquement feux"
        elif present == ["incertain"]:
            purity = "uniquement incertains"
        else:
            purity = "mixte"
        family_rows.append([
            family,
            total,
            fmt(sum(ratios) / len(ratios), 3) if ratios else "",
            f"{counts['plates_detection']} ({100 * counts['plates_detection'] / total:.0f} %)",
            f"{counts['traffic_lights']} ({100 * counts['traffic_lights'] / total:.0f} %)",
            f"{counts['incertain']} ({100 * counts['incertain'] / total:.0f} %)",
            purity,
        ])
    hist_rows = [
        [f"{index / 10:.1f}–{(index + 1) / 10:.1f}", hist_counts[index]]
        for index in range(hist_bins)
    ]
    hist_rows.append(["> 6", above_six])
    band_low_counts = Counter(item.category for item in band_low)
    changed_counts = Counter(f"{item.category} → {item.revised}" for item in changed)

    band_counts = Counter(item.category for item in band)

    repeated = [row for row in group_rows if int(row["nb_fichiers"]) >= 2]
    by_resolution: dict[str, list[Measure]] = defaultdict(list)
    for item in measures:
        by_resolution[item.resolution].append(item)
    resolution_rows = []
    for resolution, items in sorted(by_resolution.items(), key=lambda pair: -len(pair[1])):
        formats = Counter(item.format_name for item in items)
        resolution_rows.append([
            resolution,
            len(items),
            len({item.prefix for item in items}),
            fmt(median([item.ratio for item in items if item.ratio is not None]), 3),
            fmt(median([item.area for item in items if item.area is not None]), 5),
            formats.get("boite", 0),
            formats.get("polygone", 0),
            formats.get("mixte", 0),
        ])
    repeated_view = [[
        row["prefixe"], row["resolution"], row["nb_fichiers"], row["rapport_lh_median"],
        row["aire_relative_mediane"], row["nb_boite"], row["nb_polygone"], row["nb_mixte"],
    ] for row in repeated[:40]]

    lines = [
        "# Règle proposée pour _a_trier",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Aucun fichier n'a été copié ni déplacé.",
        "- Un polygone est converti en boîte englobante seulement pour le rapport largeur/hauteur et l'aire.",
        f"- Fichiers mesurés : {len(measures)}.",
        "",
        "## Références géométriques",
        "",
        "Plaques : toutes les boîtes des labels de `dataset/`. Feux : toutes les boîtes des labels train/valid/test déjà routés vers `traffic_lights` (rectangles qui contiennent une classe autre que 0). Les trois labels vides n'ajoutent pas de boîte.",
        "",
        f"- Plaques : {len(plate_ratios)} boîtes, l/h médian {plate_ratio:.3f} (p10 {plate_low:.3f}, p90 {percentile(plate_ratios, 0.90):.3f}), aire médiane {plate_area:.5f}.",
        f"- Feux : {len(light_ratios)} boîtes, l/h médian {light_ratio:.3f} (p10 {percentile(light_ratios, 0.10):.3f}, p90 {light_high:.3f}), aire médiane {light_area:.5f}.",
        "",
        "## Règle",
        "",
        "Le rapport largeur/hauteur sépare les références : le p90 des feux (1,11) est sous le p10 des plaques de `dataset/` (1,76). L'aire est calculée et affichée, mais elle ne décide pas : une plaque cadrée de loin a une petite aire, proche de celle d'un feu.",
        "",
        f"- `traffic_lights` si le format est une boîte et le rapport l/h médian est inférieur ou égal à {threshold_low:.3f}.",
        f"- `plates_detection` si le rapport l/h médian est supérieur à {threshold_low:.3f}. Le p10 des plaques de `dataset/` ({plate_low:.3f}) n'est pas le seuil : les plaques de `_a_trier` sont souvent moins larges que ces gros plans, tout en restant au-dessus des feux.",
        "- `incertain` si le format est un polygone et le rapport tombe du côté des feux, ou si aucune boîte mesurable n'existe. Le polygone contredit alors le seuil.",
        "- L'ambiguïté vaut 1 sur le seuil et diminue quand le rapport s'en éloigne. Elle sert à choisir les 10 cas limites.",
        "",
        "Cette règle n'est pas appliquée. `_a_trier` n'est pas réécrit.",
        "",
        "## Effectifs proposés",
        "",
        markdown_table(
            ["Catégorie", "Fichiers"],
            [[name, by_category[name]] for name in ("plates_detection", "traffic_lights", "incertain")],
        ),
        "",
        markdown_table(
            ["Format", "Plaques", "Feux", "Incertain"],
            [[
                name,
                sum(1 for item in measures if item.format_name == name and item.category == "plates_detection"),
                sum(1 for item in measures if item.format_name == name and item.category == "traffic_lights"),
                sum(1 for item in measures if item.format_name == name and item.category == "incertain"),
            ] for name in ("boite", "polygone", "mixte", "autre")],
        ),
        "",
        f"## Cas qui contredisent la règle ({len(contradictions)})",
        "",
        "Un fichier contredit le seuil s'il est un polygone dont le rapport l/h est du côté des feux, si au moins la moitié de ses boîtes est de l'autre côté du seuil, ou s'il est proposé en plaques avec une classe autre que 0. Les polygones sous le seuil sont laissés incertains.",
        "",
    ]
    if contradictions:
        lines.append(markdown_table(
            ["Label", "Proposition", "Format", "l/h", "Contradiction"],
            [[
                REORG.relposix(item.label, src),
                item.category,
                item.format_name,
                fmt(item.ratio, 3),
                item.contradiction,
            ] for item in contradictions[:30]],
        ))
        if len(contradictions) > 30:
            lines.append("")
            lines.append(f"Les {len(contradictions)} cas sont dans `reports/a_trier_contradictions.csv`.")
    else:
        lines.append("- Aucun cas en contradiction avec la règle.")
    lines += [
        "",
        "## Groupes préfixe × résolution",
        "",
        f"- Groupes : {len(group_rows)}.",
        f"- Groupes d'un seul fichier : {sum(1 for row in group_rows if int(row['nb_fichiers']) == 1)}.",
        f"- Groupes de plusieurs fichiers : {len(repeated)}.",
        "- Le préfixe est le nom avant `_jpg.rf.`. Sans ce motif, le préfixe indique `(sans _jpg.rf.)` puis le nom avant un autre `.rf.` s'il existe.",
        "- Le tableau complet est `reports/a_trier_groupes.csv`. Les mesures fichier par fichier sont dans `reports/a_trier_mesures.csv`.",
        "",
    ]
    if repeated_view:
        lines.append("Groupes de 2 fichiers ou plus (40 premiers) :")
        lines.append("")
        lines.append(markdown_table(
            ["Préfixe", "Résolution", "Fichiers", "l/h", "Aire", "Boîtes", "Polygones", "Mixtes"],
            repeated_view,
        ))
        lines.append("")
    lines += [
        "Répartition par résolution, tous préfixes confondus :",
        "",
        markdown_table(
            ["Résolution", "Fichiers", "Préfixes", "l/h", "Aire", "Boîtes", "Polygones", "Mixtes"],
            resolution_rows,
        ),
        "",
        "## Contrôle avant application",
        "",
        "Dry-run : aucune copie. Quarante images aléatoires par catégorie (graine 42), toutes les images dont le rapport l/h est entre 0,9 et 1,3, et les incertains. La classe prévue est écrite sur chaque image.",
        "",
        f"- Référence feux : {horizontal_reference} boîtes avec l/h ≥ 1 (boîtier horizontal ou carré), dont {wide_reference} au-dessus du seuil {threshold_low:.3f}. Ces boîtes, si elles étaient seules dans un fichier de classe 0, partiraient en plaques.",
        f"- Bande 0,9–1,3 : {len(band)} fichiers (plaques {band_counts['plates_detection']}, feux {band_counts['traffic_lights']}, incertains {band_counts['incertain']}).",
        f"- Risque de feu horizontal classé plaque : {len(horizontal_risks)} fichiers. Critère : proposé en plaques, et soit une boîte de l/h entre le seuil et 2,5 avec une aire ≤ p90 des feux ({light_area_p90:.5f}), soit un nom de type S2TLD avec l/h ≤ 2,5.",
        "",
        "## Planches",
        "",
        "Les planches `contact_regle_` reprennent l'échantillon de la règle. Les planches `contact_verif_` sont le contrôle demandé avant application.",
        "",
    ]
    for path in sheets:
        lines.append(f"- `{path.relative_to(PROJECT_ROOT).as_posix()}`")
    lines += [
        "",
        "## Étape 1b — seuil révisé (non appliqué)",
        "",
        "Le seuil l/h > 1,11 n'est pas validé : quatre plaques presque carrées partiraient en feux. Rien n'est copié.",
        "",
        "### Histogramme des boîtes de classe 0",
        "",
        f"Toutes les boîtes de classe 0 des fichiers de `_a_trier` : {len(box_ratios)} boîtes. Tranches de 0,1, de 0 à 6. Figure : `reports/hist_ratio.png`.",
        "",
        markdown_table(["Tranche l/h", "Boîtes"], hist_rows),
        "",
        f"- Boîtes au-dessus de 6 : {above_six}.",
        f"- Médiane de fichier la plus haute parmi les préfixes à 6 chiffres : {fmt(light_file_max, 3)}.",
        f"- Médiane de fichier la plus basse parmi les autres préfixes : {fmt(other_file_min, 3)}.",
        f"- Intervalle vide entre ces deux médianes de fichier : {fmt(light_file_max, 3)} à {fmt(other_file_min, 3)}. Aucun fichier n'a sa médiane dans cet intervalle.",
        "",
        "### Bande 0,6–0,9",
        "",
        f"{len(band_low)} images ont une médiane l/h entre 0,6 et 0,9. Planche : {band_low_note}. Classe affichée = groupe actuel (seuil 1,11).",
        "",
        f"- Plaques {band_low_counts['plates_detection']}, feux {band_low_counts['traffic_lights']}, incertains {band_low_counts['incertain']}.",
        "",
        "### Préfixe de source",
        "",
        "Le préfixe de famille regroupe les noms du même jeu (MA-2014-moped, Morocco_license_plate, marokko, identifiant numérique). Les parts sont celles des groupes actuels, seuil 1,11. Le ratio moyen est la moyenne des médianes de fichier.",
        "",
        markdown_table(
            ["Préfixe", "Fichiers", "l/h moyen", "Plaques", "Feux", "Incertains", "Pureté"],
            family_rows,
        ),
        "",
        "Un préfixe « uniquement feux » ne contient que des fichiers déjà classés feux. Un préfixe « uniquement plaques » ne contient que des fichiers déjà classés plaques. Les dix incertains sont des plaques au regard des images, mais ils restent dans la colonne Incertains de ce tableau parce que la règle 1,11 ne les a pas encore déplacés.",
        "",
        "Le seul préfixe qui ne contient que des feux, une fois les plaques carrées remises à leur place, est `id_6_chiffres` (1 211 fichiers). `Morocco_license_plate` apparaît « uniquement feux » parce que son unique fichier a un l/h de 1,004 et que le seuil 1,11 l'a envoyé en feux : c'est une des quatre plaques presque carrées. `marokko` et `MA-2014-moped` sont mixtes pour la même raison (une ou deux plaques carrées classées feux). `MA_Moped` ne contient que les deux incertains, qui sont des plaques. `id_8_chiffres` est mixte seulement à cause de sept incertains, sans aucun feu.",
        "",
        "### Règle révisée proposée",
        "",
        f"(a) Nouveau seuil : médiane l/h du fichier **supérieure à {REVISED_THRESHOLD:.2f}** → `plates_detection`, sinon `traffic_lights`. L'histogramme des {len(box_ratios)} boîtes a un vide : aucune boîte entre 0,7 et 0,8. En dessous, 2 279 boîtes (le pic est 0,2–0,3). Au-dessus, les plaques, y compris les presque carrées des tranches 0,8–1,1. Le même vide existe sur les médianes de fichier : les préfixes à 6 chiffres s'arrêtent à {fmt(light_file_max, 3)}, les autres commencent à {fmt(other_file_min, 3)}. Le 0,70 est au milieu. Le 1,11 est trop haut : il coupe dans ces plaques presque carrées et en envoie quatre en feux. Les tranches vides au-delà de 4 sont des plaques larges peu nombreuses, pas un second seuil.",
        "",
        "(b) Une règle par préfixe donne exactement le même partage sur ces 1 631 fichiers : identifiant à 6 chiffres → `traffic_lights` ; tout autre préfixe → `plates_detection`. Elle est plus sûre si un futur lot recouvre les rapports, parce qu'elle ne dépend pas d'une plaque carrée ou d'un feu un peu large. Les deux règles sont d'accord aujourd'hui. La règle de préfixe est celle à retenir si une seule règle doit décider.",
        "",
        "(c) Nouvelle répartition, non appliquée :",
        "",
        markdown_table(
            ["Catégorie", "Fichiers"],
            [[name, revised_counts[name]] for name in ("plates_detection", "traffic_lights", "incertain")],
        ),
        "",
        f"Images qui changent de groupe par rapport à l/h > 1,11 : {len(changed)}.",
        "",
    ]
    if changed_counts:
        lines.append(markdown_table(
            ["Passage", "Fichiers"],
            [[name, count] for name, count in sorted(changed_counts.items())],
        ))
        lines.append("")
    lines += [
        "Les dix fichiers aujourd'hui incertains sont des plaques. Proposition : les envoyer vers `plates_detection`. La conversion polygone → rectangle (min/max des points, normalisé entre 0 et 1) se fera plus tard dans `data/interim/`. Elle n'est pas faite ici. Les originaux restent intacts.",
        "",
        "Planches de la règle révisée : toutes les images qui changent de groupe, puis 40 images au hasard (graine 42) par nouveau groupe. Le bandeau indique la nouvelle classe. La légende rappelle l'ancienne quand elle diffère.",
        "",
    ]
    lines.extend(describe_dataset(src))
    report = REPORTS / "a_trier_regle.md"
    text = "\n".join(str(line) for line in lines) + "\n"
    with report.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"Fichiers : {len(measures)}")
    print(f"Bande 0,6-0,9 : {len(band_low)}")
    print(f"Révisé plaques/feux/incertain : {revised_counts['plates_detection']} {revised_counts['traffic_lights']} {revised_counts['incertain']}")
    print(f"Changements : {len(changed)} {dict(changed_counts)}")
    empty_bins = [f"{index / 10:.1f}" for index, count in enumerate(hist_counts) if count == 0]
    print(f"Tranches vides : {', '.join(empty_bins) if empty_bins else 'aucune'}")
    print(f"plates_detection : {by_category['plates_detection']}")
    print(f"traffic_lights : {by_category['traffic_lights']}")
    print(f"incertain : {by_category['incertain']}")
    print(f"Bande 0,9-1,3 : {len(band)} (plaques {band_counts['plates_detection']}, feux {band_counts['traffic_lights']}, incertains {band_counts['incertain']})")
    print(f"Feux horizontaux possibles : {len(horizontal_risks)}")
    print(f"Contradictions : {len(contradictions)}")
    print(f"Groupes : {len(group_rows)}")
    print(f"Rapport : {report}")
    print("Aucune copie.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    raise SystemExit(main())
