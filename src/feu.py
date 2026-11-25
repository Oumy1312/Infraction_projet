"""Couleur d'un feu par HSV, puis lissage sur plusieurs images.

Les seuils viennent de config.yaml. Un état « inconnu » ne devient jamais rouge.
Une infraction n'est retenue que si le rouge lissé tient sur M images d'affilée
avant le franchissement.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import yaml

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT / "config.yaml"
COLORS = ("rouge", "orange", "vert")


def load_config(path: Path | str | None = None) -> dict:
    config_path = Path(path) if path else DEFAULT_CONFIG
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "feu" not in payload:
        raise ValueError(f"config.yaml sans bloc feu : {config_path}")
    return payload["feu"]


def _mask(hsv: np.ndarray, spec: dict) -> np.ndarray:
    selected = np.zeros(hsv.shape[:2], dtype=bool)
    for low, high in spec["hue"]:
        band = cv2.inRange(
            hsv,
            (int(low), int(spec["sat_min"]), int(spec["val_min"])),
            (int(high), 255, 255),
        )
        selected |= band > 0
    return selected


def classify_bgr(image: np.ndarray, config: dict | None = None) -> str:
    """Retourne rouge, orange, vert, douteux ou inconnu pour une image BGR.

    Sans bloc « douteux », le comportement reste celui des trois couleurs.
    Si la bande douteuse est à égalité avec le rouge, le résultat n'est pas rouge.
    """
    if image.size == 0:
        return "inconnu"
    rules = config if config is not None else load_config()
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    total = hsv.shape[0] * hsv.shape[1]
    if total == 0:
        return "inconnu"
    names = [name for name in (*COLORS, "douteux") if name in rules]
    scores = {name: int(_mask(hsv, rules[name]).sum()) for name in names}
    best = max(scores, key=scores.get)
    if "douteux" in scores:
        top = max(scores.values())
        leaders = [name for name, score in scores.items() if score == top]
        if "rouge" in leaders and len(leaders) > 1:
            leaders.remove("rouge")
        for name in ("douteux", "orange", "vert", "rouge"):
            if name in leaders:
                best = name
                break
    if scores[best] / total < float(rules["min_ratio"]):
        return "inconnu"
    return best


def classify_box(frame_bgr: np.ndarray, box: tuple[int, int, int, int], config: dict | None = None) -> str:
    """box est x1, y1, x2, y2 en pixels."""
    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(width, int(x1)))
    x2 = max(0, min(width, int(x2)))
    y1 = max(0, min(height, int(y1)))
    y2 = max(0, min(height, int(y2)))
    if x2 <= x1 or y2 <= y1:
        return "inconnu"
    return classify_bgr(frame_bgr[y1:y2, x1:x2], config)


def vote_majoritaire(couleurs: list[str]) -> str:
    """Couleur la plus fréquente. Rouge ne gagne qu'en tête seule.

    Un « inconnu » ne compte jamais comme rouge : en cas d'égalité avec
    le rouge, une autre couleur l'emporte.
    """
    if not couleurs:
        return "inconnu"
    counts = Counter(couleurs)
    best = max(counts.values())
    leaders = [name for name, count in counts.items() if count == best]
    if leaders == ["rouge"]:
        return "rouge"
    for name in ("douteux", "orange", "vert", "inconnu"):
        if name in leaders and name != "rouge":
            return name
    return next(name for name in leaders if name != "rouge")


def rouge_confirme_avant(etats: list[str], index: int, m: int) -> bool:
    """Vrai si les M états juste avant index sont rouges. L'image index est le franchissement."""
    if m <= 0:
        return True
    debut = index - m
    if debut < 0 or index > len(etats):
        return False
    return all(etats[i] == "rouge" for i in range(debut, index))


DEFAULT_N_S = 5 / 30
DEFAULT_M_S = 3 / 30


def images_pour(secondes: float, fps: float) -> int:
    """Convertit une durée en nombre d'images à la cadence réellement traitée."""
    if fps <= 0:
        raise ValueError("la cadence doit être positive")
    return max(1, int(round(float(secondes) * float(fps))))


def backend_depuis(feu_config: dict) -> str:
    """hsv par défaut, comme le config.yaml du projet qui ne nomme pas de backend."""
    name = str(feu_config.get("backend", "hsv")).lower()
    if name not in {"hsv", "cnn", "fusion"}:
        raise ValueError(f"backend inconnu : {name}")
    return name


def fusionner(hsv_label: str, cnn_label: str) -> str:
    """Règle fixée à l'avance. Un douteux n'est jamais un rouge."""
    if hsv_label == "rouge" and cnn_label == "rouge":
        return "rouge"
    if hsv_label == "vert" and cnn_label == "vert":
        return "vert"
    if "orange" in (hsv_label, cnn_label) and hsv_label != "rouge" and cnn_label != "rouge":
        return "orange"
    return "douteux"


class LisseurFeu:
    """Vote sur les N dernières couleurs. N et M peuvent venir d'une durée en secondes."""

    def __init__(self, n: int = 5, m: int = 3) -> None:
        if n < 1 or m < 1:
            raise ValueError("N et M doivent être au moins 1")
        self.n = n
        self.m = m
        self._fenetre: list[str] = []
        self.etats: list[str] = []

    @classmethod
    def depuis_secondes(cls, n_s: float, m_s: float, fps: float) -> "LisseurFeu":
        return cls(n=images_pour(n_s, fps), m=images_pour(m_s, fps))

    def ajouter(self, couleur: str) -> str:
        self._fenetre.append(couleur)
        if len(self._fenetre) > self.n:
            self._fenetre.pop(0)
        etat = vote_majoritaire(self._fenetre)
        self.etats.append(etat)
        return etat

    def infraction_retenue(self, index: int) -> bool:
        return rouge_confirme_avant(self.etats, index, self.m)
