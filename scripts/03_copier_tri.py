#!/usr/bin/env python3
"""Copie les jeux encore en source vers data/raw, selon la règle validée.

Règle pour les fichiers de _a_trier (classe 0 seule) :
- décision principale : préfixe de 6 chiffres → traffic_lights, sinon plates_detection
- contrôle : médiane l/h > 0,70 → plates_detection, sinon traffic_lights
- si les deux divergent, ou si le rapport est absent : data/raw/_incertains

Les 3 fichiers mixtes (rectangle et polygone) sont séparés ligne par ligne
avec le seuil 0,70. L'original va dans data/raw/_originaux/mixtes.

Les feux déjà identifiés (classe autre que 0, plus les 3 images négatives)
et les 1 596 images de dataset/ sont copiés tels quels.
dataset/ : la classe 0 doit être la plaque (obj.names = license_plate).

Le dossier source n'est pas modifié. quarantine/ n'est pas touché.
Aucun poids n'est ouvert. Défaut : dry-run. --apply copie.

    python scripts/03_copier_tri.py
    python scripts/03_copier_tri.py --apply
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import importlib.util


def load(name: str, filename: str):
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Import impossible : {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REORG = load("reorg_copy", "01_reorganize.py")
AFFINE = load("affine_copy", "02_affiner_a_trier.py")

PROJECT = REORG.PROJECT_ROOT
RAW = REORG.RAW
SRC_DEFAULT = REORG.DEFAULT_SRC
REPORTS = REORG.REPORTS
RATIO_THRESHOLD = 0.70


def dest_problem(dest: Path, src: Path) -> str | None:
    resolved = dest.resolve()
    quarantine = (PROJECT / "quarantine").resolve()
    if resolved == quarantine or REORG.is_inside(resolved, quarantine):
        return "refusé (quarantine)"
    if REORG.is_inside(resolved, src.resolve()):
        return "refusé (destination dans la source)"
    if not REORG.is_inside(resolved, PROJECT.resolve()):
        return "refusé (destination hors du projet)"
    return None


def prefix_decision(prefix: str) -> str:
    name = prefix
    if name.startswith("(sans "):
        pieces = name.split(") ", 1)
        name = pieces[1] if len(pieces) == 2 else name
    if name.isdigit() and len(name) == 6:
        return "traffic_lights"
    return "plates_detection"


def ratio_decision(ratio: float | None) -> str | None:
    if ratio is None:
        return None
    if ratio > RATIO_THRESHOLD:
        return "plates_detection"
    return "traffic_lights"


def line_ratio(kind: str, values: list[float]) -> float | None:
    if kind == "boite" and len(values) == 4 and values[3] > 1e-8:
        return values[2] / values[3]
    if kind == "polygone" and len(values) >= 6:
        xs = values[0::2]
        ys = values[1::2]
        height = max(ys) - min(ys)
        if height <= 1e-8:
            return None
        return (max(xs) - min(xs)) / height
    return None


def parse_lines(path: Path) -> list[tuple[str, str, float | None]]:
    """Chaque ligne non vide : (texte original, genre, rapport)."""
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    parsed: list[tuple[str, str, float | None]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        kind = "autre"
        ratio = None
        if len(parts) >= 5:
            try:
                values = [float(piece) for piece in parts[1:]]
            except ValueError:
                values = []
            if len(values) == 4:
                kind = "boite"
            elif len(values) >= 6 and len(values) % 2 == 0:
                kind = "polygone"
            ratio = line_ratio(kind, values) if values else None
        parsed.append((line.strip(), kind, ratio))
    return parsed


class Plan:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def add(
        self,
        source: Path,
        dest: Path | None,
        status: str,
        category: str,
        split: str,
        kind: str,
        rule: str,
        prefix: str,
        ratio: str,
        note: str,
        src: Path,
    ) -> None:
        self.rows.append({
            "source": REORG.relposix(source, src),
            "destination": "" if dest is None else dest.relative_to(PROJECT).as_posix(),
            "statut": status,
            "categorie": category,
            "split": split,
            "type": kind,
            "regle": rule,
            "prefixe": prefix,
            "ratio": ratio,
            "note": note,
        })

    def copy_file(
        self,
        source: Path,
        dest: Path,
        apply: bool,
        category: str,
        split: str,
        kind: str,
        rule: str,
        prefix: str,
        ratio: str,
        note: str,
        src: Path,
    ) -> None:
        problem = dest_problem(dest, src)
        if problem:
            self.add(source, dest, problem, category, split, kind, rule, prefix, ratio, note, src)
            return
        if dest.exists():
            status = "déjà présent, ignoré"
        elif not apply:
            status = "prévu"
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            status = "copié"
        self.add(source, dest, status, category, split, kind, rule, prefix, ratio, note, src)

    def write_text(
        self,
        source: Path,
        dest: Path,
        text: str,
        apply: bool,
        category: str,
        split: str,
        rule: str,
        prefix: str,
        ratio: str,
        note: str,
        src: Path,
    ) -> None:
        problem = dest_problem(dest, src)
        if problem:
            self.add(source, dest, problem, category, split, "label", rule, prefix, ratio, note, src)
            return
        if dest.exists():
            status = "déjà présent, ignoré"
        elif not apply:
            status = "label dérivé prévu"
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8", newline="\n")
            status = "label dérivé écrit"
        self.add(source, dest, status, category, split, "label", rule, prefix, ratio, note, src)


def pair_dest(category: str, split: str, label: Path, image: Path | None) -> tuple[Path, Path | None]:
    base = RAW / category / split
    label_dest = base / "labels" / label.name
    image_dest = None if image is None else base / "images" / image.name
    return label_dest, image_dest


def source_stamp(path: Path) -> str:
    if not path.is_file():
        return "absent"
    stat = path.stat()
    moment = datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{stat.st_size} octets, mtime {moment}"


def dataset_class_report(src: Path) -> tuple[list[str], Counter[int]]:
    labels = [path for path in REORG.walk_files(src / "dataset") if REORG.is_label_file(path)]
    counts: Counter[int] = Counter()
    bad: list[str] = []
    for path in labels:
        info = REORG.ANALYZE.classify_txt(path)
        counts.update(info.ids)
        if set(info.ids) - {0}:
            bad.append(REORG.relposix(path, src))
    names = src / "obj.names"
    declared = names.read_text(encoding="utf-8", errors="replace").strip() if names.is_file() else "(obj.names absent)"
    lines = [
        f"- Fichiers label de dataset/ : {len(labels)}.",
        f"- obj.names : {declared}.",
        f"- Identifiants de classe : {dict(sorted(counts.items()))}.",
    ]
    if declared.strip() == "license_plate" and set(counts) <= {0} and counts:
        lines.append("- Contrôle : la classe 0 de dataset/ est la plaque. Les labels sont copiés sans changer l'identifiant.")
    else:
        lines.append("- Contrôle surprenant : dataset/ n'est pas une classe 0 unique nommée license_plate. Les fichiers sont quand même copiés, sans réécriture.")
        for name in bad[:20]:
            lines.append(f"- Classe autre que 0 : `{name}`")
    return lines, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copie feux, plaques et _a_trier. Défaut : dry-run.")
    parser.add_argument("--src", type=Path, default=SRC_DEFAULT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    src = args.src.expanduser().resolve()
    problem = REORG.guard_paths(src)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    apply = args.apply
    weights = src / "yolov4-obj.weights"
    stamp_before = source_stamp(weights)

    plan = Plan()
    decisions: Counter[str] = Counter()
    divergences: list[str] = []
    mixed_notes: list[str] = []

    for split in ("train", "valid", "test"):
        labels_dir = src / split / "labels"
        images_dir = src / split / "images"
        if not labels_dir.is_dir():
            continue
        images = REORG.index_images(images_dir)
        labels = sorted(
            (path for path in labels_dir.iterdir() if path.is_file() and REORG.is_label_file(path)),
            key=lambda item: item.name.lower(),
        )
        for label in labels:
            info = REORG.ANALYZE.classify_txt(label)
            category, _group, note = REORG.route_mixed_label(split, info)
            matches = images.get(label.stem.casefold(), [])
            image = matches[0] if matches else None
            name = image.name if image is not None else label.name
            prefix = AFFINE.prefix_of(name)
            _count, boxes = AFFINE.parse_boxes(label)
            ratio = AFFINE.median([box.ratio for box in boxes if box.ratio is not None])
            ratio_text = "" if ratio is None else f"{ratio:.4f}"

            if category == "traffic_lights":
                label_dest, image_dest = pair_dest("traffic_lights", split, label, image)
                plan.copy_file(label, label_dest, apply, "traffic_lights", split, "label", "déjà feu", prefix, ratio_text, note, src)
                if image is not None:
                    plan.copy_file(image, image_dest, apply, "traffic_lights", split, "image", "déjà feu", prefix, ratio_text, note, src)
                for extra in matches[1:]:
                    plan.copy_file(extra, image_dest.parent / extra.name, apply, "traffic_lights", split, "image", "déjà feu", prefix, ratio_text, "autre extension", src)
                decisions["traffic_lights_deja"] += 1
                continue

            if info.syntax == "yolo_bbox_et_polygone":
                parsed = parse_lines(label)
                buckets: dict[str, list[str]] = {"plates_detection": [], "traffic_lights": [], "_incertains": []}
                for text, _kind, line_value in parsed:
                    side = ratio_decision(line_value)
                    if side is None:
                        buckets["_incertains"].append(text)
                    else:
                        buckets[side].append(text)
                origin_label = RAW / "_originaux" / "mixtes" / split / "labels" / label.name
                plan.copy_file(label, origin_label, apply, "_originaux", split, "label", "mixte original", prefix, ratio_text, "original conservé", src)
                if image is not None:
                    origin_image = RAW / "_originaux" / "mixtes" / split / "images" / image.name
                    plan.copy_file(image, origin_image, apply, "_originaux", split, "image", "mixte original", prefix, ratio_text, "original conservé", src)
                parts = []
                for dest_name, lines in buckets.items():
                    if not lines:
                        continue
                    body = "\n".join(lines) + "\n"
                    label_dest, image_dest = pair_dest(dest_name, split, label, image)
                    plan.write_text(
                        label, label_dest, body, apply, dest_name, split,
                        "mixte ligne l/h 0,70", prefix, ratio_text,
                        f"{len(lines)} ligne(s)", src,
                    )
                    if image is not None and image_dest is not None:
                        plan.copy_file(image, image_dest, apply, dest_name, split, "image", "mixte ligne l/h 0,70", prefix, ratio_text, f"{len(lines)} ligne(s)", src)
                    parts.append(f"{dest_name} {len(lines)}")
                mixed_notes.append(f"{REORG.relposix(label, src)} → {', '.join(parts)}")
                decisions["mixte"] += 1
                continue

            by_prefix = prefix_decision(prefix)
            by_ratio = ratio_decision(ratio)
            if by_ratio is None or by_prefix != by_ratio:
                chosen = "_incertains"
                rule = "divergence préfixe/ratio"
                divergences.append(f"{REORG.relposix(label, src)} préfixe={by_prefix} ratio={by_ratio} l/h={ratio_text}")
            else:
                chosen = by_prefix
                rule = "préfixe et ratio d'accord"
            label_dest, image_dest = pair_dest(chosen, split, label, image)
            plan.copy_file(label, label_dest, apply, chosen, split, "label", rule, prefix, ratio_text, note, src)
            if image is not None and image_dest is not None:
                plan.copy_file(image, image_dest, apply, chosen, split, "image", rule, prefix, ratio_text, note, src)
            for extra in matches[1:]:
                plan.copy_file(extra, image_dest.parent / extra.name, apply, chosen, split, "image", rule, prefix, ratio_text, "autre extension", src)
            decisions[chosen] += 1

    class_lines, _class_counts = dataset_class_report(src)
    dataset_root = src / "dataset"
    seen_names: dict[str, list[Path]] = {"image": [], "label": []}
    if dataset_root.is_dir():
        for path in REORG.walk_files(dataset_root):
            if REORG.is_model(path):
                plan.add(path, None, "ignoré (poids ou cfg, non ouvert)", "plates_detection", "dataset", "modele", "interdit", "", "", "non copié, quarantine non touchée", src)
                continue
            if REORG.is_image(path):
                kind = "image"
                dest = RAW / "plates_detection" / "dataset" / "images" / path.relative_to(dataset_root)
            elif REORG.is_label_file(path):
                kind = "label"
                dest = RAW / "plates_detection" / "dataset" / "labels" / path.relative_to(dataset_root)
            else:
                plan.add(path, None, "ignoré", "plates_detection", "dataset", "autre", "dataset", "", "", "ni image ni label", src)
                continue
            seen_names[kind].append(path)
            plan.copy_file(path, dest, apply, "plates_detection", "dataset", kind, "dataset license_plate", "", "", "classe 0 = plaque", src)
        decisions["dataset_images"] = sum(1 for path in seen_names["image"])
        decisions["dataset_labels"] = sum(1 for path in seen_names["label"])

    stamp_after = source_stamp(weights)
    REPORTS.mkdir(parents=True, exist_ok=True)
    journal = REPORTS / "copie_journal.csv"
    fields = ["source", "destination", "statut", "categorie", "split", "type", "regle", "prefixe", "ratio", "note"]
    with journal.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(plan.rows)

    status_counts = Counter(str(row["statut"]) for row in plan.rows)
    category_files = Counter((str(row["categorie"]), str(row["type"])) for row in plan.rows if str(row["statut"]) in {"prévu", "copié", "déjà présent, ignoré", "label dérivé prévu", "label dérivé écrit"})
    mode = "apply" if apply else "dry-run"
    lines = [
        "# Copie selon la règle validée",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Mode : {mode}.",
        "- Source non modifiée. quarantine/ non touché. Aucun poids ouvert.",
        "- Règle : préfixe de 6 chiffres → feu, sinon plaque. Contrôle : médiane l/h > 0,70 → plaque, sinon feu. Désaccord → `_incertains`.",
        "- Fichiers mixtes : séparation ligne par ligne au seuil 0,70. Original dans `data/raw/_originaux/mixtes`.",
        "",
        "## Décisions fichier",
        "",
        f"- Feux déjà identifiés (y compris images négatives) : {decisions['traffic_lights_deja']}.",
        f"- _a_trier vers traffic_lights : {decisions['traffic_lights']}.",
        f"- _a_trier vers plates_detection : {decisions['plates_detection']}.",
        f"- _a_trier vers _incertains : {decisions['_incertains']}.",
        f"- Fichiers mixtes séparés : {decisions['mixte']}.",
        f"- Images dataset/ : {decisions['dataset_images']}. Labels dataset/ : {decisions['dataset_labels']}.",
        "",
        "## Statuts",
        "",
    ]
    for name, count in sorted(status_counts.items()):
        lines.append(f"- {name} : {count}")
    lines += ["", "## Fichiers par destination", ""]
    for (category, kind), count in sorted(category_files.items()):
        lines.append(f"- {category} / {kind} : {count}")
    lines += ["", "## Contrôle dataset/", ""]
    lines.extend(class_lines)
    lines += ["", "## Fichiers mixtes", ""]
    if mixed_notes:
        for note in mixed_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- Aucun fichier mixte.")
    lines += ["", "## Divergences préfixe / ratio", ""]
    if divergences:
        lines.append(f"{len(divergences)} fichier(s). Ils vont dans `data/raw/_incertains`.")
        lines.append("")
        for item in divergences:
            lines.append(f"- {item}")
    else:
        lines.append("- Aucune divergence. Le préfixe et le rapport 0,70 donnent le même groupe pour chaque fichier non mixte.")
    lines += [
        "",
        "## Poids source (non ouvert)",
        "",
        f"- Avant : {stamp_before}",
        f"- Après : {stamp_after}",
        f"- Inchangé : {'oui' if stamp_before == stamp_after else 'NON, à vérifier'}.",
        "",
        "Journal : `reports/copie_journal.csv`.",
        "",
    ]
    report = REPORTS / "copie_tri.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Mode : {mode}")
    print(f"Feux déjà identifiés : {decisions['traffic_lights_deja']}")
    print(f"a_trier feux / plaques / incertains / mixtes : {decisions['traffic_lights']} {decisions['plates_detection']} {decisions['_incertains']} {decisions['mixte']}")
    print(f"dataset images/labels : {decisions['dataset_images']} {decisions['dataset_labels']}")
    print(f"Divergences : {len(divergences)}")
    print(f"Poids inchangé : {stamp_before == stamp_after}")
    print(f"Rapport : {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
