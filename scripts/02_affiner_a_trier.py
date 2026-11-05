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


def write_contact(
    title: str,
    records: list[Measure],
    sample_size: int,
    seed: int,
    rule_line: str,
    destination: Path,
    ranked: bool,
) -> Path | None:
    usable = [item for item in records if item.image is not None and item.image.is_file()]
    if not usable:
        return None
    if ranked:
        chosen = usable[:sample_size]
    elif len(usable) <= sample_size:
        chosen = usable
    else:
        chosen = random.Random(seed).sample(usable, sample_size)
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
            sheet.paste(REORG.fit_cell(annotated, cell_w, cell_h), (origin_x, origin_y))
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            draw.rectangle([origin_x, origin_y, origin_x + cell_w, origin_y + cell_h], outline=(180, 60, 60))
        caption = item.image.name if item.image else item.label.name
        if len(caption) > 42:
            caption = caption[:18] + "…" + caption[-18:]
        draw.text((origin_x + 4, origin_y + cell_h + 2), caption, fill=(220, 220, 220), font=small_font)
        score = "" if item.ambiguity is None else f"  amb={item.ambiguity:.2f}"
        draw.text(
            (origin_x + 4, origin_y + cell_h + 20),
            f"{item.format_name}  l/h={fmt(item.ratio, 2)}  aire={fmt(item.area, 4)}{score}",
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
        "## Planches",
        "",
        "Trente images aléatoires par catégorie proposée, graine 42. La planche des ambigus montre les 10 fichiers à la frontière, du plus ambigu au moins ambigu.",
        "",
    ]
    for path in sheets:
        lines.append(f"- `{path.relative_to(PROJECT_ROOT).as_posix()}`")
    lines.append("")
    lines.extend(describe_dataset(src))
    report = REPORTS / "a_trier_regle.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Fichiers : {len(measures)}")
    print(f"plates_detection : {by_category['plates_detection']}")
    print(f"traffic_lights : {by_category['traffic_lights']}")
    print(f"incertain : {by_category['incertain']}")
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
