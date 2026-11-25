#!/usr/bin/env python3
"""Plaques synthétiques selon configs/plaque_format.yaml. Pas d'entraînement.

    python scripts/04_synth_plates.py --nombre 20000
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from tqdm import tqdm

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.degradations import EFFETS, ajuster_photometrie, redimensionner  # noqa: E402
from src.ocr_plaque import (  # noqa: E402
    caracteres_de,
    charger_format,
    classes_de,
    preparer_caractere,
    texte_de,
    tirer_parties,
)
from src.plaques_reelles import ecrire_planche  # noqa: E402
from src.segmentation import segmenter  # noqa: E402

DEST = PROJECT / "data" / "synthetic" / "plaques"
REPORTS = PROJECT / "reports"
SEED = 42


def _texte(record) -> str:
    try:
        return record.toUnicode()
    except Exception:
        return ""


def decrire_police(path: Path) -> dict:
    font = TTFont(str(path), fontNumber=0)
    cmap: set[int] = set()
    for table in font["cmap"].tables:
        cmap.update(table.cmap)
    name = ""
    license_text = ""
    for record in font["name"].names:
        if record.nameID == 1 and not name:
            name = _texte(record)
        if record.nameID == 13 and not license_text:
            license_text = _texte(record).replace("\r", "\n").strip()
    return {"path": path, "nom": name or path.stem, "licence": license_text, "cmap": cmap}


def chercher_polices(lettres: str) -> dict:
    roots = [Path(r"C:\Windows\Fonts")]
    try:
        import matplotlib

        roots.append(Path(matplotlib.get_data_path()) / "fonts" / "ttf")
    except Exception:
        pass
    files = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in list(root.glob("*.ttf")) + list(root.glob("*.otf")) + list(root.glob("*.TTF")) + list(root.glob("*.OTF")):
            if path.name.lower() in seen:
                continue
            seen.add(path.name.lower())
            files.append(path)
    needed = {ord(char) for char in lettres}
    plate_words = ("plate", "ocr", "fe-font", "mandatory", "uknumber", "din1451", "din_1451")
    plate_hits = [path.name for path in files if any(word in path.name.lower() for word in plate_words)]
    arabes = []
    for path in files:
        try:
            info = decrire_police(path)
        except Exception:
            continue
        if needed and needed <= info["cmap"]:
            arabes.append(info)
    return {"arabes": arabes, "fichiers": len(files), "plaque": plate_hits, "racines": [str(root) for root in roots]}


def ecrire_polices(inventory: dict, lettres: str) -> None:
    lines = [
        "# Polices disponibles pour les plaques synthétiques",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Dossiers parcourus : {', '.join(inventory['racines'])}.",
        f"- Fichiers de police lus : {inventory['fichiers']}.",
        f"- Lettres exigées par `configs/plaque_format.yaml` : {len(lettres)} caractères. Statut : À VALIDER.",
        "",
        "Aucune police dont le nom contient plate, ocr, fe-font, mandatory, uknumber ou din1451 n'a été trouvée."
        if not inventory["plaque"]
        else "Fichiers au nom de police de plaque : " + ", ".join(inventory["plaque"]) + ".",
        "",
        "Le paquet pip `arabic-reshaper` existe : il relie les lettres d'un mot. Ce n'est pas une police. Les lettres sont ici isolées, donc il n'est pas utilisé.",
        "",
        f"Polices qui couvrent les {len(lettres)} lettres proposées : {len(inventory['arabes'])}.",
        "",
        "| Fichier | Nom | Licence (extrait) |",
        "| --- | --- | --- |",
    ]
    for info in sorted(inventory["arabes"], key=lambda item: item["nom"].lower()):
        excerpt = " ".join(info["licence"].split())[:180] if info["licence"] else "non indiquée dans la table name"
        lines.append(f"| `{info['path'].name}` | {info['nom']} | {excerpt} |")
    lines.extend(
        [
            "",
            "## Ce que ces licences permettent ici",
            "",
            "Les polices Microsoft (Arial, Tahoma, Segoe UI, Calibri, Courier New, Dubai, Times New Roman, et les autres dont la table name le dit) sont livrées avec Windows. Le texte de licence autorise à créer, afficher et imprimer un contenu avec la police, dans les conditions du produit Microsoft. Il interdit les autres usages, notamment de redistribuer le fichier de police. Les images synthétiques sont produites sur cette machine. Les fichiers `.ttf` ne sont pas copiés dans le projet.",
            "",
            "DejaVu Sans, livré avec matplotlib, reprend Bitstream Vera et place ses propres changements dans le domaine public. La licence Bitstream Vera permet d'utiliser, copier et redistribuer la police si l'avis de copyright est conservé, et interdit de vendre la police seule. Le fichier de licence est à côté des polices matplotlib (`LICENSE_DEJAVU`). Le projet ne recopie pas ce fichier de police.",
            "",
            "Les chiffres sont dessinés avec une de ces polices grasses quand elle existe : Arial Bold, Tahoma Bold, DejaVu Sans Bold, Calibri Bold, Courier New Bold, Dubai Bold. Ce n'est pas une police de plaque : aucune n'a été trouvée.",
            "",
        ]
    )
    (REPORTS / "polices.md").write_text("\n".join(lines), encoding="utf-8")


def _police(inventory: dict, needles: tuple[str, ...]) -> list[Path]:
    found = []
    for info in inventory["arabes"]:
        if info["path"].name.lower() in needles:
            found.append(info["path"])
    return found


def polices_utiles(inventory: dict) -> dict[str, list[Path]]:
    letters = _police(
        inventory,
        ("tahomabd.ttf", "arialbd.ttf", "dejavusans-bold.ttf", "dubai-bold.ttf", "segoeuib.ttf", "calibrib.ttf"),
    )
    digits = _police(
        inventory,
        ("arialbd.ttf", "tahomabd.ttf", "dejavusans-bold.ttf", "calibrib.ttf", "courbd.ttf", "dubai-bold.ttf"),
    )
    if not letters:
        letters = [info["path"] for info in inventory["arabes"][:4]]
    if not digits:
        digits = list(letters)
    if not letters or not digits:
        raise SystemExit("aucune police ne couvre les lettres du fichier de format")
    return {"lettres": letters, "chiffres": digits}


def _font_encre(path: Path, char: str, target_h: int, cache: dict) -> ImageFont.FreeTypeFont:
    key = ("encre", str(path), char, int(target_h))
    if key in cache:
        return cache[key]
    chosen = _font(path, 48, cache)
    for size in range(48, 120):
        candidate = _font(path, size, cache)
        box = candidate.getbbox(char)
        chosen = candidate
        if box[3] - box[1] >= target_h * 0.9:
            break
    cache[key] = chosen
    return chosen


def _font(path: Path, size: int, cache: dict) -> ImageFont.FreeTypeFont:
    key = (str(path), size)
    if key not in cache:
        cache[key] = ImageFont.truetype(str(path), size)
    return cache[key]


def rendre(
    fmt,
    rng: random.Random,
    polices: dict[str, list[Path]],
    cache: dict,
    mode: str = "ancien",
    profil: dict | None = None,
) -> tuple[np.ndarray, str, str]:
    parties = tirer_parties(fmt, rng)
    characters = caracteres_de(parties, fmt)
    text = texte_de(parties, fmt)
    width, height = 360, 110
    if fmt.fond != "clair":
        raise ValueError("seul un fond clair est décrit dans le fichier de format")
    base = rng.randint(214, 255)
    color = (base, min(255, base + rng.randint(-6, 8)), min(255, base + rng.randint(-8, 4)))
    image = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(image)
    ink = rng.randint(0, 35)
    draw.rectangle((2, 2, width - 3, height - 3), outline=(ink, ink, ink), width=rng.choice((2, 3, 4)))
    size = rng.choice((52, 58, 64))
    font_digit = _font(rng.choice(polices["chiffres"]), size, cache)
    letter_path = rng.choice(polices["lettres"])
    digit_ink = font_digit.getbbox("8")
    target_h = digit_ink[3] - digit_ink[1]
    gap = rng.randint(8, 14)
    widths = []
    fonts = []
    for char in characters:
        if char in fmt.lettres:
            font = _font_encre(letter_path, char, target_h, cache)
        else:
            font = font_digit
        fonts.append(font)
        box = font.getbbox(char)
        widths.append(max(1, box[2] - box[0]))
    total = sum(widths) + gap * (len(characters) - 1)
    x = max(12, (width - total) // 2)
    for char, font, char_w in zip(characters, fonts, widths):
        box = font.getbbox(char)
        y = (height - (box[3] - box[1])) // 2 - box[1]
        draw.text((x - box[0], y), char, font=font, fill=(ink, ink, ink))
        x += char_w + gap
        if fmt.trait_vertical and char in fmt.lettres:
            draw.line((x - gap // 2, 18, x - gap // 2, height - 18), fill=(ink, ink, ink), width=2)
    array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    if mode == "ancien" or profil is None:
        return salir(array, rng), text, characters
    resized = redimensionner(array, int(profil["largeur"]), int(profil["hauteur"]))
    for _name, effect in EFFETS.items():
        if rng.random() < 0.5:
            resized = effect(resized, rng)
    return ajuster_photometrie(resized, float(profil["luminosite"]), float(profil["contraste"])), text, characters


def salir(image: np.ndarray, rng: random.Random) -> np.ndarray:
    height, width = image.shape[:2]
    overlay = image.copy()
    for _ in range(rng.randint(4, 10)):
        center = (rng.randint(0, width), rng.randint(0, height))
        axes = (rng.randint(8, 40), rng.randint(2, 10))
        shade = rng.randint(90, 190)
        cv2.ellipse(overlay, center, axes, rng.randint(0, 180), 0, 360, (shade, shade, shade), -1)
    image = cv2.addWeighted(image, 0.88, overlay, 0.12, 0)
    for _ in range(rng.randint(1, 4)):
        y = rng.randint(0, height - 1)
        cv2.line(image, (0, y), (width - 1, y + rng.randint(-2, 2)), (rng.randint(40, 120),) * 3, 1)
    factor = rng.uniform(0.65, 1.2)
    shift = rng.randint(-25, 25)
    image = np.clip(image.astype(np.float32) * factor + shift, 0, 255).astype(np.uint8)
    sigma = rng.uniform(2, 10)
    noise = np.random.default_rng(rng.randrange(1, 2**31)).normal(0, sigma, image.shape)
    image = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if rng.random() < 0.7:
        kernel = rng.choice((3, 5))
        image = cv2.GaussianBlur(image, (kernel, kernel), 0)
    angle = rng.uniform(-7, 7)
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1)
    image = cv2.warpAffine(image, matrix, (width, height), borderValue=(245, 245, 245))
    src = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    jitter = np.array(
        [[rng.uniform(-0.05, 0.05) * width, rng.uniform(-0.05, 0.05) * height] for _ in range(4)],
        dtype=np.float32,
    )
    dst = src + jitter
    transform = cv2.getPerspectiveTransform(src, dst)
    image = cv2.warpPerspective(image, transform, (width, height), borderValue=(245, 245, 245))
    quality = int(rng.randint(38, 92))
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return image


def uint8_caractere(crop: np.ndarray) -> np.ndarray:
    prepared = preparer_caractere(crop)
    return np.clip(prepared[0] * 255.0, 0, 255).astype(np.uint8)


def generer(nombre: int) -> None:
    fmt = charger_format()
    inventory = chercher_polices(fmt.lettres)
    ecrire_polices(inventory, fmt.lettres)
    polices = polices_utiles(inventory)
    DEST.mkdir(parents=True, exist_ok=True)
    images = DEST / "images"
    images.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    cache: dict = {}
    class_of = {char: index for index, char in enumerate(classes_de(fmt))}
    train_x: list[np.ndarray] = []
    train_y: list[int] = []
    eval_x: list[np.ndarray] = []
    eval_y: list[int] = []
    control = []
    matched = 0
    etiquettes = DEST / "etiquettes.csv"
    with etiquettes.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("image", "transcription", "caracteres", "part", "segments"),
        )
        writer.writeheader()
        for index in tqdm(range(nombre), desc="plaques synthétiques"):
            image, text, characters = rendre(fmt, rng, polices, cache)
            name = f"{index:05d}.jpg"
            cv2.imwrite(str(images / name), image)
            boxes = segmenter(image)
            part = "eval" if index % 10 == 0 else "train"
            if len(boxes) == len(characters):
                matched += 1
                bucket_x = train_x if part == "train" else eval_x
                bucket_y = train_y if part == "train" else eval_y
                for (x, y, w, h), char in zip(boxes, characters):
                    bucket_x.append(uint8_caractere(image[y : y + h, x : x + w]))
                    bucket_y.append(class_of[char])
            if len(control) < 20:
                control.append({"crop": image, "caption": f"posé {text}"})
            writer.writerow(
                {
                    "image": name,
                    "transcription": text,
                    "caracteres": characters,
                    "part": part,
                    "segments": len(boxes),
                }
            )
    if train_x:
        np.savez(DEST / "chars_train.npz", images=np.stack(train_x), labels=np.asarray(train_y, dtype=np.int64))
    if eval_x:
        np.savez(DEST / "chars_eval.npz", images=np.stack(eval_x), labels=np.asarray(eval_y, dtype=np.int64))
    font_caption = str(polices["lettres"][0])
    ecrire_planche(
        control,
        REPORTS / "planche_plaques_synthetiques.jpg",
        "Synthétique. Légende = texte posé par le générateur, format À VALIDER.",
        columns=4,
        font_path=font_caption,
    )
    report = [
        "# Plaques synthétiques",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Nombre : {nombre}. Graine : {SEED}. Dossier : `data/synthetic/plaques/`.",
        "- Le texte de chaque plaque est tiré de `configs/plaque_format.yaml`. Toutes les valeurs y sont À VALIDER.",
        "- Le cyclomoteur est `non_decrit` : aucune plaque de ce type n'est générée.",
        f"- Part tenue à part : un index sur dix (`eval`), le reste `train`.",
        f"- Plaques dont la segmentation retrouve exactement le nombre de caractères posés : {matched}/{nombre} ({100 * matched / max(1, nombre):.1f} %).",
        "- Ces caractères segmentés, et seulement ceux-là, sont dans `chars_train.npz` et `chars_eval.npz`.",
        "- Altérations : fond clair sali, rayures, bruit, flou, luminosité, rotation, perspective, compression JPEG.",
        "- Planche : `reports/planche_plaques_synthetiques.jpg`. Polices : `reports/polices.md`.",
        "",
    ]
    (REPORTS / "synth_plaques.md").write_text("\n".join(report), encoding="utf-8")
    print(f"segmentées {matched}/{nombre}")
    print(DEST)


def _mesures(crop: np.ndarray) -> dict:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    height, width = gray.shape[:2]
    return {
        "largeur": width,
        "hauteur": height,
        "ratio": width / max(1, height),
        "luminosite": float(gray.mean()),
        "contraste": float(gray.std()),
    }


def _resume(rows: list[dict], key: str) -> str:
    values = np.array([row[key] for row in rows], dtype=np.float64)
    if values.size == 0:
        return "—"
    p10, p50, p90 = np.quantile(values, [0.1, 0.5, 0.9])
    return f"{values.mean():.1f} (p10 {p10:.1f}, p50 {p50:.1f}, p90 {p90:.1f})"


def ecrire_realisme(echantillon: int = 1000) -> None:
    from src.plaques_reelles import lister, recadrer

    fmt = charger_format()
    reels = []
    for item in lister():
        crop = recadrer(item)
        if crop is None or crop.size == 0:
            continue
        reels.append(_mesures(crop))
    rng = random.Random(SEED)
    anciens = []
    fichiers = list((DEST / "images").glob("*.jpg"))
    rng.shuffle(fichiers)
    for path in fichiers[:echantillon]:
        image = cv2.imread(str(path))
        if image is not None:
            anciens.append(_mesures(image))
    inventory = chercher_polices(fmt.lettres)
    polices = polices_utiles(inventory)
    cache: dict = {}
    nouveaux = []
    for _ in tqdm(range(echantillon), desc="générateur ajusté"):
        profil = rng.choice(reels)
        image, _text, _characters = rendre(fmt, rng, polices, cache, mode="realiste", profil=profil)
        nouveaux.append(_mesures(image))
    keys = ("ratio", "luminosite", "contraste", "largeur", "hauteur")
    labels = {
        "ratio": "Rapport largeur/hauteur",
        "luminosite": "Luminosité (moyenne des gris)",
        "contraste": "Contraste (écart-type des gris)",
        "largeur": "Largeur (px)",
        "hauteur": "Hauteur (px)",
    }
    lines = [
        "# Réalisme du générateur",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Plaques réelles mesurées dans `data/processed/plates_detection` : {len(reels)}.",
        f"- Ancien générateur, échantillon des images déjà écrites : {len(anciens)}.",
        f"- Générateur ajusté, échantillon non enregistré dans le jeu d'entraînement : {len(nouveaux)}.",
        "- L'inventaire des lettres n'a pas été modifié. Il est lu dans `configs/plaque_format.yaml`.",
        "- Le jeu des 20 000 plaques déjà produit n'est pas régénéré : la CNN de référence a été entraînée dessus.",
        "- Le générateur ajusté tire une plaque réelle au hasard et reprend sa largeur, sa hauteur, sa luminosité et son contraste. Il ajoute ensuite, chacune avec une chance sur deux : flou de mouvement, compression JPEG, réduction puis agrandissement, ombre, perspective, bruit de fond, plaque sale ou rayée.",
        "",
        "| Mesure | Réel | Ancien générateur | Générateur ajusté |",
        "| --- | --- | --- | --- |",
    ]
    for key in keys:
        lines.append(f"| {labels[key]} | {_resume(reels, key)} | {_resume(anciens, key)} | {_resume(nouveaux, key)} |")
    lines.extend(
        [
            "",
            "La moyenne est suivie des 10e, 50e et 90e centiles.",
            "",
            "## Effet de chaque dégradation sur les 150 plaques réelles",
            "",
        ]
    )
    verite = PROJECT / "data" / "test_plaques" / "verite.csv"
    transcrites = 0
    if verite.is_file():
        with verite.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("exclu") == "oui":
                    continue
                if (row.get("transcription") or "").strip():
                    transcrites += 1
    if transcrites == 0:
        lines.append(
            "Aucune transcription réelle n'est saisie. L'effet de chaque dégradation sur les 150 plaques n'est donc pas calculé. "
            "Relancer `python scripts/04_synth_plates.py --realisme` après la saisie : le script appliquera chaque dégradation à part et donnera la plaque entière exacte et le CER, pour la segmentation+CNN et pour le CRNN."
        )
    else:
        lines.extend(_effet_degradations(verite))
    lines.append("")
    (REPORTS / "realisme_plaques.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORTS / "realisme_plaques.md")


def _effet_degradations(verite: Path) -> list[str]:
    from src.crnn import WEIGHTS_PATH as CRNN_WEIGHTS
    from src.crnn import charger as charger_crnn
    from src.crnn import lire as lire_crnn
    from src.ocr_plaque import WEIGHTS_PATH, charger_modele, lire_plaque, normaliser

    fmt = charger_format()
    rows = []
    with verite.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("exclu") == "oui" or not (row.get("transcription") or "").strip():
                continue
            image = cv2.imread(str(verite.parent / "images" / row["fichier"]))
            if image is None:
                continue
            rows.append(row | {"image": image, "reference": normaliser(row["transcription"], fmt)})
    methods = []
    if WEIGHTS_PATH.is_file():
        model, names = charger_modele(WEIGHTS_PATH)
        methods.append(("segmentation + CNN", lambda crop, m=model, n=names: lire_plaque(crop, m, n, fmt)["texte"]))
    if CRNN_WEIGHTS.is_file():
        model, alphabet = charger_crnn(CRNN_WEIGHTS)
        methods.append(("CRNN", lambda crop, m=model, a=alphabet: lire_crnn(m, a, crop)))
    if not methods or not rows:
        return ["Les transcriptions existent, mais un modèle ou une image manque."]
    lines = [
        f"Plaques réelles avec transcription : {len(rows)}. Chaque dégradation est appliquée seule, graine 42. Ce n'est pas un score d'entraînement.",
        "",
        "| Méthode | Dégradation | Plaque entière exacte | CER |",
        "| --- | --- | --- | --- |",
    ]
    for method, reader in methods:
        clean_exact, clean_cer = _score_images(rows, reader, None)
        lines.append(f"| {method} | aucune (image réelle) | {clean_exact} | {clean_cer} |")
        for name, effect in EFFETS.items():
            exact, cer = _score_images(rows, reader, effect)
            lines.append(f"| {method} | {name} | {exact} | {cer} |")
    _ = est_coupee
    return lines


def _score_images(rows: list[dict], reader, effect) -> tuple[str, str]:
    from src.ocr_plaque import normaliser, taux_erreur

    fmt = charger_format()
    exact = 0
    error = 0.0
    for index, row in enumerate(rows):
        image = row["image"]
        if effect is not None:
            image = effect(image, random.Random(SEED + index))
        prediction = normaliser(reader(image), fmt)
        exact += int(prediction == row["reference"])
        error += taux_erreur(row["reference"], prediction)
    count = len(rows)
    return f"{exact}/{count}", f"{100 * error / count:.1f} %"


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère des plaques synthétiques depuis le fichier de format.")
    parser.add_argument("--nombre", type=int, default=None)
    parser.add_argument("--realisme", action="store_true")
    args = parser.parse_args()
    if args.realisme:
        ecrire_realisme()
    if args.nombre:
        generer(args.nombre)


if __name__ == "__main__":
    main()
