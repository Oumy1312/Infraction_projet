#!/usr/bin/env python3
"""Convertit les polygones YOLO en rectangles dans data/interim.

Le rectangle est le min/max des points, en coordonnées normalisées.
Les rectangles déjà présents sont réécrits au même format.
data/raw et le dossier source ne sont pas modifiés.
Une planche de 40 conversions (graine 42) est écrite dans reports/.

    python scripts/03_polygones.py
"""

from __future__ import annotations

import importlib.util
import random
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError


def load(name: str, filename: str):
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Import impossible : {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REORG = load("reorg_poly", "01_reorganize.py")
PROJECT = REORG.PROJECT_ROOT
RAW = PROJECT / "data" / "raw"
INTERIM = PROJECT / "data" / "interim"
REPORTS = PROJECT / "reports"
DATASETS = ("traffic_lights", "plates_detection", "vehicles", "_incertains")
SEED = 42
PAGE = 40


def corners(parts: list[str]) -> tuple[int, float, float, float, float, str] | None:
    try:
        class_id = int(float(parts[0]))
        values = [float(piece) for piece in parts[1:]]
    except ValueError:
        return None
    if len(values) == 4:
        cx, cy, width, height = values
        return class_id, cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2, "boite"
    if len(values) >= 6 and len(values) % 2 == 0:
        xs = values[0::2]
        ys = values[1::2]
        return class_id, min(xs), min(ys), max(xs), max(ys), "polygone"
    return None


def as_yolo(class_id: int, x1: float, y1: float, x2: float, y2: float) -> str | None:
    width = x2 - x1
    height = y2 - y1
    if width <= 1e-8 or height <= 1e-8:
        return None
    return f"{class_id} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {width:.6f} {height:.6f}"


def image_for(label: Path) -> Path | None:
    current = label.parent
    nested: list[str] = []
    while current.name != "labels":
        nested.append(current.name)
        if current.parent == current:
            return None
        current = current.parent
    folder = current.parent / "images"
    if nested:
        folder = folder.joinpath(*reversed(nested))
    if not folder.is_dir():
        return None
    hits = [
        path for path in folder.iterdir()
        if path.is_file() and path.stem == label.stem and path.suffix.lower() in REORG.IMAGE_EXTS
    ]
    return hits[0] if hits else None


def iter_labels():
    for name in DATASETS:
        root = RAW / name
        if not root.is_dir():
            continue
        for path in REORG.walk_files(root):
            if REORG.is_label_file(path) and "labels" in path.parts:
                yield name, path


def draw_sheet(samples: list[dict[str, object]], destination: Path) -> None:
    columns = 5
    rows = (len(samples) + columns - 1) // columns
    cell_w, cell_h, pad = 280, 180, 10
    header = 70
    width = pad + columns * (cell_w + pad)
    height = header + rows * (cell_h + 36 + pad)
    sheet = Image.new("RGB", (width, height), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    font = REORG.font(14)
    draw.text((pad, 12), f"40 conversions polygone → rectangle   |   graine {SEED}", fill=(240, 240, 240), font=font)
    draw.text((pad, 36), "Orange : polygone d'origine. Vert : rectangle min/max. Rien n'est modifié dans data/raw.", fill=(200, 200, 200), font=font)
    for index, sample in enumerate(samples):
        column = index % columns
        row = index // columns
        origin_x = pad + column * (cell_w + pad)
        origin_y = header + row * (cell_h + 36 + pad)
        image_path = sample["image"]
        try:
            with Image.open(image_path) as raw:
                frame = raw.convert("RGB")
                scale = min(cell_w / frame.width, cell_h / frame.height)
                resized = frame.resize((max(1, int(frame.width * scale)), max(1, int(frame.height * scale))))
            canvas = Image.new("RGB", (cell_w, cell_h), (32, 32, 32))
            offset_x = (cell_w - resized.width) // 2
            offset_y = (cell_h - resized.height) // 2
            canvas.paste(resized, (offset_x, offset_y))
            pen = ImageDraw.Draw(canvas)
            with Image.open(image_path) as sized:
                full_w, full_h = sized.size

            def point(x_norm: float, y_norm: float) -> tuple[int, int]:
                return (
                    offset_x + int(x_norm * full_w * resized.width / full_w),
                    offset_y + int(y_norm * full_h * resized.height / full_h),
                )

            for poly in sample["polys"]:
                pen.line([point(x, y) for x, y in poly] + [point(*poly[0])], fill=(255, 140, 40), width=2)
            for x1, y1, x2, y2 in sample["rects"]:
                pen.rectangle([point(x1, y1), point(x2, y2)], outline=(40, 200, 80), width=2)
            sheet.paste(canvas, (origin_x, origin_y))
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            draw.rectangle([origin_x, origin_y, origin_x + cell_w, origin_y + cell_h], outline=(180, 60, 60))
        caption = Path(str(image_path)).name
        if len(caption) > 40:
            caption = caption[:18] + "…" + caption[-18:]
        draw.text((origin_x, origin_y + cell_h + 4), caption, fill=(220, 220, 220), font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, format="JPEG", quality=85)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    converted_files = 0
    polygon_lines = 0
    box_lines = 0
    dropped = 0
    written = 0
    samples: list[dict[str, object]] = []
    for dataset, label in iter_labels():
        raw = label.read_text(encoding="utf-8-sig", errors="replace")
        output: list[str] = []
        polys: list[list[tuple[float, float]]] = []
        rects: list[tuple[float, float, float, float]] = []
        had_poly = False
        for line in raw.splitlines():
            if not line.strip():
                continue
            parsed = corners(line.split())
            if parsed is None:
                dropped += 1
                continue
            class_id, x1, y1, x2, y2, kind = parsed
            if kind == "polygone":
                had_poly = True
                polygon_lines += 1
                values = [float(piece) for piece in line.split()[1:]]
                polys.append(list(zip(values[0::2], values[1::2])))
            else:
                box_lines += 1
            text = as_yolo(class_id, x1, y1, x2, y2)
            if text is None:
                dropped += 1
                continue
            output.append(text)
            rects.append((x1, y1, x2, y2))
        relative = label.relative_to(RAW)
        dest = INTERIM / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(("\n".join(output) + ("\n" if output else "")), encoding="utf-8", newline="\n")
        written += 1
        if had_poly:
            converted_files += 1
            image = image_for(label)
            if image is not None and polys:
                samples.append({"image": image, "polys": polys, "rects": rects, "dataset": dataset})
    picker = random.Random(SEED)
    if len(samples) > PAGE:
        chosen = picker.sample(samples, PAGE)
    else:
        chosen = samples
    chosen.sort(key=lambda item: Path(str(item["image"])).name.lower())
    sheet = REPORTS / "contact_polygones.jpg"
    if chosen:
        draw_sheet(chosen, sheet)
    lines = [
        "# Conversion polygone → rectangle",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Les originaux de `data/raw` et du dossier source sont inchangés.",
        "- Rectangle : min et max des points, coordonnées normalisées. Les boîtes déjà rectangulaires sont réécrites au même format.",
        "",
        f"- Labels écrits dans `data/interim` : {written}.",
        f"- Fichiers qui contenaient au moins un polygone : {converted_files}.",
        f"- Lignes polygone converties : {polygon_lines}.",
        f"- Lignes déjà rectangulaires : {box_lines}.",
        f"- Lignes écartées (illisible ou taille nulle) : {dropped}.",
        f"- Planche : `{sheet.relative_to(PROJECT).as_posix()}` ({len(chosen)} images, graine {SEED}).",
        "",
    ]
    report = REPORTS / "polygones.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Labels interim : {written}")
    print(f"Fichiers polygone : {converted_files}")
    print(f"Lignes polygone : {polygon_lines}")
    print(f"Écartées : {dropped}")
    print(f"Planche : {len(chosen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
