from pathlib import Path

import cv2
import numpy as np
import pytest

from src.acquisition import frames
from src.feu import (
    LisseurFeu,
    backend_depuis,
    classify_bgr,
    classify_box,
    fusionner,
    load_config,
    vote_majoritaire,
)


def test_solid_colors_match_the_config_thresholds():
    config = load_config()
    red = np.zeros((40, 40, 3), dtype=np.uint8)
    red[:, :] = (0, 0, 220)
    orange = np.zeros((40, 40, 3), dtype=np.uint8)
    orange[:, :] = (0, 140, 255)
    green = np.zeros((40, 40, 3), dtype=np.uint8)
    green[:, :] = (0, 200, 0)
    gray = np.zeros((40, 40, 3), dtype=np.uint8)
    gray[:, :] = (40, 40, 40)
    assert classify_bgr(red, config) == "rouge"
    assert classify_bgr(orange, config) == "orange"
    assert classify_bgr(green, config) == "vert"
    assert classify_bgr(gray, config) == "inconnu"


def test_box_outside_the_frame_is_unknown():
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    assert classify_box(frame, (30, 30, 40, 40), load_config()) == "inconnu"


def _etats(couleurs: list[str], n: int = 5) -> list[str]:
    lisseur = LisseurFeu(n=n, m=3)
    return [lisseur.ajouter(couleur) for couleur in couleurs]


def test_rouge_stable_confirme_apres_m_images():
    lisseur = LisseurFeu(n=5, m=3)
    etats = [lisseur.ajouter("rouge") for _ in range(6)]
    assert etats == ["rouge"] * 6
    assert lisseur.infraction_retenue(2) is False
    assert lisseur.infraction_retenue(3) is True


def test_orange_ne_devient_pas_rouge():
    etats = _etats(["orange"] * 8)
    assert etats == ["orange"] * 8
    assert LisseurFeu(n=5, m=3).infraction_retenue(0) is False
    lisseur = LisseurFeu(n=5, m=3)
    for couleur in ["orange"] * 8:
        lisseur.ajouter(couleur)
    assert all(not lisseur.infraction_retenue(index) for index in range(8))


def test_clignotement_ne_confirme_pas_le_rouge():
    lisseur = LisseurFeu(n=5, m=3)
    for couleur in ("rouge", "vert") * 4:
        lisseur.ajouter(couleur)
    assert all(not lisseur.infraction_retenue(index) for index in range(8))


def test_inconnu_ne_compte_pas_comme_rouge():
    bruit = ["inconnu", "inconnu", "rouge", "inconnu", "inconnu", "rouge", "inconnu"]
    etats = _etats(bruit)
    assert "rouge" not in etats
    assert vote_majoritaire(["rouge", "inconnu"]) == "inconnu"
    lisseur = LisseurFeu(n=5, m=3)
    for couleur in bruit:
        lisseur.ajouter(couleur)
    assert all(not lisseur.infraction_retenue(index) for index in range(len(bruit)))


def test_vote_n_est_reglable():
    assert _etats(["vert", "vert", "rouge"], n=1) == ["vert", "vert", "rouge"]
    assert _etats(["vert", "vert", "rouge"], n=3)[-1] == "vert"


def test_secondes_a_5_et_30_images_par_seconde():
    lent = LisseurFeu.depuis_secondes(1.0, 0.6, fps=5)
    rapide = LisseurFeu.depuis_secondes(1.0, 0.6, fps=30)
    assert (lent.n, lent.m) == (5, 3)
    assert (rapide.n, rapide.m) == (30, 18)
    court = LisseurFeu.depuis_secondes(1.0, 0.4, fps=5)
    for _ in range(3):
        court.ajouter("rouge")
    assert court.infraction_retenue(2) is True
    meme_duree = LisseurFeu.depuis_secondes(1.0, 0.4, fps=30)
    for _ in range(3):
        meme_duree.ajouter("rouge")
    assert meme_duree.m == 12
    assert meme_duree.infraction_retenue(2) is False


def test_fusion_et_douteux_ne_sont_pas_rouge():
    assert fusionner("rouge", "rouge") == "rouge"
    assert fusionner("vert", "vert") == "vert"
    assert fusionner("orange", "vert") == "orange"
    assert fusionner("rouge", "orange") == "douteux"
    assert fusionner("douteux", "rouge") == "douteux"
    assert backend_depuis(load_config()) == "hsv"
    lisseur = LisseurFeu(n=5, m=3)
    for _ in range(5):
        assert lisseur.ajouter("douteux") == "douteux"
    assert all(not lisseur.infraction_retenue(index) for index in range(5))


def test_video_roundtrip(tmp_path: Path):
    path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (32, 24))
    if not writer.isOpened():
        pytest.skip("encodeur vidéo indisponible")
    for index in range(3):
        image = np.zeros((24, 32, 3), dtype=np.uint8)
        image[:, :] = (0, 0, 40 * (index + 1))
        writer.write(image)
    writer.release()
    read = list(frames(path))
    assert [frame.index for frame in read] == [0, 1, 2]
    assert read[1].time_s == pytest.approx(0.2)
