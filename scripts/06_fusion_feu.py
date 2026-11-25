#!/usr/bin/env python3
"""Justifie la bande douteuse sur l'ajustement, puis évalue une fois la fusion.

La règle de fusion et la bande 11-21 sont lues, pas ajustées.
Les 440 boîtes tenues à part ne servent qu'à la mesure finale.

    python scripts/06_fusion_feu.py
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.stats import binomtest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from src.feu import _mask, fusionner, load_config
from src.feu_cnn import charger, predire

REPORTS = PROJECT / "reports"
LABELS = ("rouge", "orange", "vert")
PREDICTED = ("rouge", "orange", "vert", "douteux", "inconnu", "autre")


def load_hsv_module():
    spec = importlib.util.spec_from_file_location("eval_hsv_fusion", PROJECT / "scripts" / "06_eval_hsv.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_hsv_fusion"] = module
    spec.loader.exec_module(module)
    return module


def diagnose(crop, config: dict) -> str:
    if crop is None or crop.size == 0:
        return "inconnu"
    image = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    total = image.shape[0] * image.shape[1]
    if total == 0:
        return "inconnu"
    names = [name for name in ("rouge", "orange", "vert", "douteux") if name in config]
    scores = {name: int(_mask(image, config[name]).sum()) for name in names}
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
    rejected = scores[best] / total < float(config["min_ratio"])
    return "inconnu" if rejected else best


def rejected_by_ratio(crop, config: dict) -> bool:
    if crop is None or crop.size == 0:
        return False
    image = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    total = image.shape[0] * image.shape[1]
    if total == 0:
        return False
    names = [name for name in ("rouge", "orange", "vert") if name in config]
    scores = {name: int(_mask(image, config[name]).sum()) for name in names}
    best = max(scores, key=scores.get)
    return scores[best] / total < float(config["min_ratio"])


def trop_petite(row: dict) -> bool:
    x1, y1, x2, y2 = row["box"]
    side = min(max(0, x2 - x1), max(0, y2 - y1))
    return side < 8 or row["area"] < 0.0004


def median_hue(crop) -> float | None:
    if crop is None or crop.size == 0:
        return None
    image = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    keep = (image[:, :, 1] >= 60) & (image[:, :, 2] >= 80)
    hues = image[:, :, 0][keep]
    if hues.size == 0:
        return None
    return float(np.median(hues))


def band_of(hue: float) -> str:
    if hue <= 10 or hue >= 160:
        return "0-10 ou 160-179"
    if 11 <= hue <= 21:
        return "11-21"
    if 22 <= hue <= 32:
        return "22-32"
    if 40 <= hue <= 95:
        return "40-95"
    return "ailleurs"


def cause_rouge_vert(crop, row: dict) -> tuple[str, str]:
    x1, y1, x2, y2 = row["box"]
    width = max(0, x2 - x1)
    height = max(0, y2 - y1)
    size = f"{width}×{height} px"
    hue = median_hue(crop)
    hue_text = "sans teinte saturée" if hue is None else f"teinte médiane {hue:.0f}"
    if crop is None or crop.size == 0:
        return f"{hue_text}, {size}", "recadrage vide"
    image = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    sat = image[:, :, 1] >= 60
    val = image[:, :, 2] >= 80
    green = ((image[:, :, 0] >= 40) & (image[:, :, 0] <= 95) & sat & val).mean()
    red = (((image[:, :, 0] <= 10) | (image[:, :, 0] >= 160)) & sat & val).mean()
    notes = []
    if trop_petite(row):
        notes.append("boîte trop petite")
    if green > 0.05 and red > 0.05:
        notes.append("la boîte couvre du vert et du rouge")
    elif hue is not None and 40 <= hue <= 95:
        notes.append("teinte médiane dans le vert")
    elif hue is None:
        notes.append("peu de pixels saturés, le masque vert gagne sur du bruit")
    else:
        notes.append("le masque vert dépasse le masque rouge")
    return f"{hue_text}, {size}", ", ".join(notes)


def scores(rows: list[dict], key: str, label: str) -> tuple[float, float, int, int, int]:
    tp = sum(row["true"] == label and row[key] == label for row in rows)
    fp = sum(row["true"] != label and row[key] == label for row in rows)
    fn = sum(row["true"] == label and row[key] != label for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return precision, recall, tp, fp, fn


def accuracy(rows: list[dict], key: str) -> tuple[float, int]:
    hits = sum(row["true"] == row[key] for row in rows)
    return (hits / len(rows) if rows else 0.0), hits


def matrix(rows: list[dict], key: str) -> dict[str, Counter]:
    table = {true: Counter() for true in LABELS}
    for row in rows:
        table[row["true"]][row[key]] += 1
    return table


def dangerous(table: dict[str, Counter]) -> tuple[int, int]:
    count = table["orange"]["rouge"] + table["vert"]["rouge"]
    base = sum(table["orange"].values()) + sum(table["vert"].values())
    return count, base


def mcnemar(left: list[bool], right: list[bool]) -> tuple[int, int, float]:
    only_right = sum((not a) and b for a, b in zip(left, right))
    only_left = sum(a and (not b) for a, b in zip(left, right))
    discordant = only_right + only_left
    if discordant == 0:
        return only_left, only_right, 1.0
    return only_left, only_right, float(binomtest(only_right, discordant, 0.5).pvalue)


def table_md(table: dict[str, Counter]) -> list[str]:
    columns = PREDICTED
    lines = [
        "| Vrai \\ prédit | " + " | ".join(columns) + " |",
        "| --- | " + " | ".join("---" for _ in columns) + " |",
    ]
    for true in LABELS:
        lines.append("| " + true + " | " + " | ".join(str(table[true][name]) for name in columns) + " |")
    return lines


def class_lines(rows: list[dict], key: str) -> list[str]:
    lines = ["| Couleur | Précision | Rappel |", "| --- | --- | --- |"]
    for label in LABELS:
        precision, recall, _tp, _fp, _fn = scores(rows, key, label)
        lines.append(f"| {label} | {precision:.1%} | {recall:.1%} |")
    return lines


def draw_sheet(cases: list[dict], destination: Path) -> None:
    columns = 4
    thumb = 200
    pad = 8
    caption = 78
    rows = max(1, (len(cases) + columns - 1) // columns)
    sheet = Image.new("RGB", (pad + columns * (thumb + pad), 36 + rows * (thumb + caption)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    draw.text((pad, 8), "Rouges lus verts par HSV v2. Teinte médiane, taille, cause.", fill=(240, 240, 240), font=font)
    for index, item in enumerate(cases):
        crop = item["crop"]
        column = index % columns
        row = index // columns
        origin_x = pad + column * (thumb + pad)
        origin_y = 32 + row * (thumb + caption)
        canvas = Image.new("RGB", (thumb, thumb), (32, 32, 32))
        if crop is not None and crop.size:
            picture = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            picture.thumbnail((thumb - 8, thumb - 8))
            canvas.paste(picture, ((thumb - picture.width) // 2, (thumb - picture.height) // 2))
        sheet.paste(canvas, (origin_x, origin_y))
        lines = textwrap.wrap(f"{item['hue_text']}. {item['cause']}", width=32)[:4]
        for line_index, line in enumerate(lines):
            draw.text((origin_x, origin_y + thumb + 2 + line_index * 14), line, fill=(230, 230, 230), font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)


def distribution(rows: list[dict]) -> Counter:
    counts = Counter()
    for row in rows:
        hue = median_hue(row["crop"])
        if hue is None:
            counts["sans teinte saturée"] += 1
        else:
            counts[band_of(hue)] += 1
    return counts


def pct(value: float) -> str:
    return f"{value:.1%}"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    base = load_hsv_module()
    v2 = load_config(PROJECT / "configs" / "hsv_v2.yaml")
    v3 = load_config(PROJECT / "configs" / "hsv_v3.yaml")
    boxes = base.collect()
    images = sorted({item["image"] for item in boxes}, key=lambda path: str(path))
    assignment, _sizes = base.assign_images(images)
    evaluation = []
    adjustment = []
    for item in boxes:
        crop = base.crop_bgr(item)
        packed = {**item, "crop": crop, "split": assignment[item["image"]]}
        if packed["split"] == "evaluation":
            evaluation.append(packed)
        else:
            adjustment.append(packed)
    assert len(evaluation) == 440

    red_adjust = [row for row in adjustment if row["true"] == "rouge"]
    orange_adjust = [row for row in adjustment if row["true"] == "orange"]
    red_bands = distribution(red_adjust)
    orange_bands = distribution(orange_adjust)

    model = charger()
    red_green = []
    for row in evaluation:
        row["v2"] = diagnose(row["crop"], v2)
        row["ratio"] = rejected_by_ratio(row["crop"], v2)
        row["v3"] = diagnose(row["crop"], v3)
        row["cnn"], _score = predire(model, row["crop"])
        row["fusion"] = fusionner(row["v3"], row["cnn"])
        if row["true"] == "rouge" and row["v2"] == "vert":
            hue_text, why = cause_rouge_vert(row["crop"], row)
            red_green.append({**row, "hue_text": hue_text, "cause": why})
    draw_sheet(red_green, REPORTS / "contact_rouge_vert.jpg")

    kept = [row for row in evaluation if not trop_petite(row)]
    passed_ratio = [row for row in evaluation if not row["ratio"]]
    acc_all, hits_all = accuracy(evaluation, "v2")
    acc_kept, hits_kept = accuracy(kept, "v2")
    acc_ratio, hits_ratio = accuracy(passed_ratio, "v2")
    red_v2 = scores(evaluation, "v2", "rouge")
    red_cnn = scores(evaluation, "cnn", "rouge")

    clarifications = [
        "",
        "## Clarifications",
        "",
        "Le 98,0 % (193/197) est le filtre de taille, pas `min_ratio`.",
        "Une boîte est écartée par ce filtre si son petit côté fait moins de 8 px, ou si son aire fait moins de 0,0004 de l'image.",
        f"Sur 440 boîtes, ce filtre en écarte {440 - len(kept)}. Il en reste {len(kept)}.",
        f"`min_ratio` n'écarte que {sum(row['ratio'] for row in evaluation)} boîtes : le meilleur masque coloré n'atteint pas 3 % des pixels. Ce n'est pas le même filtre, et la précision qui en résulte n'est pas 98 %.",
        "",
        "| Filtre | Boîtes restantes | Précision HSV v2 |",
        "| --- | --- | --- |",
        f"| aucun | {len(evaluation)} | {pct(acc_all)} ({hits_all}/{len(evaluation)}) |",
        f"| min_ratio (boîtes non écartées) | {len(passed_ratio)} | {pct(acc_ratio)} ({hits_ratio}/{len(passed_ratio)}) |",
        f"| taille (côté ≥ 8 px et aire ≥ 0,0004) | {len(kept)} | {pct(acc_kept)} ({hits_kept}/{len(kept)}) |",
        "",
        "Précision et rappel du rouge, sur les 440 boîtes :",
        "",
        "| Méthode | Précision rouge | Rappel rouge |",
        "| --- | --- | --- |",
        f"| HSV v2 | {red_v2[0]:.1%} ({red_v2[2]}/{red_v2[2] + red_v2[3]}) | {red_v2[1]:.1%} ({red_v2[2]}/{red_v2[2] + red_v2[4]}) |",
        f"| CNN | {red_cnn[0]:.1%} ({red_cnn[2]}/{red_cnn[2] + red_cnn[3]}) | {red_cnn[1]:.1%} ({red_cnn[2]}/{red_cnn[2] + red_cnn[4]}) |",
        "",
        f"Les {len(red_green)} rouges lus verts par HSV v2 sont dans `reports/contact_rouge_vert.jpg`, avec la teinte médiane des pixels saturés, la taille de la boîte et la cause probable.",
        "",
    ]
    report_v2 = REPORTS / "hsv_eval_v2.md"
    previous = report_v2.read_text(encoding="utf-8")
    marker = "\n## Clarifications\n"
    if marker in previous:
        previous = previous.split(marker)[0].rstrip() + "\n"
    report_v2.write_text(previous.rstrip() + "\n" + "\n".join(clarifications), encoding="utf-8", newline="\n")

    def block(name: str, key: str) -> list[str]:
        table = matrix(evaluation, key)
        acc, hits = accuracy(evaluation, key)
        danger, base = dangerous(table)
        rate = danger / base if base else 0.0
        return [
            f"### {name}",
            "",
            f"- Précision globale : {pct(acc)} ({hits}/{len(evaluation)}).",
            f"- Orange ou vert lus rouge : {danger} / {base} ({pct(rate)}).",
            "",
            *class_lines(evaluation, key),
            "",
            *table_md(table),
            "",
        ]

    correct = {
        key: [row["true"] == row[key] for row in evaluation]
        for key in ("v3", "cnn", "fusion")
    }
    pairs = (
        ("HSV v3", "CNN", "v3", "cnn"),
        ("HSV v3", "fusion", "v3", "fusion"),
        ("CNN", "fusion", "cnn", "fusion"),
    )
    mcnemar_lines = [
        "| Comparaison | Seulement A juste | Seulement B juste | p (McNemar exact) |",
        "| --- | --- | --- | --- |",
    ]
    for left_name, right_name, left_key, right_key in pairs:
        only_left, only_right, pvalue = mcnemar(correct[left_key], correct[right_key])
        p_text = "< 0,0001" if pvalue < 0.0001 else f"{pvalue:.4f}".replace(".", ",")
        mcnemar_lines.append(
            f"| {left_name} contre {right_name} | {only_left} | {only_right} | {p_text} |"
        )

    def band_lines(title: str, counts: Counter, total: int) -> list[str]:
        lines = [f"- {title} : {total} boîtes."]
        for name, count in counts.most_common():
            lines.append(f"  - {name} : {count} ({pct(count / total if total else 0)}).")
        return lines

    lines = [
        "# Fusion HSV v3 et CNN",
        "",
        f"- Généré : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Bande et règle fixées avant cette mesure. Une seule passe sur les 440 boîtes tenues à part. `config.yaml` n'a pas été modifié.",
        "",
        "## Pourquoi les teintes 11 à 21",
        "",
        "Chiffres calculés seulement sur l'ajustement (70 %), pas sur les 440.",
        "La teinte médiane est celle des pixels de saturation ≥ 60 et de valeur ≥ 80.",
        "",
        *band_lines("Rouges d'ajustement", red_bands, len(red_adjust)),
        *band_lines("Oranges d'ajustement", orange_bands, len(orange_adjust)),
        "",
        (
            f"Sur l'ajustement, {red_bands['11-21']} rouges sur {len(red_adjust)} "
            "ont leur teinte médiane dans 11-21, et "
            f"{red_bands['0-10 ou 160-179']} dans 0-10 ou 160-179. "
            f"Les oranges tombent surtout dans 22-32 ({orange_bands['22-32']} sur {len(orange_adjust)}) : "
            f"{orange_bands['11-21']} ont leur médiane dans 11-21. "
            "La bande n'est pas un trou vide. C'est la zone mesurée de beaucoup de feux annotés rouges, "
            "juste avant celle des oranges. La classer « douteux » évite de l'appeler rouge, "
            "et fait baisser le rappel du rouge. Elle n'a pas été déplacée après la mesure sur les 440."
        ),
        "",
        "## Règle de fusion",
        "",
        "- rouge si HSV v3 et la CNN disent tous les deux rouge ;",
        "- vert si les deux disent vert ;",
        "- orange si au moins un des deux dit orange et qu'aucun ne dit rouge ;",
        "- sinon douteux.",
        "- Un douteux ne déclenche pas d'infraction.",
        "",
        "## Évaluation",
        "",
        *block("HSV v3", "v3"),
        *block("CNN", "cnn"),
        *block("Fusion", "fusion"),
        "## McNemar apparié",
        "",
        "Chaque boîte est une paire : juste ou faux pour les deux méthodes. Le test exact est binomial sur les paires discordantes.",
        "",
        *mcnemar_lines,
        "",
    ]
    destination = REPORTS / "fusion_feu.md"
    destination.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(destination)
    print(f"rouges lus verts {len(red_green)}")
    for key in ("v3", "cnn", "fusion"):
        acc, hits = accuracy(evaluation, key)
        print(key, f"{acc:.1%}", hits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
