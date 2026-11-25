import csv
import importlib.util
import random
import sys
from pathlib import Path

import numpy as np
import torch

from src.crnn import PetitCRNN, reduire_ctc
from src.ocr_plaque import (
    caracteres_de,
    charger_format,
    compiler_regex,
    distance_edition,
    intervalle_bootstrap,
    normaliser,
    plausible,
    scores,
    statuts,
    taux_erreur,
    texte_de,
    tirer_parties,
)
from src.qualite_plaque import HAUTEUR_MIN, LAPLACIEN_MIN, LARGEUR_MIN, qualite_suffisante, vehicule_de
from src.segmentation import segmenter

ROOT = Path(__file__).resolve().parents[1]


def _synth():
    spec = importlib.util.spec_from_file_location("synth_plaques", ROOT / "scripts" / "04_synth_plates.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["synth_plaques"] = module
    spec.loader.exec_module(module)
    return module


def test_chaque_valeur_est_a_valider():
    fmt = charger_format()
    found = statuts(fmt.raw)
    assert len(found) >= 8
    assert {value for _, value in found} == {"À VALIDER"}


def test_la_regex_suit_le_fichier():
    fmt = charger_format()
    motif = compiler_regex(fmt)
    rng = random.Random(42)
    for _ in range(30):
        parties = tirer_parties(fmt, rng)
        assert motif.fullmatch(texte_de(parties, fmt))
        assert motif.fullmatch(caracteres_de(parties, fmt))
    assert motif.fullmatch("ABC") is None
    assert motif.fullmatch("") is None


def test_scores_caractere_par_caractere():
    assert distance_edition("1749ب40", "1749ب41") == 1
    mark = scores("1749ب40", "1749ب41")
    assert mark["exact"] is False
    assert mark["caracteres"] == 6 / 7
    fmt = charger_format()
    assert normaliser("12  ب  3", fmt) == "12ب3"


def test_segmentation_retrouve_souvent_le_nombre_pose():
    module = _synth()
    fmt = charger_format()
    polices = {
        "lettres": [Path(r"C:\Windows\Fonts\tahomabd.ttf")],
        "chiffres": [Path(r"C:\Windows\Fonts\arialbd.ttf")],
    }
    hits = 0
    for seed in range(8):
        image, _text, characters = module.rendre(fmt, random.Random(seed), polices, {})
        count = len(segmenter(image))
        assert plausible(count, fmt) or count == len(characters)
        if count == len(characters):
            hits += 1
    assert hits >= 5


def test_preparer_ecrit_un_csv_sans_ecraser(tmp_path):
    spec = importlib.util.spec_from_file_location("annoter", ROOT / "tools" / "annoter_plaques.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["annoter"] = module
    spec.loader.exec_module(module)
    count = module.preparer(3, tmp_path)
    assert count == 3
    first = (tmp_path / "verite.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(first.splitlines()))
    rows[0]["transcription"] = "12ب3"
    with (tmp_path / "verite.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=module.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    assert module.preparer(3, tmp_path) == 3
    again = list(csv.DictReader((tmp_path / "verite.csv").open(encoding="utf-8")))
    assert again[0]["transcription"] == "12ب3"


def test_critere_fixe_dans_le_document():
    text = (ROOT / "docs" / "critere_qualite_plaque.md").read_text(encoding="utf-8")
    assert "96" in text and "24" in text and "50" in text
    assert (LARGEUR_MIN, HAUTEUR_MIN, LAPLACIEN_MIN) == (96, 24, 50.0)
    flou = np.full((40, 120, 3), 180, dtype=np.uint8)
    assert qualite_suffisante(flou, coupee=False) is False
    assert qualite_suffisante(flou, coupee=True) is False
    assert vehicule_de("moped") == "moto"
    assert vehicule_de("IMG") == "voiture"


def test_decodage_ctc_et_intervalle():
    assert reduire_ctc([0, 1, 1, 0, 2], ("a", "b")) == "ab"
    assert taux_erreur("abcd", "abxd") == 0.25
    summary = intervalle_bootstrap([True, False, True, True], [0.0, 0.5, 0.0, 0.0], reprises=200, seed=1)
    assert summary["n"] == 4
    assert summary["exact_bas"] <= summary["exact"] <= summary["exact_haut"]
    model = PetitCRNN(5)
    sortie = model(torch.zeros(2, 1, 32, 128))
    assert sortie.shape == (2, 32, 5)
