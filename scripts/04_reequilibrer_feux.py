#!/usr/bin/env python3
"""Replace the light split so near-duplicate groups still stay together
and the 70/20/10 shares are recovered. Does not retrain anything.
"""

from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

from tqdm import tqdm

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))


def load_controls():
    spec = importlib.util.spec_from_file_location(
        "controles", PROJECT / "scripts" / "04_controles_pre_train.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["controles"] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    controls = load_controls()
    rows = controls.list_images("traffic_lights")
    hashes = [
        controls.phash_int(path)
        for path, _split in tqdm(rows, desc="pHash feux", unit="img")
    ]
    before = Counter(split for _path, split in rows)
    print("Avant rééquilibrage", dict(before), flush=True)
    assignment = controls.assign_lights(rows, hashes)
    new_rows = [(path, assignment[path]) for path, _split in rows]
    phash_after, _best = controls.cross_pairs(new_rows, hashes)
    consecutive = controls.consecutive_cross(new_rows)
    proche = Counter()
    numbered = []
    for path, split in new_rows:
        value = controls.six_digit(path.name)
        if value is not None:
            numbered.append((value, split))
    numbered.sort()
    for (left_id, left_split), (right_id, right_split) in zip(numbered, numbered[1:]):
        if 0 < right_id - left_id <= controls.PROCHE_GAP and left_split != right_split:
            proche[tuple(sorted((left_split, right_split)))] += 1
    print("pHash après", dict(phash_after), flush=True)
    print("Consécutifs après", dict(consecutive), flush=True)
    print("Proches après", dict(proche), flush=True)
    if phash_after or consecutive or proche:
        raise SystemExit("Le rééquilibrage reprend des fuites, aucun fichier déplacé.")
    empty = Counter()
    for image, split in new_rows:
        label = controls.label_path(image)
        if label.is_file() and label.read_text(encoding="utf-8").strip() == "":
            empty[split] += 1
    moved = controls.apply_assignment(rows, assignment)
    after = Counter(split for _path, split in new_rows)
    print(f"Déplacés : {moved}", flush=True)
    print("Après", dict(after), flush=True)
    print("Négatifs", dict(empty), flush=True)
    report = PROJECT / "reports" / "fuites.md"
    text = report.read_text(encoding="utf-8")
    marker = "## Après le regroupement des feux"
    head = text.split(marker)[0].rstrip()
    total = sum(after.values())
    lines = [
        marker,
        "",
        "Le premier placement mettait les plus gros groupes dans train "
        f"({before['train']} / {before['val']} / {before['test']}). "
        "Les fuites étaient déjà à zéro, mais test tombait à 5 %. "
        "Le placement a été refait : chaque groupe va dans le sous-ensemble "
        "qu'il fait le moins déborder de sa cible 70/20/10.",
        "",
        f"- Images déplacées lors de ce rééquilibrage : {moved}.",
        "- traffic_lights : "
        + ", ".join(
            f"{name} {after[name]} ({after[name] / total:.1%})"
            for name in ("train", "val", "test")
        )
        + ".",
        f"- Paires pHash entre sous-ensembles : {controls.fmt_counter(phash_after)}.",
        f"- Numéros consécutifs entre sous-ensembles : {controls.fmt_counter(consecutive)}.",
        f"- Numéros proches (écart <= 2) entre sous-ensembles : {controls.fmt_counter(proche)}.",
        "",
        "Les jeux vehicles et plates_detection n'ont pas été redécoupés. "
        "Leurs paires sont dans le tableau Avant.",
        "",
        "Planche de 30 exemples (état avant, priorité aux paires train/test) : "
        "`reports/contact_fuites.jpg`.",
        "",
    ]
    report.write_text(head + "\n\n" + "\n".join(lines), encoding="utf-8", newline="\n")
    print("Rapport mis à jour", flush=True)


if __name__ == "__main__":
    main()
