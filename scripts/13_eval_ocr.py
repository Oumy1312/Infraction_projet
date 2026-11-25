#!/usr/bin/env python3
"""Plaque entière exacte et CER, avec intervalle bootstrap. Synthétique et réel séparés.

Les 150 plaques réelles ne servent qu'ici. Elles n'entrent pas dans l'entraînement.

    python scripts/13_eval_ocr.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import cv2

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.crnn import WEIGHTS_PATH as CRNN_WEIGHTS  # noqa: E402
from src.crnn import charger as charger_crnn  # noqa: E402
from src.crnn import lire as lire_crnn  # noqa: E402
from src.ocr_plaque import WEIGHTS_PATH  # noqa: E402
from src.ocr_plaque import charger_format, charger_modele, intervalle_bootstrap, lire_plaque, normaliser, taux_erreur  # noqa: E402
from src.qualite_plaque import est_coupee, qualite_suffisante, vehicule_de  # noqa: E402

SYNTH = PROJECT / "data" / "synthetic" / "plaques"
REAL = PROJECT / "data" / "test_plaques" / "verite.csv"


def lire_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def lecteurs(fmt):
    found = []
    if WEIGHTS_PATH.is_file():
        model, names = charger_modele(WEIGHTS_PATH)
        found.append(("segmentation + CNN", lambda image, m=model, n=names: lire_plaque(image, m, n, fmt)["texte"]))
    if CRNN_WEIGHTS.is_file():
        model, alphabet = charger_crnn(CRNN_WEIGHTS)
        found.append(("CRNN", lambda image, m=model, a=alphabet: lire_crnn(m, a, image)))
    return found


def juger(reference: str, prediction: str) -> dict:
    return {"exact": reference == prediction, "cer": taux_erreur(reference, prediction)}


def evaluer_synthetique(reader, fmt, limit: int) -> list[dict]:
    rows = []
    folder = SYNTH / "images"
    for record in lire_csv(SYNTH / "etiquettes.csv"):
        if record.get("part") != "eval":
            continue
        if limit and len(rows) >= limit:
            break
        image = cv2.imread(str(folder / record["image"]))
        if image is None:
            continue
        reference = normaliser(record.get("caracteres", ""), fmt)
        prediction = normaliser(reader(image), fmt)
        mark = juger(reference, prediction)
        rows.append(
            {
                **mark,
                "qualite": qualite_suffisante(image, coupee=False),
                "vehicule": "voiture",
                "image": record["image"],
                "reference": reference,
                "prediction": prediction,
            }
        )
    return rows


def evaluer_reel(reader, fmt, csv_path: Path) -> tuple[list[dict], int, int]:
    rows = []
    vides = 0
    illisibles = 0
    folder = csv_path.parent / "images"
    for record in lire_csv(csv_path):
        if record.get("exclu") == "oui":
            illisibles += 1
            continue
        reference = normaliser(record.get("transcription", ""), fmt)
        if not reference:
            vides += 1
            continue
        image = cv2.imread(str(folder / record["fichier"]))
        if image is None:
            continue
        origine = PROJECT / record.get("origine", "")
        coupee = est_coupee(origine) if origine.is_file() else False
        prediction = normaliser(reader(image), fmt)
        mark = juger(reference, prediction)
        rows.append(
            {
                **mark,
                "qualite": qualite_suffisante(image, coupee),
                "vehicule": vehicule_de(record.get("source", "")),
                "image": record["fichier"],
                "reference": reference,
                "prediction": prediction,
            }
        )
    return rows, vides, illisibles


def sous_ensembles(rows: list[dict], reel: bool) -> list[tuple[str, list[dict]]]:
    groups = [("toutes", rows), ("qualité suffisante", [row for row in rows if row["qualite"]])]
    if reel:
        groups.extend(
            [
                ("voitures, toutes", [row for row in rows if row["vehicule"] == "voiture"]),
                ("motos, toutes", [row for row in rows if row["vehicule"] == "moto"]),
                ("voitures, qualité suffisante", [row for row in rows if row["vehicule"] == "voiture" and row["qualite"]]),
                ("motos, qualité suffisante", [row for row in rows if row["vehicule"] == "moto" and row["qualite"]]),
            ]
        )
    return groups


def formater(summary: dict) -> str:
    if summary["n"] == 0:
        return "| 0 | — | — | — | — |"
    return (
        f"| {summary['n']} "
        f"| {100 * summary['exact']:.1f} % "
        f"| {100 * summary['exact_bas']:.1f} % – {100 * summary['exact_haut']:.1f} % "
        f"| {100 * summary['cer']:.1f} % "
        f"| {100 * summary['cer_bas']:.1f} % – {100 * summary['cer_haut']:.1f} % |"
    )


def bloc(method: str, jeu: str, rows: list[dict], reel: bool, libelle: str) -> list[str]:
    lines = [
        f"### {method} — {jeu}",
        "",
        libelle,
        "",
        "| Sous-ensemble | N | Plaque entière exacte | IC 95 % | CER | IC 95 % |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, group in sous_ensembles(rows, reel):
        summary = intervalle_bootstrap([row["exact"] for row in group], [row["cer"] for row in group])
        lines.append(f"| {name} {formater(summary)}")
    misses = [row for row in rows if not row["exact"]][:12]
    if misses:
        lines.extend(["", "Écarts, 12 premiers :", "", "| Image | Référence | Lecture |", "| --- | --- | --- |"])
        for row in misses:
            lines.append(f"| {row['image']} | {row['reference']} | {row['prediction']} |")
    lines.append("")
    return lines


def composition_reelle(csv_path: Path) -> list[str]:
    from collections import Counter

    counts: Counter[tuple[str, str]] = Counter()
    for record in lire_csv(csv_path):
        image = cv2.imread(str(csv_path.parent / "images" / record["fichier"]))
        if image is None:
            continue
        origine = PROJECT / record.get("origine", "")
        coupee = est_coupee(origine) if origine.is_file() else False
        groupe = "qualité suffisante" if qualite_suffisante(image, coupee) else "en dessous du critère"
        counts[(vehicule_de(record.get("source", "")), groupe)] += 1
    lines = [
        "## Composition des 150 plaques réelles, avant toute transcription",
        "",
        "Ce tableau ne mesure pas une lecture. Il compte les images selon le critère fixé et selon la source (`moped` = moto).",
        "",
        "| Véhicule | Groupe | Images |",
        "| --- | --- | --- |",
    ]
    for key in sorted(counts):
        lines.append(f"| {key[0]} | {key[1]} | {counts[key]} |")
    lines.append("")
    return lines


def rappel_segmentes() -> list[str]:
    path = PROJECT / "reports" / "ocr_chars.md"
    if not path.is_file():
        return []
    return [
        "## Chiffre qui n'est pas une lecture de plaque entière",
        "",
        "Dans `reports/ocr_chars.md`, l'exactitude de la CNN porte sur des caractères synthétiques déjà segmentés, et seulement quand le nombre de contours égalait le texte posé. Ce n'est pas la précision globale, ni un score de plaque entière, ni un score réel.",
        "",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Évalue la segmentation+CNN et le CRNN, à part.")
    parser.add_argument("--verite", type=Path, default=REAL)
    parser.add_argument("--limite-synth", type=int, default=0, help="0 = toutes les plaques synthétiques tenues à part")
    args = parser.parse_args()
    fmt = charger_format()
    methods = lecteurs(fmt)
    if not methods:
        raise SystemExit("aucun poids : ocr_chars.pt ou crnn.pt")
    parts = [
        "# Comparaison des lectures de plaque",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Chaque ligne dit ce qu'elle mesure. Aucun de ces chiffres n'est une précision globale.",
        "- Intervalle de confiance : bootstrap, 1 000 tirages avec remise, quantiles 2,5 % et 97,5 %, graine 42.",
        "- CER = distance de Levenshtein / longueur de la référence.",
        "- La qualité suffisante est le critère de `docs/critere_qualite_plaque.md`, fixé avant cette mesure.",
        "- Les plaques réelles ne servent pas à l'entraînement. Une plaque marquée illisible est exclue.",
        "- Synthétique : la part `eval` de `data/synthetic/plaques`. Le cyclomoteur n'y est pas généré, donc pas de ligne moto.",
        "",
    ]
    parts.append(
        "Sur le jeu synthétique déjà écrit, les images tenues à part qui passent le critère sont signalées à part. Si les deux lignes ont le même effectif, toutes ces images passent le critère."
    )
    parts.append("")
    parts.extend(rappel_segmentes())
    parts.extend(composition_reelle(args.verite))
    eval_lines = [
        "# Évaluation OCR",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Synthétique et réel sont séparés. Les plaques réelles ne servent pas à l'entraînement.",
        "",
    ]
    for name, reader in methods:
        synthetic = evaluer_synthetique(reader, fmt, args.limite_synth)
        real, empty, skipped = evaluer_reel(reader, fmt, args.verite)
        label_s = (
            "Synthétique, plaque entière, part tenue à part, générateur déjà écrit dans `etiquettes.csv`. "
            "Ce n'est pas le score des caractères déjà segmentés."
        )
        label_r = (
            "Réel, plaque entière, transcriptions saisies dans `data/test_plaques/verite.csv`. "
            "Voiture = toute source sauf `moped`. Moto = source `moped`."
        )
        parts.extend(bloc(name, "synthétique tenu à part", synthetic, False, label_s))
        parts.extend(bloc(name, "réel", real, True, label_r))
        eval_lines.extend(bloc(name, "synthétique tenu à part", synthetic, False, label_s))
        eval_lines.append(f"Lignes réelles sans transcription : {empty}. Plaques illisibles exclues : {skipped}.")
        eval_lines.append("")
        eval_lines.extend(bloc(name, "réel", real, True, label_r))
    comparison = PROJECT / "reports" / "ocr_comparaison.md"
    evaluation = PROJECT / "reports" / "ocr_eval.md"
    comparison.write_text("\n".join(parts) + "\n", encoding="utf-8")
    evaluation.write_text("\n".join(eval_lines) + "\n", encoding="utf-8")
    print(comparison)
    print(evaluation)


if __name__ == "__main__":
    main()
