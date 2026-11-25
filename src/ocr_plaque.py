"""OCR de plaque. Le motif vient uniquement de configs/plaque_format.yaml."""

from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml
from torch import nn

from src.segmentation import segmenter

PROJECT = Path(__file__).resolve().parents[1]
FORMAT_PATH = PROJECT / "configs" / "plaque_format.yaml"
WEIGHTS_PATH = PROJECT / "data" / "models" / "ocr_chars.pt"
STATUT_ATTENDU = "À VALIDER"
SIZE = 32


def _valeur(node: dict, key: str):
    block = node[key]
    if isinstance(block, dict) and "valeur" in block:
        return block["valeur"]
    raise KeyError(key)


def statuts(node, path: str = "") -> list[tuple[str, str]]:
    found = []
    if isinstance(node, dict):
        if "statut" in node:
            found.append((path or "(racine)", str(node["statut"])))
        for key, value in node.items():
            if key == "statut":
                continue
            child = f"{path}.{key}" if path else str(key)
            found.extend(statuts(value, child))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(statuts(value, f"{path}[{index}]"))
    return found


class FormatPlaque:
    def __init__(self, path: Path, raw: dict) -> None:
        self.path = path
        self.raw = raw
        serie = raw["chiffres_serie"]
        lettre = raw["lettre"]
        prefecture = raw["chiffres_prefecture"]
        self.serie_min = int(_valeur(serie, "min"))
        self.serie_max = int(_valeur(serie, "max"))
        self.chiffres = str(_valeur(serie, "glyphes"))
        self.zeros_a_gauche = bool(_valeur(serie, "zeros_a_gauche"))
        self.nombre_lettres = int(_valeur(lettre, "nombre"))
        self.lettres = str(_valeur(lettre, "ensemble"))
        self.pref_min = int(_valeur(prefecture, "min"))
        self.pref_max = int(_valeur(prefecture, "max"))
        self.chiffres_prefecture = str(_valeur(prefecture, "glyphes"))
        self.liste_fermee = bool(_valeur(prefecture, "liste_fermee"))
        self.ordre = [str(item) for item in _valeur(raw, "ordre_affichage")]
        self.separateurs = [str(item) for item in _valeur(raw, "separateurs")]
        self.sens = str(_valeur(raw, "sens"))
        self.trait_vertical = bool(_valeur(raw, "trait_vertical"))
        self.fond = str(_valeur(raw, "fond"))
        self.cyclomoteur = str(_valeur(raw, "cyclomoteur"))
        if self.serie_min > self.serie_max or self.pref_min > self.pref_max:
            raise ValueError("bornes de chiffres incohérentes")
        if self.nombre_lettres < 1 or not self.lettres or not self.chiffres:
            raise ValueError("alphabet vide")
        allowed = {"chiffres_serie", "lettre", "chiffres_prefecture"}
        if not self.ordre or any(name not in allowed for name in self.ordre):
            raise ValueError("ordre d'affichage inconnu")
        while len(self.separateurs) < max(0, len(self.ordre) - 1):
            self.separateurs.append("")


def charger_format(path: Path | str | None = None) -> FormatPlaque:
    fichier = Path(path) if path else FORMAT_PATH
    raw = yaml.safe_load(fichier.read_text(encoding="utf-8"))
    return FormatPlaque(fichier, raw)


def _bloc(fmt: FormatPlaque, kind: str) -> str:
    if kind == "chiffres_serie":
        return f"[{re.escape(fmt.chiffres)}]{{{fmt.serie_min},{fmt.serie_max}}}"
    if kind == "chiffres_prefecture":
        return f"[{re.escape(fmt.chiffres_prefecture)}]{{{fmt.pref_min},{fmt.pref_max}}}"
    if kind == "lettre":
        return f"[{re.escape(fmt.lettres)}]{{{fmt.nombre_lettres}}}"
    raise KeyError(kind)


def compiler_regex(fmt: FormatPlaque) -> re.Pattern[str]:
    """Motif de la chaîne lue de gauche à droite. Les séparateurs du fichier sont optionnels."""
    order = list(fmt.ordre)
    if fmt.sens == "droite_a_gauche":
        order = list(reversed(order))
    pieces = []
    for index, kind in enumerate(order):
        pieces.append(_bloc(fmt, kind))
        if index < len(order) - 1:
            separator = fmt.separateurs[index] if index < len(fmt.separateurs) else ""
            if separator.strip() == "":
                pieces.append(r"\s*")
            else:
                pieces.append(f"(?:{re.escape(separator)})?")
    return re.compile("^" + "".join(pieces) + "$")


def classes_de(fmt: FormatPlaque) -> tuple[str, ...]:
    seen: list[str] = []
    for character in fmt.chiffres + fmt.chiffres_prefecture + fmt.lettres:
        if character not in seen:
            seen.append(character)
    return tuple(seen)


def bornes_caracteres(fmt: FormatPlaque) -> tuple[int, int]:
    low = high = 0
    for kind in fmt.ordre:
        if kind == "chiffres_serie":
            low += fmt.serie_min
            high += fmt.serie_max
        elif kind == "chiffres_prefecture":
            low += fmt.pref_min
            high += fmt.pref_max
        elif kind == "lettre":
            low += fmt.nombre_lettres
            high += fmt.nombre_lettres
    return low, high


def plausible(count: int, fmt: FormatPlaque) -> bool:
    low, high = bornes_caracteres(fmt)
    return low <= count <= high


def _tirer_chiffres(rng, low: int, high: int, glyphes: str, zeros: bool) -> str:
    length = rng.randint(low, high)
    pool = list(glyphes)
    chars = [rng.choice(pool) for _ in range(length)]
    if not zeros and length > 0 and chars[0] == "0":
        nonzero = [item for item in pool if item != "0"] or pool
        chars[0] = rng.choice(nonzero)
    return "".join(chars)


def tirer_parties(fmt: FormatPlaque, rng) -> dict[str, str]:
    if fmt.liste_fermee:
        raise ValueError("liste fermée de préfectures demandée, mais aucune liste n'est dans le fichier")
    return {
        "chiffres_serie": _tirer_chiffres(rng, fmt.serie_min, fmt.serie_max, fmt.chiffres, fmt.zeros_a_gauche),
        "lettre": "".join(rng.choice(fmt.lettres) for _ in range(fmt.nombre_lettres)),
        "chiffres_prefecture": _tirer_chiffres(
            rng, fmt.pref_min, fmt.pref_max, fmt.chiffres_prefecture, fmt.zeros_a_gauche
        ),
    }


def ordre_visuel(fmt: FormatPlaque) -> list[str]:
    if fmt.sens == "droite_a_gauche":
        return list(reversed(fmt.ordre))
    return list(fmt.ordre)


def caracteres_de(parties: dict[str, str], fmt: FormatPlaque) -> str:
    return "".join(parties[kind] for kind in ordre_visuel(fmt))


def texte_de(parties: dict[str, str], fmt: FormatPlaque) -> str:
    order = ordre_visuel(fmt)
    chunks = []
    for index, kind in enumerate(order):
        chunks.append(parties[kind])
        if index < len(order) - 1:
            chunks.append(fmt.separateurs[index] if index < len(fmt.separateurs) else "")
    return "".join(chunks)


def normaliser(texte: str, fmt: FormatPlaque) -> str:
    cleaned = texte or ""
    for separator in fmt.separateurs:
        if separator:
            cleaned = cleaned.replace(separator, "")
    return "".join(cleaned.split())


def distance_edition(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for index, char_left in enumerate(left, start=1):
        current = [index]
        for column, char_right in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (char_left != char_right),
                )
            )
        previous = current
    return previous[-1]


def taux_erreur(reference: str, prediction: str) -> float:
    if not reference:
        return 0.0 if not prediction else 1.0
    return distance_edition(reference, prediction) / len(reference)


def intervalle_bootstrap(exacts: list[bool], erreurs: list[float], reprises: int = 1000, seed: int = 42) -> dict:
    exact = np.asarray(list(exacts), dtype=np.float64)
    cer = np.asarray(list(erreurs), dtype=np.float64)
    count = int(exact.shape[0])
    if count == 0:
        return {"n": 0, "exact": 0.0, "exact_bas": 0.0, "exact_haut": 0.0, "cer": 0.0, "cer_bas": 0.0, "cer_haut": 0.0}
    rng = np.random.default_rng(seed)
    means_exact = np.empty(reprises)
    means_cer = np.empty(reprises)
    for index in range(reprises):
        drawn = rng.integers(0, count, count)
        means_exact[index] = exact[drawn].mean()
        means_cer[index] = cer[drawn].mean()
    return {
        "n": count,
        "exact": float(exact.mean()),
        "exact_bas": float(np.quantile(means_exact, 0.025)),
        "exact_haut": float(np.quantile(means_exact, 0.975)),
        "cer": float(cer.mean()),
        "cer_bas": float(np.quantile(means_cer, 0.025)),
        "cer_haut": float(np.quantile(means_cer, 0.975)),
    }


def scores(reference: str, prediction: str) -> dict:
    distance = distance_edition(reference, prediction)
    if not reference and not prediction:
        ratio = 1.0
    elif not reference:
        ratio = 0.0
    else:
        ratio = max(0.0, len(reference) - distance) / len(reference)
    return {"exact": reference == prediction, "distance": distance, "caracteres": ratio}


class PetitCaractere(nn.Module):
    def __init__(self, n_classes: int) -> None:
        super().__init__()
        self.couches = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(4),
        )
        self.sortie = nn.Linear(64 * 4 * 4, n_classes)

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return self.sortie(self.couches(batch).flatten(1))


def preparer_caractere(crop: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    height, width = gray.shape[:2]
    side = max(height, width, 1)
    canvas = np.full((side, side), 255, dtype=np.uint8)
    y = (side - height) // 2
    x = (side - width) // 2
    canvas[y : y + height, x : x + width] = gray
    resized = cv2.resize(canvas, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    return (resized.astype(np.float32) / 255.0)[None, :, :]


def charger_modele(path: Path | str | None = None) -> tuple[PetitCaractere, tuple[str, ...]]:
    weights = Path(path) if path else WEIGHTS_PATH
    if not weights.is_file():
        raise FileNotFoundError(f"poids des caractères introuvables : {weights}")
    blob = torch.load(weights, map_location="cpu", weights_only=False)
    names = tuple(blob["noms"])
    model = PetitCaractere(len(names))
    model.load_state_dict(blob["state"])
    model.eval()
    return model, names


def predire_caractere(model: PetitCaractere, names: tuple[str, ...], crop: np.ndarray) -> tuple[str, float]:
    if crop is None or crop.size == 0:
        return "", 0.0
    batch = torch.from_numpy(np.ascontiguousarray(preparer_caractere(crop))).unsqueeze(0)
    with torch.no_grad():
        scores_tensor = torch.softmax(model(batch), dim=1)[0]
    index = int(scores_tensor.argmax())
    return names[index], float(scores_tensor[index])


def lire_plaque(image: np.ndarray, model: PetitCaractere, names: tuple[str, ...], fmt: FormatPlaque) -> dict:
    boxes = segmenter(image)
    characters = []
    confidences = []
    for x, y, width, height in boxes:
        crop = image[y : y + height, x : x + width]
        character, confidence = predire_caractere(model, names, crop)
        if character:
            characters.append(character)
            confidences.append(confidence)
    text = "".join(characters)
    motif = compiler_regex(fmt)
    return {
        "texte": text,
        "conforme": bool(motif.fullmatch(text)),
        "confiance": float(sum(confidences) / len(confidences)) if confidences else 0.0,
        "boites": len(boxes),
    }
