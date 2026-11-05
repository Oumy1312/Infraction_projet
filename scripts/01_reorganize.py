#!/usr/bin/env python3
"""Étape 2 — réorganisation par copie, selon les réponses de validation.

Décisions appliquées :
- Les annotations qui n'ont que la classe 0, ainsi que les polygones, vont dans
  data/raw/_a_trier/. Rien n'est converti. Une planche contact est générée par groupe.
- Les 3 labels vides de train/ sont des images négatives : ils suivent traffic_lights.
- test_img/car.jpg et les modèles .weights/.cfg vont dans quarantine/.
- plates_chars n'est pas alimenté (dataset considéré absent).
- Les chemins ../train/images des YAML ne sont pas réutilisés.
- data.yaml, data (2).yaml, obj.names et les README vont dans data/raw/_originaux/.
- classes.txt reste avec vehicles.

Le mode par défaut est --dry-run : aucune copie. --apply copie vraiment.
--only limite la copie à vehicles, polygone, originaux, quarantine.
Le dossier source n'est jamais modifié. Un fichier déjà présent à destination est ignoré.

Exemple :

    python scripts/01_reorganize.py
    python scripts/01_reorganize.py --apply
    python scripts/01_reorganize.py --apply --only vehicles,polygone,originaux,quarantine
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import yaml
    from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
    from tqdm import tqdm
except ImportError as exc:
    print(f"Dépendance manquante : {exc}")
    print("Installez-les avec : python -m pip install -r requirements.txt")
    raise SystemExit(1)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = PROJECT_ROOT.parent / "Infraction"
RAW = PROJECT_ROOT / "data" / "raw"
QUARANTINE = PROJECT_ROOT / "quarantine"
REPORTS = PROJECT_ROOT / "reports"

MODEL_SUFFIXES = {".weights", ".pt", ".onnx", ".cfg"}
MODEL_NO_READ = {".weights", ".pt", ".onnx"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".gif"}
SPLIT_NAMES = {"train", "valid", "val", "test"}
SYSTEM_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
CLASS_LIST_NAMES = {"classes.txt", "obj.names", "obj.data"}
RF_MOTIF = "_jpg.rf."
CONTACT_SEED = 42

COLORS = (
    (255, 64, 64),
    (40, 190, 70),
    (50, 120, 255),
    (240, 180, 0),
    (220, 60, 220),
    (0, 190, 200),
    (255, 140, 40),
    (160, 90, 255),
)


def load_analyzer():
    path = Path(__file__).with_name("00_analyze_mess.py")
    spec = importlib.util.spec_from_file_location("analyze_mess", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ANALYZE = load_analyzer()


@dataclass
class Action:
    source: Path
    dest: Path | None
    category: str
    group: str
    split: str
    kind: str
    note: str = ""
    status: str = ""
    blocked: bool = False
    excluded: bool = False


@dataclass
class LabelJob:
    label: Path
    image: Path | None
    split: str
    syntax: str
    ids: set[int]
    n_boxes: int
    n_poly: int
    category: str
    group: str
    motif_rf: bool
    note: str = ""


@dataclass
class ScopeBag:
    images: list[Path] = field(default_factory=list)
    labels: list[Path] = field(default_factory=list)


def relposix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def is_model(path: Path) -> bool:
    return path.suffix.lower() in MODEL_SUFFIXES


def is_system(path: Path) -> bool:
    return path.name.lower() in SYSTEM_NAMES


def is_class_list(path: Path) -> bool:
    return path.name.lower() in CLASS_LIST_NAMES or path.suffix.lower() == ".names"


def is_readme(path: Path) -> bool:
    return path.name.lower().startswith("readme")


def is_label_file(path: Path) -> bool:
    if path.suffix.lower() != ".txt":
        return False
    if is_class_list(path) or is_readme(path):
        return False
    return True


def split_of(path: Path, top: Path) -> str:
    top_name = top.name.lower()
    if top_name in {"train", "test"}:
        return top_name
    if top_name in {"valid", "val"}:
        return "valid"
    try:
        relative = path.resolve().relative_to(top.resolve())
    except ValueError:
        return "(racine)"
    for part in relative.parts:
        lowered = part.lower()
        if lowered in SPLIT_NAMES:
            return "valid" if lowered == "val" else lowered
    return "(racine)"


def pair_parent(path: Path) -> Path:
    if path.parent.name.lower() in {"images", "labels"}:
        return path.parent.parent
    return path.parent


def motif_rf(path: Path) -> bool:
    return RF_MOTIF in path.name.lower()


def safe_group(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return cleaned.strip("._") or "groupe"


def read_roboflow_projects(src: Path) -> list[tuple[str, str]]:
    """Nom de projet du bloc roboflow, par fichier YAML. Ne lit pas les chemins pour router."""
    found: list[tuple[str, str]] = []
    for path in sorted(src.glob("*.yaml")) + sorted(src.glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
        except (OSError, yaml.YAMLError):
            found.append((path.name, "illisible"))
            continue
        if not isinstance(data, dict):
            found.append((path.name, "illisible"))
            continue
        block = data.get("roboflow")
        if isinstance(block, dict) and block.get("project"):
            found.append((path.name, str(block["project"])))
        else:
            found.append((path.name, "aucun"))
    return found


def roboflow_hint(projects: list[tuple[str, str]]) -> str:
    if not projects:
        return "aucun YAML"
    return " ; ".join(f"{name}={project}" for name, project in projects)


def class_names_from_yaml(src: Path) -> list[str]:
    path = src / "data.yaml"
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except (OSError, yaml.YAMLError):
        return []
    names = data.get("names") if isinstance(data, dict) else None
    if isinstance(names, list):
        return [str(item) for item in names]
    if isinstance(names, dict):
        return [str(names[key]) for key in sorted(names, key=lambda item: str(item))]
    return []


def read_class_lines(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def shapes_of(path: Path) -> list[tuple[str, int, list[float]]]:
    """Géométrie pour le dessin. N'est appelée que sur l'échantillon des planches."""
    try:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    shapes: list[tuple[str, int, list[float]]] = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            class_id = int(float(parts[0]))
            values = [float(piece) for piece in parts[1:]]
        except ValueError:
            continue
        if len(values) == 4:
            shapes.append(("bbox", class_id, values))
        elif len(values) >= 6 and len(values) % 2 == 0:
            shapes.append(("poly", class_id, values))
    return shapes


def route_mixed_label(split: str, info) -> tuple[str, str, str]:
    """Retourne category, group, note. La classe 0 seule n'est jamais affectée à un dataset."""
    ids = set(info.ids)
    only_zero = ids <= {0}
    if info.syntax == "vide" and split == "train":
        return "traffic_lights", "negatives", "image négative (label vide)"
    if split == "train" and info.syntax == "yolo_bbox" and ids and not only_zero:
        return "traffic_lights", "bbox_multiclasse", "classes autres que 0, rectangles YOLO"
    if info.syntax == "yolo_polygone":
        kind = "polygone"
        note = "polygone conservé tel quel, non converti"
    elif info.syntax == "yolo_bbox_et_polygone":
        kind = "mixte"
        note = "mélange rectangle et polygone, non converti"
    elif info.syntax == "vide":
        kind = "label_vide"
        note = "label vide hors du train S2TLD"
    elif info.syntax == "yolo_bbox" and only_zero:
        kind = "bbox_classe0"
        note = "classe 0 seule, non classée par défaut"
    else:
        kind = safe_group(info.syntax)
        note = "format non affecté automatiquement"
    return "_a_trier", f"{split}__{kind}", note


def dest_for_mixed(category: str, group: str, split: str, label: Path, image: Path | None) -> tuple[Path | None, Path | None]:
    if category == "traffic_lights":
        base = RAW / "traffic_lights" / split
    else:
        base = RAW / "_a_trier" / safe_group(group)
    label_dest = base / "labels" / label.name
    image_dest = None if image is None else base / "images" / image.name
    return label_dest, image_dest


def walk_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in sorted(dirnames) if name != ".git"]
        for name in sorted(filenames):
            found.append(Path(dirpath) / name)
    return found


def add_tree_actions(
    actions: list[Action],
    root: Path,
    src: Path,
    category: str,
    dest_root: Path,
) -> None:
    if not root.is_dir():
        return
    for path in walk_files(root):
        if is_system(path):
            actions.append(Action(path, None, category, "", split_of(path, root), "systeme", "fichier système ignoré"))
            continue
        relative = path.relative_to(root)
        if is_model(path):
            actions.append(Action(
                path,
                QUARANTINE / path.relative_to(src),
                "quarantine",
                "modele",
                split_of(path, root),
                "modele",
                "modèle pré-entraîné, contenu non lu" if path.suffix.lower() in MODEL_NO_READ else "configuration de modèle",
            ))
            continue
        actions.append(Action(
            path,
            dest_root / relative,
            category,
            category,
            split_of(path, root),
            "image" if is_image(path) else ("label" if is_label_file(path) else "autre"),
        ))


def index_images(folder: Path) -> dict[str, list[Path]]:
    indexed: dict[str, list[Path]] = defaultdict(list)
    if not folder.is_dir():
        return indexed
    for path in folder.iterdir():
        if path.is_file() and is_image(path):
            indexed[path.stem.casefold()].append(path)
    return indexed


def collect_scope_bags(src: Path) -> dict[tuple[str, str, Path], ScopeBag]:
    bags: dict[tuple[str, str, Path], ScopeBag] = defaultdict(ScopeBag)
    if not src.is_dir():
        return bags
    for top in src.iterdir():
        if not top.is_dir():
            continue
        for path in walk_files(top):
            if is_system(path) or is_model(path):
                continue
            key = (top.name, split_of(path, top), pair_parent(path).resolve())
            if is_image(path):
                bags[key].images.append(path)
            elif is_label_file(path):
                bags[key].labels.append(path)
    return bags


def inventory_rows(bags: dict[tuple[str, str, Path], ScopeBag]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for (top, split, _parent), bag in bags.items():
        image_stems = {path.stem.casefold() for path in bag.images}
        label_stems = {path.stem.casefold() for path in bag.labels}
        slot = grouped.setdefault( (top, split), {
            "dossier": top,
            "split": split,
            "images": 0,
            "labels": 0,
            "images_sans_label": 0,
            "labels_sans_image": 0,
            "noms": Counter(),
        })
        slot["images"] += len(bag.images)
        slot["labels"] += len(bag.labels)
        slot["images_sans_label"] += sum(1 for path in bag.images if path.stem.casefold() not in label_stems)
        slot["labels_sans_image"] += sum(1 for path in bag.labels if path.stem.casefold() not in image_stems)
        slot["noms"].update(path.name.casefold() for path in bag.images)
        slot["noms"].update(path.name.casefold() for path in bag.labels)
    rows = []
    for key in sorted(grouped):
        slot = grouped[key]
        names: Counter = slot["noms"]
        duplicates = sorted(name for name, count in names.items() if count > 1)
        rows.append({
            "dossier": slot["dossier"],
            "split": slot["split"],
            "images": slot["images"],
            "labels": slot["labels"],
            "images_sans_label": slot["images_sans_label"],
            "labels_sans_image": slot["labels_sans_image"],
            "doublons": len(duplicates),
            "exemples_doublons": ", ".join(duplicates[:8]),
        })
    return rows


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = [str(cell).replace("|", "\\|").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def font(size: int) -> ImageFont.ImageFont:
    for candidate in (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"):
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def draw_annotation(image: Image.Image, label: Path) -> Image.Image:
    canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    width, height = canvas.size
    stroke = max(2, min(width, height) // 180)
    for kind, class_id, values in shapes_of(label):
        color = COLORS[class_id % len(COLORS)]
        if kind == "bbox":
            center_x, center_y, box_w, box_h = values
            x0 = (center_x - box_w / 2) * width
            y0 = (center_y - box_h / 2) * height
            x1 = (center_x + box_w / 2) * width
            y1 = (center_y + box_h / 2) * height
            draw.rectangle([x0, y0, x1, y1], outline=(0, 0, 0), width=stroke + 2)
            draw.rectangle([x0, y0, x1, y1], outline=color, width=stroke)
        else:
            points = [(values[index] * width, values[index + 1] * height) for index in range(0, len(values), 2)]
            if len(points) >= 2:
                draw.line(points, fill=(0, 0, 0), width=stroke + 2)
                draw.line(points, fill=color, width=stroke)
            radius = stroke + 1
            for point_x, point_y in points:
                draw.ellipse(
                    (point_x - radius, point_y - radius, point_x + radius, point_y + radius),
                    outline=color,
                    width=max(1, stroke // 2),
                )
    return canvas


def fit_cell(image: Image.Image, cell_w: int, cell_h: int) -> Image.Image:
    plate = Image.new("RGB", (cell_w, cell_h), (32, 32, 32))
    thumb = image.copy()
    thumb.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
    plate.paste(thumb, ((cell_w - thumb.width) // 2, (cell_h - thumb.height) // 2))
    return plate


def write_contact_sheet(
    group: str,
    jobs: list[LabelJob],
    hint: str,
    sample_size: int,
    seed: int,
) -> Path | None:
    usable = [job for job in jobs if job.image is not None and job.image.is_file()]
    if not usable:
        return None
    rng = random.Random(seed)
    chosen = usable if len(usable) <= sample_size else rng.sample(usable, sample_size)
    columns = 5
    rows = (len(chosen) + columns - 1) // columns
    cell_w, cell_h = 320, 260
    caption_h = 36
    header_h = 118
    pad = 8
    sheet_w = columns * cell_w + (columns + 1) * pad
    sheet_h = header_h + rows * (cell_h + caption_h) + (rows + 1) * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    title_font = font(18)
    small_font = font(14)
    poly_files = sum(1 for job in jobs if job.n_poly)
    poly_lines = sum(job.n_poly for job in jobs)
    rf_count = sum(1 for job in jobs if job.motif_rf)
    header = [
        f"{group}   |   {len(jobs)} fichiers   |   échantillon {len(chosen)} (graine {seed})",
        f"polygones : {poly_files} fichiers, {poly_lines} lignes, aucune conversion",
        f"motif {RF_MOTIF} : {rf_count}/{len(jobs)}",
        f"roboflow (indice, non utilisé pour classer) : {hint}",
    ]
    y = 10
    for line in header:
        draw.text((pad, y), line, fill=(240, 240, 240), font=title_font if y == 10 else small_font)
        y += 26
    for index, job in enumerate(chosen):
        column = index % columns
        row = index // columns
        origin_x = pad + column * (cell_w + pad)
        origin_y = header_h + pad + row * (cell_h + caption_h + pad)
        try:
            with Image.open(job.image) as image:
                annotated = draw_annotation(image, job.label)
            cell = fit_cell(annotated, cell_w, cell_h)
            sheet.paste(cell, (origin_x, origin_y))
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            draw.rectangle([origin_x, origin_y, origin_x + cell_w, origin_y + cell_h], outline=(180, 60, 60))
            draw.text((origin_x + 8, origin_y + 8), f"illisible ({type(exc).__name__})", fill=(255, 180, 180), font=small_font)
        caption = job.image.name
        if len(caption) > 42:
            caption = caption[:20] + "…" + caption[-20:]
        draw.text((origin_x + 4, origin_y + cell_h + 4), caption, fill=(220, 220, 220), font=small_font)
        kind = "polygone" if job.n_poly else "rectangle"
        draw.text(
            (origin_x + 4, origin_y + cell_h + 20),
            f"{kind}  classes={','.join(str(item) for item in sorted(job.ids)) or 'vide'}",
            fill=(180, 180, 180),
            font=small_font,
        )
    destination = REPORTS / f"contact_{safe_group(group)}.jpg"
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, format="JPEG", quality=85)
    return destination


def mark_duplicate_destinations(actions: list[Action]) -> None:
    seen: dict[str, Action] = {}
    for action in actions:
        if action.dest is None:
            continue
        key = str(action.dest).casefold()
        previous = seen.get(key)
        if previous is None:
            seen[key] = action
            continue
        action.blocked = True
        action.note = (action.note + " ; " if action.note else "") + f"même destination que {previous.source.name}"


def action_selected(action: Action, only: set[str]) -> bool:
    """Sélection d'un --apply partiel. polygone = groupes polygone purs, pas les mixtes."""
    if action.category == "vehicles" and "vehicles" in only:
        return True
    if action.category == "_originaux" and "originaux" in only:
        return True
    if action.category == "quarantine" and "quarantine" in only:
        return True
    if "polygone" in only and action.category == "_a_trier" and "polygone" in action.group.split("__"):
        return True
    return False


def execute(actions: list[Action], apply: bool, src: Path) -> None:
    iterable = tqdm(actions, desc="Copie", unit="fichier") if apply else actions
    for action in iterable:
        if action.excluded:
            action.status = "hors sélection, non copié"
            continue
        if action.blocked:
            action.status = "collision de destination, non copié"
            continue
        if action.dest is None:
            action.status = "non copié"
            continue
        if is_inside(action.dest, src):
            action.status = "refusé (destination dans la source)"
            continue
        if not is_inside(action.dest, PROJECT_ROOT):
            action.status = "refusé (destination hors du projet)"
            continue
        if action.dest.exists():
            action.status = "existe déjà, ignoré"
            continue
        if not apply:
            action.status = "dry-run"
            continue
        try:
            action.dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(action.source, action.dest)
            action.status = "copié"
        except OSError as exc:
            action.status = f"erreur: {exc}"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_datasets_md(
    src: Path,
    actions: list[Action],
    jobs: list[LabelJob],
    mode: str,
) -> str:
    def image_count(category: str) -> int:
        return sum(1 for action in actions if action.category == category and action.kind == "image" and action.dest is not None)

    light_names = class_names_from_yaml(src)
    vehicle_names = read_class_lines(src / "vehicle dataset" / "classes.txt")
    plate_names = read_class_lines(src / "obj.names") or ["license_plate"]
    negatives = [job for job in jobs if job.note.startswith("image négative")]
    lines = [
        "# Datasets",
        "",
        f"- Mode du dernier passage : {mode}",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Les comptes d'images sont ceux du plan de copie (fichiers prévus, ou copiés si `--apply`).",
        "- La licence est laissée à « à vérifier » tant qu'elle n'a pas été confirmée hors du fichier YAML.",
        "- `data/raw/plates_chars/` n'est pas alimenté : le dataset caractères est considéré absent.",
        "",
        "## Vehicle Dataset for YOLO",
        "",
        "- Lien : à vérifier (Kaggle)",
        "- Dossier local : `data/raw/vehicles/`",
        f"- Classes : {', '.join(vehicle_names) if vehicle_names else 'à vérifier'}",
        f"- Images : {image_count('vehicles')}",
        "- Licence : à vérifier",
        "- `classes.txt` est copié avec ce dossier.",
        "",
        "## S2TLD",
        "",
        "- Lien : https://universe.roboflow.com/hellosongdo/s2tld/dataset/1",
        "- Dossier local : `data/raw/traffic_lights/`",
        f"- Classes : {', '.join(light_names) if light_names else 'à vérifier'}",
        f"- Images : {image_count('traffic_lights')} (rectangles avec au moins une classe autre que 0, plus {len(negatives)} image(s) négative(s))",
        "- Licence : à vérifier",
        "- Le YAML d'origine mentionne CC BY 4.0. Ce n'est pas repris comme licence confirmée.",
        "- Les fichiers qui n'ont que la classe 0 ne sont pas dans ce dossier.",
        "",
        "## Moroccan License Plate Detection",
        "",
        "- Lien : à vérifier (Kaggle)",
        "- Dossier local : `data/raw/plates_detection/`",
        f"- Classes : {', '.join(plate_names)}",
        f"- Images : {image_count('plates_detection')}",
        "- Licence : à vérifier",
        "- Organisation d'origine conservée : image et annotation côte à côte (Darknet).",
        "",
        "## Moroccan Vehicle Registration Plates (caractères)",
        "",
        "- Lien : à vérifier (Kaggle)",
        "- Dossier local : aucun. Dataset considéré absent tant qu'il n'est pas confirmé.",
        "- Classes : —",
        "- Images : 0",
        "- Licence : à vérifier",
        "",
        "## Fichiers laissés à trier",
        "",
        "- Dossier local : `data/raw/_a_trier/`",
        f"- Images : {image_count('_a_trier')}",
        "- Détail : `reports/a_trier.csv` et `reports/contact_*.jpg`",
        "- Les polygones sont copiés sans conversion.",
        "",
        "## Originaux et quarantaine",
        "",
        "- YAML, `obj.names` et README : `data/raw/_originaux/`",
        "- Poids, configurations et `test_img/car.jpg` : `quarantine/`",
        "",
    ]
    return "\n".join(lines)


def build_inventory_md(rows: list[dict[str, object]], actions: list[Action]) -> str:
    source_table = markdown_table(
        ["Dossier", "Split", "Images", "Labels", "Images sans label", "Labels sans image", "Noms en doublon", "Exemples"],
        [[
            row["dossier"], row["split"], row["images"], row["labels"],
            row["images_sans_label"], row["labels_sans_image"], row["doublons"], row["exemples_doublons"] or "—",
        ] for row in rows],
    )
    planned: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for action in actions:
        if action.kind not in {"image", "label"} or action.dest is None:
            continue
        planned[(action.category, action.split or "(racine)")][action.kind] += 1
    planned_rows = [
        [category, split, counts["image"], counts["label"]]
        for (category, split), counts in sorted(planned.items())
    ]
    planned_table = markdown_table(
        ["Destination", "Split", "Images prévues", "Labels prévus"],
        planned_rows,
    )
    return "\n".join([
        "# Inventaire par dossier et par split",
        "",
        f"Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "Comptes lus dans le dossier source. Un doublon est un même nom de fichier répété dans le même dossier et le même split.",
        "",
        source_table,
        "",
        "## Répartition prévue",
        "",
        planned_table,
        "",
    ])


def build_rapport(
    src: Path,
    mode: str,
    actions: list[Action],
    jobs: list[LabelJob],
    projects: list[tuple[str, str]],
    sheets: list[Path],
    rows: list[dict[str, object]],
    only: set[str] | None = None,
) -> str:
    by_status = Counter(action.status for action in actions)
    by_category = Counter(action.category for action in actions if action.kind == "image" and action.dest is not None)
    negatives = [job for job in jobs if job.note.startswith("image négative")]
    poly_jobs = [job for job in jobs if job.n_poly]
    unsorted = [job for job in jobs if job.category == "_a_trier"]
    lines = [
        "# Rapport de réorganisation",
        "",
        f"- Source : `{src}`",
        f"- Mode : {mode}",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Le dossier source n'est pas modifié. Les copies n'ont lieu qu'avec `--apply`.",
        "- Un fichier déjà présent à destination est ignoré.",
        "",
    ]
    if only:
        lines += [
            f"- Sélection `--only` : {', '.join(sorted(only))}.",
            "- Les polygones purs vont dans leur dossier prévu sous `data/raw/_a_trier/`.",
            "- Les boîtes de classe 0 et les fichiers mixtes de `_a_trier` ne sont pas copiés.",
            "- `traffic_lights`, `plates_detection` et `plates_chars` ne sont pas copiés par cette sélection.",
            "",
        ]
    lines += [
        "## Volumes d'images prévus",
        "",
        markdown_table(
            ["Destination", "Images"],
            [[name, count] for name, count in sorted(by_category.items())],
        ),
        "",
        "## Statuts",
        "",
        markdown_table(
            ["Statut", "Fichiers"],
            [[name, count] for name, count in sorted(by_status.items())],
        ),
        "",
        "## Images négatives",
        "",
        "Les labels vides du split train sont conservés avec les feux (images négatives).",
        "",
    ]
    if negatives:
        for job in negatives:
            image_name = job.image.name if job.image else "(image absente)"
            lines.append(f"- `{relposix(job.label, src)}` — image `{image_name}` — motif `{RF_MOTIF}` : {'oui' if job.motif_rf else 'non'}")
    else:
        lines.append("- Aucun label vide dans train/.")
    lines += [
        "",
        "## Polygones",
        "",
        f"- Fichiers contenant au moins un polygone : {len(poly_jobs)}",
        f"- Lignes de polygone : {sum(job.n_poly for job in poly_jobs)}",
        "- Aucune conversion en rectangle n'a été faite. Les fichiers sont copiés tels quels dans `data/raw/_a_trier/`.",
        "",
        "## Classe 0 laissée à trier",
        "",
        f"- Fichiers d'annotation : {len(unsorted)}",
        f"- Indice roboflow lu dans les YAML, non utilisé pour choisir le dataset : {roboflow_hint(projects)}",
        f"- Le motif `{RF_MOTIF}` est noté dans `reports/a_trier.csv` et sur les planches.",
        "",
        "Planches contact :",
        "",
    ]
    if sheets:
        for path in sheets:
            lines.append(f"- `{path.relative_to(PROJECT_ROOT).as_posix()}`")
    else:
        lines.append("- Aucune planche (pas d'image dans les groupes à trier).")
    lines += [
        "",
        "## Inventaire source (résumé)",
        "",
        markdown_table(
            ["Dossier", "Split", "Images", "Labels", "Sans label", "Sans image", "Doublons"],
            [[
                row["dossier"], row["split"], row["images"], row["labels"],
                row["images_sans_label"], row["labels_sans_image"], row["doublons"],
            ] for row in rows],
        ),
        "",
        "Le détail des noms en doublon est dans `reports/inventaire_splits.md`.",
        "",
    ]
    return "\n".join(lines) + "\n"


def guard_paths(src: Path) -> str | None:
    if not src.is_dir():
        return f"Dossier source introuvable : {src}"
    if src.resolve() == PROJECT_ROOT.resolve() or is_inside(PROJECT_ROOT, src):
        return "La source ne doit pas contenir le projet de destination."
    if is_inside(src, PROJECT_ROOT):
        return "La source ne doit pas être à l'intérieur du projet."
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copie les datasets mélangés vers Infraction_projet. Défaut : dry-run.")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="Dossier source. Défaut : Infraction à côté du projet.")
    parser.add_argument("--dry-run", action="store_true", help="Simule les copies (défaut si --apply est absent).")
    parser.add_argument("--apply", action="store_true", help="Effectue les copies.")
    parser.add_argument(
        "--only",
        default="",
        help="Copie partielle : vehicles, polygone, originaux, quarantine (séparés par des virgules).",
    )
    parser.add_argument("--contact", type=int, default=20, help="Images par planche contact.")
    parser.add_argument("--seed", type=int, default=CONTACT_SEED, help="Graine de l'échantillon des planches.")
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        print("Choisissez un seul mode : --dry-run ou --apply.", file=sys.stderr)
        return 2
    apply = bool(args.apply)
    allowed_only = {"vehicles", "polygone", "originaux", "quarantine"}
    only = {part.strip().lower() for part in args.only.split(",") if part.strip()}
    unknown = only - allowed_only
    if unknown:
        print(f"Valeur --only inconnue : {', '.join(sorted(unknown))}.", file=sys.stderr)
        return 2
    mode = "apply" if apply else "dry-run"
    if only:
        mode += " (only: " + ", ".join(sorted(only)) + ")"

    src = args.src.expanduser().resolve()
    problem = guard_paths(src)
    if problem:
        print(problem, file=sys.stderr)
        return 1

    projects = read_roboflow_projects(src)
    hint = roboflow_hint(projects)
    actions: list[Action] = []
    jobs: list[LabelJob] = []

    for path in sorted(src.iterdir(), key=lambda item: item.name.lower()):
        if path.is_file():
            if is_system(path):
                actions.append(Action(path, None, "ignore", "", "(racine)", "systeme", "fichier système ignoré"))
            elif is_model(path):
                note = "poids non lu" if path.suffix.lower() in MODEL_NO_READ else "configuration de modèle"
                actions.append(Action(path, QUARANTINE / path.name, "quarantine", "modele", "(racine)", "modele", note))
            elif path.suffix.lower() in {".yaml", ".yml"} or is_readme(path) or path.name.lower() == "obj.names":
                actions.append(Action(path, RAW / "_originaux" / path.name, "_originaux", "meta", "(racine)", "meta", "copie de traçabilité, chemins YAML non réutilisés"))
            else:
                actions.append(Action(path, None, "ignore", "", "(racine)", "autre", "fichier racine non prévu"))

    known = {"dataset", "test", "test_img", "train", "valid", "vehicle dataset"}
    for path in src.iterdir():
        if path.is_dir() and path.name not in known:
            actions.append(Action(path, None, "ignore", "", "(racine)", "dossier", "dossier non prévu, non copié"))

    add_tree_actions(actions, src / "vehicle dataset", src, "vehicles", RAW / "vehicles")
    add_tree_actions(actions, src / "dataset", src, "plates_detection", RAW / "plates_detection")

    test_img = src / "test_img"
    if test_img.is_dir():
        for path in walk_files(test_img):
            actions.append(Action(
                path,
                QUARANTINE / path.relative_to(src),
                "quarantine",
                "test_img",
                "(racine)",
                "image" if is_image(path) else "autre",
                "image isolée sans annotation",
            ))

    label_cache: dict[Path, object] = {}
    label_files = [
        path for path in walk_files(src)
        if is_label_file(path) and path.relative_to(src).parts[0] in {"train", "valid", "test"}
    ]
    for path in tqdm(label_files, desc="Annotations train/valid/test", unit="fichier"):
        label_cache[path.resolve()] = ANALYZE.classify_txt(path)

    for split in ("train", "valid", "test"):
        labels_dir = src / split / "labels"
        images_dir = src / split / "images"
        if not labels_dir.is_dir():
            continue
        images = index_images(images_dir)
        used_stems: set[str] = set()
        label_paths = sorted((path for path in labels_dir.iterdir() if path.is_file() and is_label_file(path)), key=lambda item: item.name.lower())
        for label in label_paths:
            info = label_cache.get(label.resolve())
            if info is None:
                info = ANALYZE.classify_txt(label)
            category, group, note = route_mixed_label(split, info)
            if category == "_a_trier" and motif_rf(label):
                group = f"{group}__rf"
            elif category == "_a_trier":
                group = f"{group}__sans_rf"
            matches = images.get(label.stem.casefold(), [])
            image = matches[0] if matches else None
            used_stems.add(label.stem.casefold())
            label_dest, image_dest = dest_for_mixed(category, group, split, label, image)
            ids = set(info.ids)
            note_out = note if image is not None else f"{note} ; label sans image"
            job = LabelJob(
                label=label,
                image=image,
                split=split,
                syntax=info.syntax,
                ids=ids,
                n_boxes=info.n_boxes,
                n_poly=info.n_poly_lines,
                category=category,
                group=group,
                motif_rf=motif_rf(label),
                note=note,
            )
            jobs.append(job)
            job.note = note_out
            actions.append(Action(label, label_dest, category, group, split, "label", note_out))
            if image is not None:
                actions.append(Action(image, image_dest, category, group, split, "image", note))
            for extra in matches[1:]:
                extra_dest = None if image_dest is None else image_dest.parent / extra.name
                actions.append(Action(extra, extra_dest, category, group, split, "image", "autre extension du même stem"))
        if images_dir.is_dir():
            for path in sorted(images_dir.iterdir(), key=lambda item: item.name.lower()):
                if path.is_file() and is_image(path) and path.stem.casefold() not in used_stems:
                    actions.append(Action(path, None, "ignore", "", split, "image", "image sans label, non copiée"))

    extra_poly = 0
    extra_poly_files = 0
    other_labels = [
        path for path in walk_files(src)
        if is_label_file(path) and path.relative_to(src).parts[0] not in {"train", "valid", "test"}
    ]
    for path in tqdm(other_labels, desc="Contrôle polygones autres dossiers", unit="fichier"):
        info = ANALYZE.classify_txt(path)
        if info.n_poly_lines:
            extra_poly += info.n_poly_lines
            extra_poly_files += 1

    mark_duplicate_destinations(actions)
    if only:
        for action in actions:
            if action.dest is not None and not action_selected(action, only):
                action.excluded = True
                action.note = (action.note + " ; " if action.note else "") + "hors sélection --only, non copié"
    execute(actions, apply, src)

    sheets: list[Path] = []
    grouped_jobs: dict[str, list[LabelJob]] = defaultdict(list)
    for job in jobs:
        if job.category == "_a_trier":
            grouped_jobs[job.group].append(job)
    for group in sorted(grouped_jobs):
        sheet = write_contact_sheet(group, grouped_jobs[group], hint, args.contact, args.seed)
        if sheet is not None:
            sheets.append(sheet)

    log_rows = [{
        "source": relposix(action.source, src),
        "destination": "" if action.dest is None else action.dest.relative_to(PROJECT_ROOT).as_posix(),
        "statut": action.status,
        "categorie": action.category,
        "groupe": action.group,
        "note": action.note,
    } for action in actions]
    write_csv(
        REPORTS / "reorganisation_log.csv",
        ["source", "destination", "statut", "categorie", "groupe", "note"],
        log_rows,
    )

    a_trier_rows = []
    for job in jobs:
        if job.category != "_a_trier":
            continue
        label_dest, image_dest = dest_for_mixed(job.category, job.group, job.split, job.label, job.image)
        a_trier_rows.append({
            "source_image": "" if job.image is None else relposix(job.image, src),
            "source_label": relposix(job.label, src),
            "destination_image": "" if image_dest is None else image_dest.relative_to(PROJECT_ROOT).as_posix(),
            "destination_label": "" if label_dest is None else label_dest.relative_to(PROJECT_ROOT).as_posix(),
            "groupe": job.group,
            "split": job.split,
            "format": job.syntax,
            "classes": " ".join(str(item) for item in sorted(job.ids)),
            "nb_boites": job.n_boxes,
            "nb_polygones": job.n_poly,
            "motif_jpg_rf": "oui" if job.motif_rf else "non",
            "projet_roboflow": hint,
            "note": job.note,
        })
    write_csv(
        REPORTS / "a_trier.csv",
        [
            "source_image", "source_label", "destination_image", "destination_label",
            "groupe", "split", "format", "classes", "nb_boites", "nb_polygones",
            "motif_jpg_rf", "projet_roboflow", "note",
        ],
        a_trier_rows,
    )

    bags = collect_scope_bags(src)
    rows = inventory_rows(bags)
    inventory = build_inventory_md(rows, actions)
    if extra_poly:
        inventory += (
            f"\nPolygones hors train/valid/test : {extra_poly_files} fichiers, "
            f"{extra_poly} lignes. Ils restent dans leur dossier d'origine prévu, sans conversion.\n"
        )
    (REPORTS / "inventaire_splits.md").write_text(inventory, encoding="utf-8", newline="\n")
    rapport = build_rapport(src, mode, actions, jobs, projects, sheets, rows, only or None)
    (REPORTS / "reorganisation_rapport.md").write_text(rapport, encoding="utf-8", newline="\n")
    (PROJECT_ROOT / "DATASETS.md").write_text(
        build_datasets_md(src, actions, jobs, mode),
        encoding="utf-8",
        newline="\n",
    )

    print(f"Mode : {mode}")
    print(f"Source : {src}")
    print(f"Actions : {len(actions)}")
    print(f"À trier : {sum(1 for job in jobs if job.category == '_a_trier')} annotations")
    print(f"Images négatives : {sum(1 for job in jobs if job.note.startswith('image négative'))}")
    print(f"Planches : {len(sheets)}")
    print(f"Journal : {REPORTS / 'reorganisation_log.csv'}")
    if apply:
        copied = sum(1 for action in actions if action.status == "copié")
        skipped = sum(1 for action in actions if action.status == "hors sélection, non copié")
        print(f"Copies effectuées : {copied}. Hors sélection : {skipped}.")
    else:
        print("Aucune copie. Relancer avec --apply pour copier.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    raise SystemExit(main())
