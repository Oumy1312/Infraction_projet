#!/usr/bin/env python3
"""Étape 1 — analyse sèche d'un dossier de datasets YOLO mélangés.

Lit le dossier source et écrit un plan Markdown. Ne copie, ne déplace,
ne modifie et ne supprime aucun fichier du dossier source.
N'ouvre jamais les poids .weights, .pt ou .onnx (taille disque seulement).

Exemple, depuis la racine de Infraction_projet :

    python scripts/00_analyze_mess.py
    python scripts/00_analyze_mess.py --src "C:\\Users\\user\\Desktop\\Infraction"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import yaml
    from PIL import Image, UnidentifiedImageError
    from tqdm import tqdm
except ImportError as exc:
    print(f"Dépendance manquante : {exc}")
    print("Installez-les avec : python -m pip install -r requirements.txt")
    raise SystemExit(1)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = PROJECT_ROOT.parent / "Infraction"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "reorganisation_plan.md"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".gif"}
ANNO_EXTS = {".txt", ".xml", ".json"}
MODEL_NO_READ = {".weights", ".pt", ".onnx"}
MODEL_EXTS = MODEL_NO_READ | {".cfg"}
CLASS_LIST_NAMES = {"classes.txt", "obj.names", "obj.data"}
SYSTEM_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}

VEHICLE_TOKENS = {
    "car", "bus", "truck", "motorcycle", "motorbike", "bike", "van",
    "threewheel", "suv", "pickup", "auto", "voiture", "camion", "moto",
}
LIGHT_COLORS = {"red", "green", "yellow", "amber"}
LIGHT_STATES = {"go", "stop", "warn", "wait", "off", "wait_on"}
PLATE_TOKENS = {
    "plate", "license", "license_plate", "licence", "licence_plate",
    "plaque", "matricule", "numberplate", "number_plate",
}

DATASETS = ("vehicles", "traffic_lights", "plates_detection", "plates_chars")
CLASS_LINE = re.compile(r"(?m)^classes\s*=\s*(\d+)\s*$")
IMAGE_COUNT_RE = re.compile(r"(\d[\d \u00a0]*)\s+images\b", re.IGNORECASE)
README_SKIP = (
    "collaborate",
    "collect &",
    "understand and search",
    "annotate, and",
    "export, train",
    "active learning",
    "notebooks you can use",
    "100k other",
)


@dataclass
class DirStats:
    files: int = 0
    images: int = 0
    annos: int = 0
    size: int = 0
    exts: Counter = field(default_factory=Counter)
    direct_images: int = 0
    direct_annos: int = 0


@dataclass
class SeenFile:
    path: Path
    size: int


@dataclass
class DeclaredPath:
    key: str
    raw: str
    candidates: list[tuple[str, Path, bool]]


@dataclass
class ClassSource:
    path: Path
    kind: str
    names: list[str]
    declared: list[DeclaredPath] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)
    anchor: Path = field(default_factory=Path)


@dataclass
class AnnoInfo:
    syntax: str
    ids: Counter = field(default_factory=Counter)
    n_boxes: int = 0
    example_line: str = ""
    point_counts: Counter = field(default_factory=Counter)
    n_closed: int = 0
    n_poly_lines: int = 0
    extra_names: list[str] = field(default_factory=list)


@dataclass
class Group:
    directory: Path
    syntax: str
    n_files: int = 0
    n_boxes: int = 0
    ids: Counter = field(default_factory=Counter)
    stems: set[str] = field(default_factory=set)
    examples: list[str] = field(default_factory=list)
    example_line: str = ""
    patterns: Counter = field(default_factory=Counter)
    point_counts: Counter = field(default_factory=Counter)
    n_closed: int = 0
    n_poly_lines: int = 0
    matched_images: int = 0
    unmatched_labels: int = 0
    target: str = "incertain"
    confidence: str = "faible"
    reasons: list[str] = field(default_factory=list)
    conflict: bool = False

    @property
    def union(self) -> set[int]:
        return set(self.ids)


@dataclass
class LabelDir:
    path: Path
    layout: str
    image_dir: Path
    n_images: int = 0
    images_without_label: int = 0
    orphan_image_examples: list[str] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    pillow: list[str] = field(default_factory=list)


@dataclass
class ModelFile:
    path: Path
    size: int
    note: str


@dataclass
class ImageOnly:
    path: Path
    n_images: int
    examples: list[str]
    pillow: list[str]
    target: str = "incertain"
    confidence: str = "faible"
    reasons: list[str] = field(default_factory=list)


def plural(count: int, singular: str, plural_form: str) -> str:
    return f"{count} {singular if count == 1 else plural_form}"


def human_size(num: int) -> str:
    value = float(num)
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if value < 1024 or unit == "To":
            if unit == "o":
                return f"{int(value)} o"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num} o"


def md(value: object) -> str:
    if value is None:
        text = "—"
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


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


def read_text_capped(path: Path, limit: int) -> str:
    """Lit du texte. Refuse les poids de modèle."""
    if path.suffix.lower() in MODEL_NO_READ:
        raise RuntimeError(f"Refus de lire un fichier de poids : {path}")
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        return handle.read(limit)


def is_class_list(path: Path) -> bool:
    return path.name.lower() in CLASS_LIST_NAMES or path.suffix.lower() == ".names"


def is_readme(path: Path) -> bool:
    return path.name.lower().startswith("readme")


def is_annotation(path: Path) -> bool:
    if path.suffix.lower() not in ANNO_EXTS:
        return False
    if is_class_list(path) or is_readme(path):
        return False
    return True


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def fmt_exts(counter: Counter) -> str:
    if not counter:
        return "—"
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{ext} ({count})" for ext, count in items)


def fmt_ids(counter: Counter) -> str:
    if not counter:
        return "aucune"
    items = sorted(counter)
    if len(items) <= 24:
        return ", ".join(f"{index}×{counter[index]}" for index in items)
    return f"{len(items)} ids distincts, min {items[0]}, max {items[-1]}"


def fmt_names(names: list[str], limit: int = 40) -> str:
    if not names:
        return "(aucune)"
    shown = names[:limit]
    text = ", ".join(shown)
    if len(names) > limit:
        text += f", … ({len(names)} au total)"
    return text


def filename_pattern(name: str) -> str:
    lower = name.lower()
    if ".rf." in lower:
        return "Roboflow (.rf.)"
    if "whatsapp" in lower or re.search(r"(^|[^a-z])wa\d+", lower):
        return "WhatsApp (WA)"
    return "autre"


def token_set(names: list[str]) -> set[str]:
    tokens: set[str] = set()
    for name in names:
        base = name.strip().lower()
        if not base:
            continue
        tokens.add(base)
        tokens.add(base.replace(" ", "_").replace("-", "_"))
        for part in re.split(r"[\s_\-]+", base):
            if part:
                tokens.add(part)
    return tokens


def looks_like_characters(names: list[str]) -> bool:
    if len(names) < 8:
        return False
    short = [name.strip() for name in names if len(name.strip()) <= 2]
    alnum = [name for name in short if name.isalnum()]
    return len(alnum) >= 8 and len(alnum) / len(names) >= 0.6


def name_scores(names: list[str]) -> tuple[Counter, list[str]]:
    scores: Counter = Counter()
    reasons: list[str] = []
    if not names:
        return scores, reasons
    tokens = token_set(names)
    vehicle_hits = sorted(tokens & VEHICLE_TOKENS)
    color_hits = sorted(tokens & LIGHT_COLORS)
    state_hits = sorted(tokens & LIGHT_STATES)
    plate_hits = sorted((tokens & PLATE_TOKENS) | {name for name in tokens if name in PLATE_TOKENS})
    if len(vehicle_hits) >= 2:
        scores["vehicles"] += 3 + len(vehicle_hits)
        reasons.append("classes de véhicules : " + ", ".join(vehicle_hits))
    if len(color_hits) >= 2:
        scores["traffic_lights"] += 4 + len(color_hits)
        reasons.append("couleurs de feux : " + ", ".join(color_hits))
    if color_hits and state_hits:
        scores["traffic_lights"] += 2
        reasons.append("états de feux : " + ", ".join(sorted(state_hits)))
    if plate_hits and len(names) == 1:
        scores["plates_detection"] += 5
        reasons.append(f"une seule classe de plaque : {names[0]}")
    elif plate_hits:
        scores["plates_detection"] += 3
        reasons.append("classes de plaque : " + ", ".join(plate_hits))
    if looks_like_characters(names):
        scores["plates_chars"] += 5
        reasons.append("noms très courts (chiffres ou lettres), typiques des caractères de plaque")
    return scores, reasons


def folder_scores(relative_text: str) -> tuple[Counter, list[str]]:
    text = relative_text.lower()
    scores: Counter = Counter()
    reasons: list[str] = []
    if any(token in text for token in ("vehicle", "vehicule", "véhicule")):
        scores["vehicles"] += 4
        reasons.append("le chemin du dossier contient « vehicle »")
    if any(token in text for token in ("traffic", "s2tld", "feu")):
        scores["traffic_lights"] += 3
        reasons.append("le chemin du dossier évoque les feux tricolores")
    if any(token in text for token in ("char", "ocr", "alphabet", "digit")):
        scores["plates_chars"] += 3
        reasons.append("le chemin du dossier évoque des caractères")
    elif any(token in text for token in ("plate", "license", "licence", "plaque")):
        scores["plates_detection"] += 3
        reasons.append("le chemin du dossier évoque des plaques")
    return scores, reasons


def primary_target(names: list[str]) -> str:
    scores, _reasons = name_scores(names)
    if not scores:
        return "incertain"
    ranking = scores.most_common()
    best, best_score = ranking[0]
    second = ranking[1][1] if len(ranking) > 1 else 0
    if best_score - second < 2:
        return "incertain"
    return best


def match_tag(class_union: set[int], names: list[str]) -> str:
    if not names or not class_union:
        return "inconnu"
    nc = len(names)
    if min(class_union) < 0 or max(class_union) >= nc:
        return "incompatible"
    if class_union == {0} and nc > 1:
        return "ambigu"
    return "compatible"


def pick(scores: Counter, reasons: list[str]) -> tuple[str, str]:
    if not scores:
        reasons.append("Aucun indice de nom de dossier ou de classes ne permet de trancher.")
        return "incertain", "faible"
    ranking = scores.most_common()
    best, best_score = ranking[0]
    second = ranking[1][1] if len(ranking) > 1 else 0
    lead = best_score - second
    reasons.append(
        "indices chiffrés : " + ", ".join(f"{name}={score}" for name, score in ranking)
    )
    if best_score >= 4 and lead >= 3:
        return best, "haute"
    if best_score >= 3 and lead >= 2:
        return best, "moyenne"
    reasons.append("Les indices sont trop proches pour choisir un dataset.")
    return "incertain", "faible"


def syntax_label(syntax: str) -> str:
    labels = {
        "yolo_bbox": "YOLO txt normalisé (rectangle classe x y largeur hauteur)",
        "yolo_polygone": "YOLO polygone normalisé (classe + paires x y)",
        "yolo_bbox_et_polygone": "rectangle et polygone dans le même fichier",
        "txt_coordonnees_absolues": "txt à coordonnées absolues, non normalisées",
        "vide": "fichier txt vide",
        "voc_xml": "VOC XML",
        "coco_json": "COCO JSON",
        "liste_darknet": "liste de chemins Darknet, pas des boîtes",
        "illisible": "fichier illisible",
        "txt_trop_volumineux": "txt trop volumineux, non interprété",
    }
    return labels.get(syntax, syntax)


def layout_label(layout: str) -> str:
    labels = {
        "ultralytics": "Ultralytics : dossiers images/ et labels/ séparés",
        "plat": "Darknet : images et annotations dans le même dossier",
        "autre": "organisation non standard",
    }
    return labels.get(layout, layout)


def resolve_yaml_path(base_file: Path, raw: str) -> list[tuple[str, Path, bool]]:
    raw_path = Path(str(raw).strip())
    found: list[tuple[str, Path, bool]] = []
    seen: set[Path] = set()

    def add(label: str, path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            return
        seen.add(resolved)
        found.append((label, resolved, resolved.exists()))

    if raw_path.is_absolute():
        add("chemin absolu", raw_path)
        return found
    add("relatif au fichier qui le déclare", base_file.parent / raw_path)
    parts = list(raw_path.parts)
    stripped = list(parts)
    while stripped and stripped[0] == "..":
        stripped = stripped[1:]
    if stripped and tuple(stripped) != tuple(parts):
        add(
            "préfixe « .. » retiré, depuis le dossier du fichier",
            base_file.parent.joinpath(*stripped),
        )
    return found


def looks_like_path_list(lines: list[str]) -> bool:
    sample = lines[:30]
    hits = 0
    for line in sample:
        low = line.lower().replace("\\", "/")
        first = line.split()[0]
        try:
            int(float(first))
            numeric = True
        except ValueError:
            numeric = False
        if not numeric and (low.endswith(tuple(IMAGE_EXTS)) or "/" in low):
            hits += 1
    return hits >= max(1, int(0.6 * len(sample)))


def line_kind(values: list[float]) -> str:
    if not values:
        return "autre"
    peak = max(abs(value) for value in values)
    normalized = peak <= 1.05
    if len(values) == 4 and normalized:
        return "bbox"
    if len(values) >= 6 and len(values) % 2 == 0 and normalized:
        return "poly"
    if peak > 1.5:
        return "absolu"
    return "hors_plage"


def classify_txt(path: Path) -> AnnoInfo:
    info = AnnoInfo(syntax="illisible")
    try:
        if path.stat().st_size > 2_000_000:
            info.syntax = "txt_trop_volumineux"
            return info
        raw = read_text_capped(path, 2_000_000)
    except OSError:
        return info
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        info.syntax = "vide"
        return info
    if looks_like_path_list(lines):
        info.syntax = "liste_darknet"
        info.example_line = lines[0][:180]
        return info

    kinds: set[str] = set()
    for line in lines:
        parts = line.split()
        if info.example_line == "":
            info.example_line = line[:180]
        try:
            class_id = int(float(parts[0]))
            values = [float(piece) for piece in parts[1:]]
        except (ValueError, IndexError):
            kinds.add("non_parse")
            continue
        kind = line_kind(values)
        kinds.add(kind)
        info.ids[class_id] += 1
        info.n_boxes += 1
        if kind == "poly":
            info.n_poly_lines += 1
            info.point_counts[len(values) // 2] += 1
            if len(values) >= 4 and abs(values[0] - values[-2]) < 1e-4 and abs(values[1] - values[-1]) < 1e-4:
                info.n_closed += 1

    if kinds == {"bbox"}:
        info.syntax = "yolo_bbox"
    elif kinds == {"poly"}:
        info.syntax = "yolo_polygone"
    elif kinds <= {"bbox", "poly"} and len(kinds) > 1:
        info.syntax = "yolo_bbox_et_polygone"
    elif kinds == {"absolu"}:
        info.syntax = "txt_coordonnees_absolues"
    elif not kinds:
        info.syntax = "vide"
    else:
        info.syntax = "txt_" + "+".join(sorted(kinds))
    return info


def classify_xml(path: Path) -> AnnoInfo:
    info = AnnoInfo(syntax="xml_autre")
    try:
        raw = read_text_capped(path, 200_000)
    except OSError:
        info.syntax = "illisible"
        return info
    low = raw.lower()
    info.extra_names = re.findall(r"<name>\s*([^<]+?)\s*</name>", raw, flags=re.IGNORECASE)
    if "<annotation" in low and ("<bndbox" in low or "<object" in low):
        info.syntax = "voc_xml"
    return info


def classify_json(path: Path) -> AnnoInfo:
    info = AnnoInfo(syntax="json_autre")
    try:
        raw = read_text_capped(path, 2_000_000)
    except OSError:
        info.syntax = "illisible"
        return info
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        head = raw[:8000].lower()
        if '"images"' in head and '"annotations"' in head:
            info.syntax = "coco_json"
        return info
    if isinstance(data, dict) and "images" in data and "annotations" in data:
        info.syntax = "coco_json"
        for category in data.get("categories") or []:
            if isinstance(category, dict) and category.get("name") is not None:
                info.extra_names.append(str(category["name"]))
    return info


def classify_annotation(path: Path) -> AnnoInfo:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return classify_txt(path)
    if suffix == ".xml":
        return classify_xml(path)
    if suffix == ".json":
        return classify_json(path)
    return AnnoInfo(syntax="autre")


def parse_names_file(path: Path) -> list[str]:
    raw = read_text_capped(path, 1_000_000)
    names: list[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if path.name.lower() == "obj.data" and "=" in text:
            continue
        names.append(text)
    return names


def normalize_yaml_names(raw: object, yaml_path: Path) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, dict):
        def sort_key(key: object) -> tuple[int, str]:
            text = str(key)
            return (0, f"{int(text):08d}") if text.isdigit() else (1, text)

        return [str(raw[key]) for key in sorted(raw, key=sort_key)]
    if isinstance(raw, str):
        for _label, candidate, exists in resolve_yaml_path(yaml_path, raw):
            if exists and candidate.is_file() and is_inside(candidate, yaml_path.parent.parent):
                try:
                    return parse_names_file(candidate)
                except OSError:
                    return []
        return [raw]
    return []


def parse_yaml_source(path: Path) -> ClassSource | None:
    try:
        raw = read_text_capped(path, 1_000_000)
        data = yaml.safe_load(raw) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"{path.name} illisible : {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path.name} ne contient pas un dictionnaire YAML")
    source = ClassSource(path=path, kind="yaml", names=[], anchor=path.parent)
    source.names = normalize_yaml_names(data.get("names"), path)
    if "nc" in data:
        source.meta["nc"] = str(data.get("nc"))
    roboflow = data.get("roboflow")
    if isinstance(roboflow, dict):
        for key in ("workspace", "project", "version", "license", "url"):
            if roboflow.get(key) is not None:
                source.meta[key] = str(roboflow[key])
    for key in ("train", "val", "valid", "test"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            source.declared.append(
                DeclaredPath(key=key, raw=value.strip(), candidates=resolve_yaml_path(path, value))
            )
    return source


def parse_obj_data(path: Path) -> ClassSource:
    raw = read_text_capped(path, 1_000_000)
    pairs: dict[str, str] = {}
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        pairs[key.strip().lower()] = value.strip()
    source = ClassSource(path=path, kind="obj.data", names=[], anchor=path.parent)
    if "classes" in pairs:
        source.meta["classes"] = pairs["classes"]
    names_ref = pairs.get("names")
    if names_ref:
        source.declared.append(
            DeclaredPath(key="names", raw=names_ref, candidates=resolve_yaml_path(path, names_ref))
        )
        for _label, candidate, exists in source.declared[-1].candidates:
            if exists and candidate.is_file():
                try:
                    source.names = parse_names_file(candidate)
                except OSError:
                    source.names = []
                break
    for key in ("train", "valid", "val", "test", "backup"):
        if pairs.get(key):
            source.declared.append(
                DeclaredPath(
                    key=key,
                    raw=pairs[key],
                    candidates=resolve_yaml_path(path, pairs[key]),
                )
            )
    return source


def expand_existing_dir(path: Path) -> set[Path]:
    found = {path}
    if not path.is_dir():
        return found
    if path.name.lower() == "images":
        found.add(path.parent)
        labels = path.parent / "labels"
        if labels.is_dir():
            found.add(labels)
    if path.name.lower() == "labels":
        found.add(path.parent)
        images = path.parent / "images"
        if images.is_dir():
            found.add(images)
    for child_name in ("images", "labels"):
        child = path / child_name
        if child.is_dir():
            found.add(child)
    return found


def yaml_targets(source: ClassSource, src: Path) -> set[Path]:
    targets: set[Path] = set()
    for declared in source.declared:
        if declared.key == "names":
            continue
        for _label, candidate, exists in declared.candidates:
            if exists and candidate.is_dir() and is_inside(candidate, src):
                targets |= expand_existing_dir(candidate)
    return targets


def source_is_s2tld(source: ClassSource) -> bool:
    blob = " ".join([source.path.name, *source.meta.values()]).lower()
    return "s2tld" in blob


def associated_image_dir(label_dir: Path) -> Path:
    if label_dir.name.lower() == "labels":
        sibling = label_dir.parent / "images"
        if sibling.is_dir():
            return sibling
    return label_dir


def layout_of(label_dir: Path, image_dir: Path) -> str:
    if label_dir.name.lower() == "labels" and image_dir.name.lower() == "images":
        return "ultralytics"
    if label_dir == image_dir:
        return "plat"
    return "autre"


def cfg_note(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return f"stat impossible ({exc})"
    if size > 2_000_000:
        return "fichier .cfg volumineux, contenu non lu — à mettre en quarantaine"
    try:
        text = read_text_capped(path, 2_000_000)
    except OSError as exc:
        return f"lecture impossible ({exc}) — à mettre en quarantaine"
    found = CLASS_LINE.findall(text)
    if found:
        values = ", ".join(found)
        return (
            f"texte de configuration, classes={values}. "
            "Ce n'est pas un poids, mais c'est un modèle pré-entraîné à mettre en quarantaine "
            "et à ne pas utiliser pour l'entraînement."
        )
    return "texte de configuration .cfg, à mettre en quarantaine et à ne pas utiliser pour l'entraînement."


def pillow_sample(image_dir: Path, limit: int = 3) -> list[str]:
    try:
        images = sorted(
            (path for path in image_dir.iterdir() if path.is_file() and is_image(path)),
            key=lambda path: path.name.lower(),
        )
    except OSError as exc:
        return [f"dossier illisible ({exc})"]
    lines: list[str] = []
    for path in images[:limit]:
        try:
            with Image.open(path) as image:
                lines.append(f"{path.name} : {image.format} {image.size[0]}×{image.size[1]} {image.mode}")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            lines.append(f"{path.name} : illisible ({type(exc).__name__})")
    return lines


def mapping_text(names: list[str], class_union: set[int]) -> str:
    parts: list[str] = []
    for index in sorted(class_union):
        if 0 <= index < len(names):
            parts.append(f"{index}={names[index]}")
        if len(parts) >= 16:
            parts.append("…")
            break
    return ", ".join(parts) if parts else "aucun id couvert"


def applicable_sources(
    label_dir: Path,
    layout: str,
    sources: list[ClassSource],
    src: Path,
) -> list[ClassSource]:
    local_names: list[ClassSource] = []
    root_names: list[ClassSource] = []
    selected: list[ClassSource] = []
    for source in sources:
        if source.kind in {"names", "classes", "obj.data"}:
            if source.anchor.resolve() == src.resolve():
                if layout == "plat":
                    root_names.append(source)
            else:
                try:
                    label_dir.resolve().relative_to(source.anchor.resolve())
                except ValueError:
                    continue
                local_names.append(source)
        elif source.kind == "yaml":
            if label_dir.resolve() in yaml_targets(source, src):
                selected.append(source)
        elif source.anchor.resolve() == label_dir.resolve():
            selected.append(source)
    if local_names:
        local_names.sort(key=lambda source: len(source.anchor.parts), reverse=True)
        best = len(local_names[0].anchor.parts)
        selected.extend(source for source in local_names if len(source.anchor.parts) == best)
    else:
        selected.extend(root_names)
    return selected


def id_mass_outside(counter: Counter, names: list[str]) -> int:
    if not names:
        return sum(counter.values())
    nc = len(names)
    return sum(count for index, count in counter.items() if index < 0 or index >= nc)


def evaluate_group(
    group: Group,
    sources: list[ClassSource],
    src: Path,
    readme_s2tld: bool,
) -> None:
    reasons: list[str] = []
    layout = layout_of(group.directory, associated_image_dir(group.directory))
    usable = applicable_sources(group.directory, layout, sources, src)
    relative = relposix(group.directory, src)
    folder_points, folder_reasons = folder_scores(relative)

    if group.syntax == "vide" or (
        not group.syntax.startswith("yolo") and group.syntax not in {"voc_xml", "coco_json"}
    ):
        reasons.append(f"Format : {syntax_label(group.syntax)}.")
        reasons.append("Ces fichiers ne sont pas affectés automatiquement.")
        group.target = "incertain"
        group.confidence = "faible"
        group.reasons = reasons
        return

    tagged: list[tuple[ClassSource, str]] = []
    for source in usable:
        if not source.names:
            continue
        tagged.append((source, match_tag(group.union, source.names)))

    for source, tag in tagged:
        if tag == "incompatible":
            outside = id_mass_outside(group.ids, source.names)
            reasons.append(
                f"{source.path.name} ({plural(len(source.names), 'classe', 'classes')}, "
                f"hypothèse {primary_target(source.names)}) ne couvre pas ces ids "
                f"({plural(outside, 'boîte hors plage', 'boîtes hors plage')})."
            )
        elif tag == "ambigu":
            reasons.append(
                f"{source.path.name} : la classe 0 vaut « {source.names[0]} », "
                f"mais le fichier décrit {len(source.names)} classes et ces annotations "
                "n'utilisent que la classe 0."
            )
        elif tag == "compatible":
            reasons.append(
                f"{source.path.name} couvre les ids observés "
                f"({mapping_text(source.names, group.union)})."
            )

    claims = [(source, tag) for source, tag in tagged if tag in {"compatible", "ambigu"}]
    compatible = [source for source, tag in tagged if tag == "compatible"]
    ambigu = [source for source, tag in tagged if tag == "ambigu"]

    def finish_uncertain(extra: str) -> None:
        reasons.extend(folder_reasons)
        reasons.append(extra)
        group.target = "incertain"
        group.confidence = "faible"
        group.conflict = True
        group.reasons = reasons

    if group.union == {0} and len(claims) >= 2:
        finish_uncertain(
            "Plusieurs fichiers de classes peuvent revendiquer la classe 0. "
            "Pas d'affectation automatique."
        )
        return
    if group.union == {0} and ambigu and not compatible:
        finish_uncertain(
            "Seule la classe 0 apparaît, dans un jeu qui en déclare plusieurs. "
            "Pas d'affectation automatique."
        )
        return

    targets = {primary_target(source.names) for source in compatible}
    targets.discard("incertain")
    if len(targets) > 1:
        finish_uncertain(
            "Plusieurs fichiers de classes compatibles désignent des datasets différents."
        )
        return

    scores: Counter = Counter()
    seen_names: set[tuple[str, ...]] = set()
    for source in compatible:
        key = tuple(source.names)
        if key in seen_names:
            reasons.append(f"{source.path.name} répète les mêmes noms de classes.")
            continue
        seen_names.add(key)
        points, detail = name_scores(source.names)
        scores.update(points)
        reasons.extend(detail)
        if readme_s2tld and source_is_s2tld(source):
            scores["traffic_lights"] += 2
            reasons.append("le README cite le projet s2tld, le même que ce fichier YAML")
    if len(group.union) >= 15 and "plates_chars" not in scores:
        scores["plates_chars"] += 3
        reasons.append(
            f"{len(group.union)} ids distincts sans noms de caractères explicites : "
            "hypothèse plaques / caractères"
        )
    scores.update(folder_points)
    reasons.extend(folder_reasons)
    if group.syntax == "yolo_polygone":
        if group.point_counts:
            points, count = group.point_counts.most_common(1)[0]
            reasons.append(f"polygones : forme la plus fréquente = {points} sommets ({count} boîtes)")
        if group.n_poly_lines and group.n_closed >= group.n_poly_lines / 2:
            reasons.append("la majorité des polygones sont fermés (le premier point répète le dernier)")
    target, confidence = pick(scores, reasons)
    if target != "incertain" and group.syntax != "yolo_bbox" and confidence == "haute":
        confidence = "moyenne"
        reasons.append("Confiance ramenée à moyenne : le format n'est pas le rectangle YOLO classique.")
    group.target = target
    group.confidence = confidence
    group.reasons = reasons


def readme_highlights(path: Path) -> list[str]:
    try:
        raw = read_text_capped(path, 200_000)
    except OSError as exc:
        return [f"illisible ({exc})"]
    kept: list[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        low = text.lower()
        if any(chunk in low for chunk in README_SKIP):
            continue
        if (
            text.startswith("#")
            or text.startswith("=")
            or "http" in low
            or "license" in low
            or "licence" in low
            or "yolo" in low
            or "s2tld" in low
            or "image" in low
            or "annot" in low
        ):
            kept.append(text)
    if not kept:
        kept = [line.strip() for line in raw.splitlines() if line.strip()][:8]
    return kept[:30]


def announced_counts(text: str) -> list[int]:
    found: list[int] = []
    for match in IMAGE_COUNT_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(1))
        if digits:
            found.append(int(digits))
    return found


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, text: str = "") -> None:
        self.lines.append(text)

    def heading(self, level: int, text: str) -> None:
        self.add(f"{'#' * level} {text}")
        self.add()

    def bullets(self, items: list[str]) -> None:
        if not items:
            self.add("_Aucun._")
            self.add()
            return
        for item in items:
            self.add(f"- {item}")
        self.add()

    def table(self, headers: list[str], rows: list[list[object]]) -> None:
        if not rows:
            self.add("_Aucune ligne._")
            self.add()
            return
        self.add("| " + " | ".join(headers) + " |")
        self.add("| " + " | ".join("---" for _ in headers) + " |")
        for row in rows:
            self.add("| " + " | ".join(md(cell) for cell in row) + " |")
        self.add()

    def text(self) -> str:
        return "\n".join(self.lines).rstrip() + "\n"


def top_name(path: Path, src: Path) -> str:
    relative = path.resolve().relative_to(src.resolve())
    return relative.parts[0]


def verdict_for(targets: list[tuple[str, str]]) -> tuple[str, str, str]:
    """Retourne dataset, confiance, et le mot mélange ou unique ou incertain."""
    if not targets:
        return "incertain", "faible", "incertain"
    datasets = {target for target, _confidence in targets}
    if datasets == {"incertain"}:
        return "incertain", "faible", "incertain"
    if len(datasets) > 1:
        return "incertain", "faible", "mélange"
    only = next(iter(datasets))
    order = {"faible": 0, "moyenne": 1, "haute": 2}
    confidence = min((confidence for _target, confidence in targets), key=lambda item: order.get(item, 0))
    return only, confidence, "unique"


def build_questions(
    groups: list[Group],
    image_only: list[ImageOnly],
    sources: list[ClassSource],
    src: Path,
    readmes: list[tuple[Path, list[str]]],
    across_count: int,
    announced_gap: str | None,
    literal_path_issue: bool,
) -> list[str]:
    questions: list[str] = []

    def add(text: str) -> None:
        if text not in questions:
            questions.append(text)

    conflict_groups = [group for group in groups if group.conflict and group.union == {0}]
    if conflict_groups:
        lines = []
        for group in conflict_groups:
            lines.append(
                f"{relposix(group.directory, src)} — {syntax_label(group.syntax)} — "
                f"{plural(group.n_files, 'fichier', 'fichiers')}, "
                f"environ {plural(group.matched_images, 'image', 'images')}"
            )
        claims = []
        sample = conflict_groups[0]
        layout = layout_of(sample.directory, associated_image_dir(sample.directory))
        for source in applicable_sources(sample.directory, layout, sources, src):
            if source.names:
                claims.append(
                f"{source.path.name} : classe 0 = « {source.names[0]} » "
                f"({plural(len(source.names), 'classe', 'classes')}, piste {primary_target(source.names)})"
                )
        claim_text = "; ".join(claims) if claims else "plusieurs fichiers de classes"
        add(
            "Ces annotations n'utilisent que la classe 0, et plusieurs fichiers de classes "
            f"peuvent la revendiquer ({claim_text}). "
            "Doivent-elles aller dans traffic_lights, plates_detection ou plates_chars ?\n"
            + "\n".join(f"  - {line}" for line in lines)
        )

    other_uncertain = [
        group for group in groups if group.target == "incertain" and group not in conflict_groups
    ]
    if other_uncertain or image_only:
        lines = []
        for group in other_uncertain:
            lines.append(
                f"{relposix(group.directory, src)} — {syntax_label(group.syntax)} — "
                f"{group.n_files} fichiers. Exemples : {', '.join(group.examples[:3]) or 'aucun'}"
            )
        for item in image_only:
            lines.append(
                f"{relposix(item.path, src)} — {item.n_images} image(s) sans annotation. "
                f"Exemples : {', '.join(item.examples[:3]) or 'aucun'}"
            )
        add(
            "Que faut-il faire des éléments suivants, qui restent incertains ?\n"
            + "\n".join(f"  - {line}" for line in lines)
        )

    found_chars = any(
        group.target == "plates_chars" and group.confidence in {"haute", "moyenne"}
        for group in groups
    )
    if not found_chars:
        add(
            "Le dataset « Moroccan Vehicle Registration Plates » (plaques / caractères) "
            "n'a pas été reconnu : aucune liste de classes du type chiffre ou lettre. "
            "Est-il absent de ce dossier, ou correspond-il à l'un des groupes incertains ci-dessus ?"
        )

    if literal_path_issue:
        add(
            "Dans les YAML, les chemins du type `../train/images` sortent du dossier source "
            "une fois résolus tels quels, et ce dossier externe n'existe pas. "
            "En retirant le préfixe `..`, on retombe sur les dossiers locaux train/images, "
            "valid/images et test/images. Confirmez-vous que ce sont bien ces dossiers locaux "
            "qui sont visés ?"
        )

    if announced_gap:
        add(announced_gap if announced_gap.endswith("?") else announced_gap + " ?")

    if across_count:
        add(
            f"{across_count} nom(s) d'image identiques apparaissent dans des dossiers de "
            "premier niveau différents. Confirmez-vous qu'il faut les copier dans des "
            "sous-dossiers séparés, afin qu'une copie ne remplace pas un fichier par un autre ?"
        )

    root_meta = [
        source.path.name
        for source in sources
        if source.kind != "annotations" and source.path.parent.resolve() == src.resolve()
    ]
    nested_meta = [
        relposix(source.path, src)
        for source in sources
        if source.kind != "annotations" and source.path.parent.resolve() != src.resolve()
    ]
    readme_names = [path.name for path, _lines in readmes]
    if root_meta or readme_names or nested_meta:
        listed = ", ".join(root_meta + readme_names)
        nested = ", ".join(nested_meta)
        extra = (
            f" {nested} est déjà dans un dossier de données et suivrait ce dossier vers data/raw/."
            if nested
            else ""
        )
        add(
            "Je propose de copier les fichiers de la racine "
            f"({listed}) dans configs/, pas dans data/raw/.{extra} "
            "Confirmez-vous cet emplacement pour l'étape 2 ?"
        )
    return questions


def render(
    src: Path,
    stats: dict[Path, DirStats],
    top_dirs: list[Path],
    top_files: list[SeenFile],
    holders: list[Path],
    sources: list[ClassSource],
    readmes: list[tuple[Path, list[str]]],
    label_dirs: list[LabelDir],
    image_only: list[ImageOnly],
    models: list[ModelFile],
    across: dict[str, list[tuple[str, str]]],
    within: dict[tuple[str, str], list[str]],
    questions: list[str],
    errors: list[str],
    announced_note: str | None,
) -> str:
    report = Report()
    total = stats[src]
    report.heading(1, "Plan de réorganisation (dry-run)")
    report.add(f"- Source : `{src}`")
    report.add(f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.add(f"- Script : `scripts/00_analyze_mess.py`")
    report.add(
        "- Mode : analyse seule. Aucun fichier de la source n'a été copié, déplacé, modifié ou supprimé."
    )
    report.add(
        "- Les dossiers `data/raw/...` du projet restent vides. "
        "Ce document est une proposition à valider avant toute copie."
    )
    report.add(
        f"- Volume parcouru : {total.files} fichiers, {total.images} images, "
        f"{total.annos} annotations, {human_size(total.size)}."
    )
    report.add(
        "- Une annotation compte un `.txt`, `.xml` ou `.json` de boîtes. "
        "`classes.txt`, `obj.names`, `obj.data` et les README sont comptés à part."
    )
    report.add()

    report.heading(2, "a. Inventaire du premier niveau")
    rows: list[list[object]] = []
    for directory in top_dirs:
        item = stats.get(directory, DirStats())
        rows.append([
            relposix(directory, src),
            "dossier",
            item.images,
            item.annos,
            fmt_exts(item.exts),
            human_size(item.size),
        ])
    for seen in top_files:
        path = seen.path
        image_count = 1 if is_image(path) else 0
        anno_count = 1 if is_annotation(path) else 0
        rows.append([
            path.name,
            "fichier",
            image_count,
            anno_count,
            path.suffix.lower() or "(sans extension)",
            human_size(seen.size),
        ])
    rows.append(["TOTAL", "", total.images, total.annos, fmt_exts(total.exts), human_size(total.size)])
    report.table(
        ["Élément", "Type", "Images", "Annotations", "Extensions", "Taille"],
        rows,
    )

    report.heading(3, "Dossiers qui contiennent directement les fichiers")
    holder_rows = []
    for directory in holders:
        item = stats[directory]
        holder_rows.append([
            relposix(directory, src),
            item.direct_images,
            item.direct_annos,
            fmt_exts(item.exts),
            human_size(item.size),
        ])
    report.table(
        ["Dossier", "Images directes", "Annotations directes", "Extensions (tout le sous-arbre)", "Taille du sous-arbre"],
        holder_rows,
    )

    report.heading(2, "b. Fichiers de classes")
    if not sources:
        report.add("Aucun `data.yaml`, `obj.names` ou `classes.txt` trouvé.")
        report.add()
    for source in sources:
        report.heading(3, relposix(source.path, src))
        report.add(f"- Type : {source.kind}")
        report.add(f"- Nombre de classes : {len(source.names)}")
        if source.meta.get("nc") and source.meta["nc"] != str(len(source.names)):
            report.add(
                f"- Le champ `nc` vaut {source.meta['nc']}, "
                f"alors que la liste contient {len(source.names)} noms."
            )
        for key, value in source.meta.items():
            if key == "nc":
                continue
            report.add(f"- {key} : {value}")
        report.add(f"- Noms : {fmt_names(source.names)}")
        points, detail = name_scores(source.names)
        if points:
            report.add(
                "- Lecture des noms : "
                + ", ".join(f"{name}={score}" for name, score in points.most_common())
                + ". "
                + " ".join(detail)
            )
        report.add()
        if source.declared:
            declared_rows = []
            for declared in source.declared:
                for label, candidate, exists in declared.candidates:
                    where = "dans la source" if is_inside(candidate, src) else "hors de la source"
                    declared_rows.append([
                        declared.key,
                        declared.raw,
                        label,
                        str(candidate),
                        "oui" if exists else "non",
                        where,
                    ])
            report.table(
                ["Clé", "Déclaré", "Interprétation", "Chemin résolu", "Existe", "Emplacement"],
                declared_rows,
            )
        else:
            report.add("Ce fichier ne déclare pas de chemin train/val/test.")
            report.add()

    report.heading(2, "Documentation lue")
    if not readmes:
        report.add("Aucun README trouvé.")
        report.add()
    for path, lines in readmes:
        report.heading(3, path.name)
        report.bullets(lines)
    if announced_note:
        report.add(announced_note)
        report.add()

    report.heading(2, "c. Format d'annotation")
    report.add(
        "Le format est déduit en lisant les annotations, pas seulement leur extension. "
        "YOLO et Darknet partagent le rectangle normalisé `classe x y largeur hauteur`. "
        "Le dossier est appelé Darknet quand l'image et le `.txt` sont côte à côte, "
        "et Ultralytics quand `images/` et `labels/` sont séparés."
    )
    report.add()
    if not label_dirs:
        report.add("Aucune annotation trouvée.")
        report.add()
    for label_dir in label_dirs:
        report.heading(3, relposix(label_dir.path, src))
        report.add(f"- Organisation : {layout_label(label_dir.layout)}")
        report.add(
            f"- Dossier d'images associé : `{relposix(label_dir.image_dir, src)}` "
            f"({label_dir.n_images} images)"
        )
        report.add(f"- Images sans annotation : {label_dir.images_without_label}")
        if label_dir.orphan_image_examples:
            report.add("- Exemples d'images sans annotation : " + ", ".join(label_dir.orphan_image_examples))
        if label_dir.pillow:
            report.add("- Échantillon Pillow :")
            for line in label_dir.pillow:
                report.add(f"  - {line}")
        report.add()
        for group in label_dir.groups:
            title = syntax_label(group.syntax)
            if label_dir.layout == "plat" and group.syntax == "yolo_bbox":
                title = "Darknet — " + title
            elif label_dir.layout == "ultralytics" and group.syntax == "yolo_bbox":
                title = "YOLO Ultralytics — " + title
            report.add(f"**{title}**")
            report.add()
            report.add(f"- Fichiers : {group.n_files}")
            report.add(f"- Boîtes ou polygones : {group.n_boxes}")
            report.add(f"- Images liées par le nom : {group.matched_images}")
            report.add(f"- Annotations sans image : {group.unmatched_labels}")
            report.add(f"- Ids de classes (id × nombre de boîtes) : {fmt_ids(group.ids)}")
            if group.patterns:
                report.add(
                    "- Noms de fichiers : "
                    + ", ".join(f"{name} ({count})" for name, count in group.patterns.most_common())
                )
            if group.examples:
                report.add("- Exemples : " + ", ".join(group.examples[:5]))
            if group.example_line:
                report.add(f"- Première ligne lue : `{group.example_line}`")
            report.add()

    report.heading(2, "d. Proposition d'affectation")
    report.add(
        "Destinations prévues, encore vides : "
        + ", ".join(f"`data/raw/{name}`" for name in DATASETS)
        + ". La valeur `incertain` signifie qu'il faut votre réponse avant de copier."
    )
    report.add()

    by_top: dict[str, list[Group]] = defaultdict(list)
    for label_dir in label_dirs:
        for group in label_dir.groups:
            by_top[top_name(label_dir.path, src)].append(group)
    image_only_tops = {top_name(item.path, src): item for item in image_only}

    summary_rows: list[list[object]] = []
    for directory in top_dirs:
        name = directory.name
        groups = by_top.get(name, [])
        item = stats.get(directory, DirStats())
        if groups:
            target, confidence, kind = verdict_for([(group.target, group.confidence) for group in groups])
            if kind == "mélange":
                proposal = "mélange — copier selon les sous-groupes, pas le dossier entier"
                confidence = "voir sous-groupes"
            elif kind == "incertain":
                proposal = "incertain"
            else:
                proposal = f"{target} — copier le dossier entier vers data/raw/{target}/"
            summary_rows.append([name, proposal, confidence, sum(group.n_files for group in groups)])
        elif name in image_only_tops:
            only = image_only_tops[name]
            summary_rows.append([name, "incertain — images sans annotation", only.confidence, 0])
        else:
            summary_rows.append([
                name,
                "rien à copier comme dataset d'images" if item.images == 0 else "incertain",
                "—",
                0,
            ])
    report.table(["Dossier", "Verdict", "Confiance", "Fichiers d'annotation"], summary_rows)

    report.heading(3, "Sous-groupes")
    sub_rows: list[list[object]] = []
    for label_dir in label_dirs:
        for group in label_dir.groups:
            if group.target == "incertain":
                destination = "en attente de votre réponse"
            elif verdict_for([(item.target, item.confidence) for item in by_top[top_name(label_dir.path, src)]])[2] == "unique":
                destination = f"data/raw/{group.target}/ (dossier entier)"
            else:
                destination = f"data/raw/{group.target}/ (ces fichiers seulement)"
            sub_rows.append([
                relposix(label_dir.path, src),
                syntax_label(group.syntax),
                group.n_files,
                group.matched_images,
                group.target,
                group.confidence,
                destination,
            ])
    for item in image_only:
        sub_rows.append([
            relposix(item.path, src),
            "image sans annotation",
            0,
            item.n_images,
            item.target,
            item.confidence,
            "en attente de votre réponse",
        ])
    report.table(
        ["Dossier", "Format", "Annotations", "Images", "Dataset", "Confiance", "Destination proposée"],
        sub_rows,
    )

    report.heading(3, "Justification")
    for label_dir in label_dirs:
        for group in label_dir.groups:
            report.add(
                f"**{relposix(label_dir.path, src)} — {syntax_label(group.syntax)}** "
                f"→ `{group.target}` ({group.confidence})"
            )
            report.add()
            report.bullets(group.reasons)
    for item in image_only:
        report.add(f"**{relposix(item.path, src)}** → `{item.target}` ({item.confidence})")
        report.add()
        report.bullets(item.reasons)

    report.heading(2, "e. Collisions")
    report.heading(3, "Chemins déclarés par plusieurs fichiers de classes")
    raw_map: dict[tuple[str, str], list[str]] = defaultdict(list)
    existing_map: dict[Path, list[str]] = defaultdict(list)
    for source in sources:
        for declared in source.declared:
            raw_map[(declared.key, declared.raw)].append(source.path.name)
            for _label, candidate, exists in declared.candidates:
                if exists:
                    existing_map[candidate].append(f"{source.path.name}:{declared.key}")
    collision_rows = []
    for (key, raw), owners in sorted(raw_map.items()):
        unique_owners = sorted(set(owners))
        if len(unique_owners) > 1:
            collision_rows.append([key, raw, ", ".join(unique_owners)])
    report.table(["Clé", "Chemin déclaré", "Fichiers"], collision_rows)
    shared_rows = []
    for candidate, owners in sorted(existing_map.items(), key=lambda item: str(item[0])):
        unique_owners = sorted(set(owners))
        if len(unique_owners) > 1:
            shared_rows.append([str(candidate), ", ".join(unique_owners)])
    report.add("Chemins résolus qui existent et qui sont visés par plusieurs déclarations :")
    report.add()
    report.table(["Chemin", "Déclarations"], shared_rows)

    report.heading(3, "Noms d'images identiques entre dossiers de premier niveau")
    if not across:
        report.add("Aucun nom d'image en commun entre des dossiers de premier niveau différents.")
        report.add()
    else:
        report.add(f"{len(across)} nom(s) en collision. Exemples :")
        report.add()
        across_rows = []
        for name, places in list(across.items())[:25]:
            across_rows.append([name, " ; ".join(rel for _top, rel in places[:6])])
        report.table(["Nom", "Emplacements"], across_rows)
        if len(across) > 25:
            report.add(f"{len(across) - 25} autre(s) nom(s) non affichés.")
            report.add()

    report.heading(3, "Même nom à l'intérieur d'un dossier de premier niveau")
    if not within:
        report.add("Aucun doublon interne de nom d'image.")
        report.add()
    else:
        report.add(f"{len(within)} doublon(s) interne(s). Exemples :")
        report.add()
        within_rows = []
        for (top, name), places in list(within.items())[:25]:
            within_rows.append([top, name, " ; ".join(places[:6])])
        report.table(["Dossier", "Nom", "Chemins"], within_rows)
        if len(within) > 25:
            report.add(f"{len(within) - 25} autre(s) doublon(s) non affichés.")
            report.add()

    report.heading(2, "f. Quarantaine")
    report.add(
        "Les fichiers ci-dessous sont des modèles ou des configurations de modèle pré-entraînés. "
        "Ils ne doivent pas servir à l'entraînement et ne doivent pas être copiés dans `data/`. "
        "Après votre validation, l'étape 2 les copiera dans `quarantine/`."
    )
    report.add(
        "Les `.weights`, `.pt` et `.onnx` n'ont pas été ouverts : seule la taille sur le disque a été lue."
    )
    report.add()
    if not models:
        report.add("Aucun fichier `.weights`, `.pt`, `.onnx` ou `.cfg`.")
        report.add()
    else:
        report.table(
            ["Fichier", "Taille", "Note"],
            [[relposix(model.path, src), human_size(model.size), model.note] for model in models],
        )

    report.heading(2, "g. Incertain — questions")
    if not questions:
        report.add("Aucun point bloquant. Le plan peut être validé tel quel.")
        report.add()
    else:
        for index, question in enumerate(questions, start=1):
            report.add(f"{index}. {question}")
            report.add()

    if errors:
        report.heading(2, "Lectures impossibles")
        report.bullets(errors)
    return report.text()


def walk_source(src: Path, errors: list[str]) -> tuple[list[SeenFile], dict[Path, DirStats]]:
    files: list[SeenFile] = []
    stats: dict[Path, DirStats] = defaultdict(DirStats)
    discovered: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [name for name in sorted(dirnames) if name != ".git"]
        for name in sorted(filenames):
            discovered.append(Path(dirpath) / name)
    for path in tqdm(discovered, desc="Inventaire", unit="fichier"):
        try:
            resolved = path.resolve()
            size = resolved.stat().st_size
        except OSError as exc:
            errors.append(f"{path} : {exc}")
            continue
        files.append(SeenFile(path=resolved, size=size))
        suffix = resolved.suffix.lower() or "(sans extension)"
        image = is_image(resolved)
        anno = is_annotation(resolved)
        node = resolved.parent
        first = True
        while True:
            item = stats[node]
            item.files += 1
            item.size += size
            item.exts[suffix] += 1
            item.images += int(image)
            item.annos += int(anno)
            if first:
                item.direct_images += int(image)
                item.direct_annos += int(anno)
                first = False
            if node == src:
                break
            parent = node.parent
            if parent == node:
                break
            node = parent
    return files, stats


def image_indexes(
    files: list[SeenFile],
    src: Path,
) -> tuple[dict[Path, dict[str, list[Path]]], dict[str, list[tuple[str, str]]], dict[tuple[str, str], list[str]]]:
    by_dir: dict[Path, dict[str, list[Path]]] = defaultdict(lambda: defaultdict(list))
    by_name: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for seen in files:
        if not is_image(seen.path):
            continue
        stem = seen.path.stem.casefold()
        by_dir[seen.path.parent][stem].append(seen.path)
        relative = relposix(seen.path, src)
        top = relative.split("/", 1)[0]
        by_name[seen.path.name.casefold()].append((top, relative, seen.path.name))

    across: dict[str, list[tuple[str, str]]] = {}
    within: dict[tuple[str, str], list[str]] = {}
    for key, places in by_name.items():
        tops = {top for top, _relative, _name in places}
        display = places[0][2]
        if len(tops) > 1:
            across[display] = [(top, relative) for top, relative, _name in places]
        by_top: dict[str, list[str]] = defaultdict(list)
        for top, relative, _name in places:
            by_top[top].append(relative)
        for top, relatives in by_top.items():
            unique = list(dict.fromkeys(relatives))
            if len(unique) > 1:
                within[(top, display)] = unique
    return by_dir, across, within


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyse un dossier de datasets YOLO mélangés et écrit un plan, sans rien copier.",
    )
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="Dossier source. Défaut : le dossier Infraction à côté de ce projet.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Rapport Markdown à écrire.")
    args = parser.parse_args(argv)

    src = args.src.expanduser().resolve()
    report_path = args.report.expanduser()
    if not report_path.is_absolute():
        report_path = (Path.cwd() / report_path).resolve()
    else:
        report_path = report_path.resolve()

    if not src.is_dir():
        print(f"Dossier source introuvable : {src}", file=sys.stderr)
        return 1
    if report_path == src or src in report_path.parents:
        print("Refus : le rapport serait écrit dans le dossier source.", file=sys.stderr)
        return 2

    errors: list[str] = []
    files, stats = walk_source(src, errors)
    if src not in stats:
        stats[src] = DirStats()

    top_dirs = sorted(
        (path.resolve() for path in src.iterdir() if path.is_dir()),
        key=lambda path: path.name.lower(),
    )
    top_files = sorted(
        (seen for seen in files if seen.path.parent == src),
        key=lambda seen: seen.path.name.lower(),
    )
    holders = sorted(
        (path for path, item in stats.items() if path != src and path.is_dir() and (item.direct_images or item.direct_annos)),
        key=lambda path: relposix(path, src).lower(),
    )

    sources: list[ClassSource] = []
    models: list[ModelFile] = []
    readmes: list[tuple[Path, list[str]]] = []
    for seen in files:
        suffix = seen.path.suffix.lower()
        name = seen.path.name.lower()
        if suffix in MODEL_EXTS:
            if suffix in MODEL_NO_READ:
                note = "contenu non lu (poids pré-entraîné) — quarantaine, ne pas utiliser pour l'entraînement"
            else:
                note = cfg_note(seen.path)
            models.append(ModelFile(path=seen.path, size=seen.size, note=note))
        if name.endswith((".yaml", ".yml")):
            try:
                parsed = parse_yaml_source(seen.path)
            except RuntimeError as exc:
                errors.append(str(exc))
                continue
            if parsed is not None:
                sources.append(parsed)
        elif name in {"classes.txt", "obj.names"} or suffix == ".names":
            try:
                names = parse_names_file(seen.path)
            except OSError as exc:
                errors.append(f"{seen.path} : {exc}")
                continue
            sources.append(ClassSource(
                path=seen.path,
                kind="names",
                names=names,
                anchor=seen.path.parent,
            ))
        elif name == "obj.data":
            try:
                sources.append(parse_obj_data(seen.path))
            except OSError as exc:
                errors.append(f"{seen.path} : {exc}")
        elif is_readme(seen.path):
            readmes.append((seen.path, readme_highlights(seen.path)))

    by_dir, across, within = image_indexes(files, src)
    grouped: dict[tuple[Path, str], Group] = {}
    extra_names: dict[Path, list[str]] = defaultdict(list)
    annotations = [seen for seen in files if is_annotation(seen.path)]
    for seen in tqdm(annotations, desc="Annotations", unit="fichier"):
        info = classify_annotation(seen.path)
        if info.extra_names:
            extra_names[seen.path.parent].extend(info.extra_names)
        key = (seen.path.parent, info.syntax)
        group = grouped.get(key)
        if group is None:
            group = Group(directory=seen.path.parent, syntax=info.syntax)
            grouped[key] = group
        group.n_files += 1
        group.n_boxes += info.n_boxes
        group.ids.update(info.ids)
        group.stems.add(seen.path.stem.casefold())
        group.point_counts.update(info.point_counts)
        group.n_closed += info.n_closed
        group.n_poly_lines += info.n_poly_lines
        group.patterns[filename_pattern(seen.path.name)] += 1
        if len(group.examples) < 5:
            group.examples.append(seen.path.name)
        if not group.example_line and info.example_line:
            group.example_line = info.example_line

    for directory, names in extra_names.items():
        unique = list(dict.fromkeys(names))
        if unique:
            sources.append(ClassSource(
                path=directory / "(classes lues dans les annotations)",
                kind="annotations",
                names=unique,
                anchor=directory,
            ))

    readme_blob = "\n".join(line for _path, lines in readmes for line in lines)
    readme_s2tld = "s2tld" in readme_blob.lower()
    for group in grouped.values():
        image_dir = associated_image_dir(group.directory)
        images = by_dir.get(image_dir, {})
        group.matched_images = sum(1 for stem in group.stems if stem in images)
        group.unmatched_labels = group.n_files - len(group.stems) + sum(
            1 for stem in group.stems if stem not in images
        )
        evaluate_group(group, sources, src, readme_s2tld)

    label_dirs: list[LabelDir] = []
    by_label_parent: dict[Path, list[Group]] = defaultdict(list)
    for group in grouped.values():
        by_label_parent[group.directory].append(group)
    pillow_cache: dict[Path, list[str]] = {}

    def samples(directory: Path) -> list[str]:
        if directory not in pillow_cache:
            pillow_cache[directory] = pillow_sample(directory)
        return pillow_cache[directory]

    for directory, dir_groups in sorted(by_label_parent.items(), key=lambda item: relposix(item[0], src).lower()):
        image_dir = associated_image_dir(directory)
        images = by_dir.get(image_dir, {})
        stems: set[str] = set()
        for group in dir_groups:
            stems |= group.stems
        missing = [paths[0].name for stem, paths in sorted(images.items()) if stem not in stems]
        label_dirs.append(LabelDir(
            path=directory,
            layout=layout_of(directory, image_dir),
            image_dir=image_dir,
            n_images=sum(len(paths) for paths in images.values()),
            images_without_label=len(missing),
            orphan_image_examples=missing[:5],
            groups=sorted(dir_groups, key=lambda group: group.syntax),
            pillow=samples(image_dir) if images else [],
        ))

    covered_tops = {top_name(label_dir.path, src) for label_dir in label_dirs}
    image_only: list[ImageOnly] = []
    for directory in top_dirs:
        if directory.name in covered_tops:
            continue
        item = stats.get(directory, DirStats())
        if item.images <= 0:
            continue
        flat_examples: list[str] = []
        for paths in by_dir.get(directory, {}).values():
            flat_examples.extend(path.name for path in paths)
        if not flat_examples:
            for seen in files:
                if is_image(seen.path) and is_inside(seen.path, directory):
                    flat_examples.append(seen.path.name)
        flat_examples = sorted(set(flat_examples), key=str.lower)[:5]
        image_only.append(ImageOnly(
            path=directory,
            n_images=item.images,
            examples=flat_examples,
            pillow=samples(directory),
            reasons=[
                f"{item.images} image(s) et aucune annotation.",
                "Le nom du fichier seul ne suffit pas à choisir un dataset.",
            ],
        ))

    literal_path_issue = False
    for source in sources:
        for declared in source.declared:
            literal_missing = False
            stripped_inside = False
            for label, candidate, exists in declared.candidates:
                if label.startswith("relatif") and not exists:
                    literal_missing = True
                if label.startswith("préfixe") and exists and is_inside(candidate, src):
                    stripped_inside = True
            if literal_missing and stripped_inside:
                literal_path_issue = True

    announced_note = None
    announced_gap = None
    numbers = [number for number in announced_counts(readme_blob) if number >= 100]
    if numbers and readme_s2tld:
        announced = max(numbers)
        image_dirs: set[Path] = set()
        for source in sources:
            if not source_is_s2tld(source):
                continue
            for declared in source.declared:
                for _label, candidate, exists in declared.candidates:
                    if exists and candidate.is_dir() and candidate.name.lower() == "images" and is_inside(candidate, src):
                        image_dirs.add(candidate.resolve())
        counted = sum(stats[directory].direct_images for directory in image_dirs if directory in stats)
        announced_note = (
            f"Le README annonce {announced} images. "
            f"Les dossiers d'images locaux visés par le YAML s2tld en contiennent {counted} "
            f"({', '.join(relposix(path, src) for path in sorted(image_dirs)) or 'aucun'})."
        )
        if announced and abs(counted - announced) / announced > 0.05:
            announced_gap = (
                f"Le README s2tld annonce {announced} images, mais les dossiers locaux visés "
                f"en contiennent {counted}. Confirmez-vous que la différence vient d'un autre "
                f"dataset mélangé dans train/, valid/ ou test/ ?"
            )

    questions = build_questions(
        list(grouped.values()),
        image_only,
        sources,
        src,
        readmes,
        len(across),
        announced_gap,
        literal_path_issue,
    )
    text = render(
        src, stats, top_dirs, top_files, holders, sources, readmes, label_dirs,
        image_only, models, across, within, questions, errors, announced_note,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    existed = report_path.exists()
    report_path.write_text(text, encoding="utf-8", newline="\n")

    print(f"Source : {src}")
    print(f"Fichiers lus (métadonnées) : {len(files)}")
    print(f"Rapport : {report_path}")
    if existed:
        print("Le rapport précédent a été remplacé.")
    print("Aucune copie effectuée. Le dossier source n'a pas été modifié.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    raise SystemExit(main())
