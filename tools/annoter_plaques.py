#!/usr/bin/env python3
"""Choisit 150 plaques réelles et enregistre leur transcription.

Préparer les images :

    python tools/annoter_plaques.py --preparer

Saisir les transcriptions :

    streamlit run tools/annoter_plaques.py
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

import cv2

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.plaques_reelles import lister, nettete, recadrer  # noqa: E402

DEST = PROJECT / "data" / "test_plaques"
CSV_PATH = DEST / "verite.csv"
IMAGES = DEST / "images"
COLUMNS = ("fichier", "source", "origine", "transcription", "remarque", "exclu")
SEED = 42
N = 150


def _lire() -> list[dict]:
    if not CSV_PATH.is_file():
        return []
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _ecrire(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in COLUMNS})


def preparer(n: int = N, dest: Path | None = None) -> int:
    global DEST, CSV_PATH, IMAGES
    if dest is not None:
        DEST = dest
        CSV_PATH = dest / "verite.csv"
        IMAGES = dest / "images"
    if CSV_PATH.is_file() and len(_lire()) >= n:
        return len(_lire())
    measured = []
    for item in lister():
        crop = recadrer(item)
        if crop is None or crop.shape[1] < 80 or crop.shape[0] < 28:
            continue
        measured.append({**item, "crop": crop, "sharp": nettete(crop)})
    rng = random.Random(SEED)
    by_source: dict[str, list[dict]] = {}
    for row in measured:
        by_source.setdefault(row["source"], []).append(row)
    for group in by_source.values():
        rng.shuffle(group)
    chosen = []
    sources = sorted(by_source)
    while len(chosen) < n and any(by_source[source] for source in sources):
        for source in sources:
            pool = by_source[source]
            if pool and len(chosen) < n:
                chosen.append(pool.pop())
    IMAGES.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, row in enumerate(chosen, start=1):
        filename = f"{index:03d}_{row['source']}.jpg"
        cv2.imwrite(str(IMAGES / filename), row["crop"])
        rows.append(
            {
                "fichier": filename,
                "source": row["source"],
                "origine": str(row["image"].relative_to(PROJECT)),
                "transcription": "",
                "remarque": "",
                "exclu": "",
            }
        )
    _ecrire(rows)
    return len(rows)


def _dans_streamlit() -> bool:
    if "streamlit" not in sys.modules and not any("streamlit" in arg for arg in sys.argv):
        return False
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


def terminee(row: dict) -> bool:
    return row.get("exclu") == "oui" or bool((row.get("transcription") or "").strip())


def premiere_restante(rows: list[dict]) -> int:
    for index, row in enumerate(rows):
        if not terminee(row):
            return index
    return 0


def suivante(rows: list[dict], index: int) -> int:
    for cursor in range(index + 1, len(rows)):
        if not terminee(rows[cursor]):
            return cursor
    return premiere_restante(rows)


def interface() -> None:
    import streamlit as st

    from src.ocr_plaque import charger_format

    preparer()
    rows = _lire()
    fmt = charger_format()
    st.title("Transcription de plaques réelles")
    st.caption("Les boutons viennent de configs/plaque_format.yaml. Ne pas taper les filets. Une plaque illisible est exclue de l'évaluation.")
    if not rows:
        st.warning("Aucune plaque préparée.")
        return
    faites = sum(1 for row in rows if (row.get("transcription") or "").strip())
    illisibles = sum(1 for row in rows if row.get("exclu") == "oui")
    restantes = len(rows) - faites - illisibles
    st.progress((faites + illisibles) / len(rows))
    st.write(f"{faites} transcrites, {illisibles} illisibles, {restantes} restantes sur {len(rows)}. La reprise ouvre la première plaque non terminée.")
    if "index" not in st.session_state:
        st.session_state.index = premiere_restante(rows)
    index = min(st.session_state.index, len(rows) - 1)
    row = rows[index]
    if st.session_state.get("fichier") != row["fichier"]:
        st.session_state.fichier = row["fichier"]
        st.session_state.brouillon = row.get("transcription") or ""
    st.image(str(IMAGES / row["fichier"]), caption=f"{index + 1}/{len(rows)} — {row['source']} — {row['fichier']}")
    st.subheader(st.session_state.brouillon or "(vide)")
    if st.session_state.get("message"):
        st.info(st.session_state.message)

    def ajouter(caractere: str) -> None:
        st.session_state.brouillon += caractere
        st.session_state.message = ""

    def effacer() -> None:
        st.session_state.brouillon = st.session_state.brouillon[:-1]
        st.session_state.message = ""

    def enregistrer(exclu: bool) -> None:
        if exclu:
            row["exclu"] = "oui"
            row["transcription"] = ""
        else:
            texte = st.session_state.brouillon.strip()
            if not texte:
                st.session_state.message = "Rien à enregistrer : ajouter un caractère, ou marquer illisible."
                return
            row["exclu"] = ""
            row["transcription"] = texte
        _ecrire(rows)
        st.session_state.index = suivante(rows, index)
        st.session_state.fichier = None
        st.session_state.message = ""

    def reculer() -> None:
        st.session_state.index = max(0, index - 1)
        st.session_state.fichier = None

    digits = list(dict.fromkeys(fmt.chiffres))
    digit_cols = st.columns(len(digits))
    for column, caractere in zip(digit_cols, digits):
        column.button(caractere, key=f"chiffre-{caractere}", on_click=ajouter, args=(caractere,))
    letters = list(dict.fromkeys(fmt.lettres))
    for start in range(0, len(letters), 7):
        group = letters[start : start + 7]
        letter_cols = st.columns(7)
        for column, caractere in zip(letter_cols, group):
            column.button(caractere, key=f"lettre-{start}-{caractere}", on_click=ajouter, args=(caractere,))
    actions = st.columns(4)
    actions[0].button("effacer le dernier caractère", on_click=effacer)
    actions[1].button("illisible", on_click=enregistrer, args=(True,))
    actions[2].button("suivant", on_click=enregistrer, args=(False,))
    actions[3].button("précédent", on_click=reculer)


def main() -> None:
    if _dans_streamlit():
        interface()
        return
    parser = argparse.ArgumentParser(description="Prépare 150 plaques à transcrire.")
    parser.add_argument("--preparer", action="store_true")
    parser.add_argument("--nombre", type=int, default=N)
    args = parser.parse_args()
    count = preparer(args.nombre)
    print(f"{count} plaques dans {CSV_PATH}")


if __name__ == "__main__":
    main()
