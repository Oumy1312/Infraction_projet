# Détection d'infraction au feu rouge

Les modèles sont entraînés de zéro. Aucun poids pré-entraîné n'est utilisé.
Le dossier source `Infraction`, à côté de ce projet, n'est jamais modifié.
`quarantine/` n'est pas relu ni complété.

## Installation

Python 3.10 ou plus.

```bash
python -m pip install -r requirements.txt
```

## Données

Les scripts s'enchaînent dans cet ordre. Sans `--apply`, la copie reste une simulation.

```bash
python scripts/00_analyze_mess.py
python scripts/01_reorganize.py
python scripts/02_affiner_a_trier.py
python scripts/03_copier_tri.py
python scripts/03_copier_tri.py --apply
python scripts/03_polygones.py
python scripts/03_validate.py
python scripts/03_classes.py
python scripts/03_decouper.py
python scripts/04_controles_pre_train.py
python scripts/05_vehicules_revise.py
python scripts/05_classes_couleur.py
python scripts/05_package_kaggle.py
python scripts/06_eval_hsv.py
```

Règle de tri validée : un préfixe de 6 chiffres désigne un feu, tout autre préfixe une plaque. Le rapport largeur/hauteur 0,70 sert de contrôle. Si les deux divergent, le fichier va dans `data/raw/_incertains`. Les fichiers mixtes sont séparés ligne par ligne.

| Dossier | Rôle |
| --- | --- |
| `data/raw/` | Copies fidèles, polygones encore présents |
| `data/interim/` | Labels convertis en rectangles |
| `data/interim/feux_couleur/` | Labels d'origine des feux (13 classes S2TLD), pour le contrôle HSV |
| `data/processed/` | train / val / test, graine 42 |
| `data/test_scenes/` | Images et labels YOLO des vidéos de Marrakech. Vide pour l'instant. Le notebook Kaggle évalue ce dossier s'il contient des images |
| `data/raw/vehicles_exclus/` | threewheel, mis à part. Les vans seuls sont revenus dans le jeu comme `car` |

Véhicules et plaques restent proches de 70 / 20 / 10. Les feux ne le sont pas : un seul groupe de quasi-doublons pHash contient 3 885 images, donc train est à 79,6 %. Le détail est dans `reports/fuites.md`.

Chaque jeu traité a un `data.yaml` à chemins relatifs :

- `data/processed/vehicles/data.yaml` : car, bus, truck, motorcycle
- `data/processed/traffic_lights/data.yaml` : traffic_light
- `data/processed/plates_detection/data.yaml` : plate

Les rapports sont dans `reports/`.

## Entraînement

Pas lancé en local : cette machine n'a pas de GPU CUDA (`torch 2.11.0+cpu`).

Sur Kaggle :

1. `notebooks/kaggle_01_coco.ipynb` télécharge COCO (véhicules, feux positifs, négatifs).
2. `python scripts/05_package_kaggle.py` prépare le zip de `data/processed`.
3. `notebooks/kaggle_02_train.ipynb` entraîne une tâche à la fois (`TASK` = `vehicles`, `traffic_lights` ou `plates_detection`), de zéro (`yolo11n.yaml`, `pretrained=False`). `SMOKE = True` prend 200 images et 3 époques, affiche le temps par époque et l'estimation pour 250. `RESUME = True` reprend `last.pt` importé depuis un dataset précédent. `save_period=10`. Avant l'entraînement, le notebook s'arrête si un `.pt` inattendu existe ou si le journal signale un téléchargement. Les métriques de validation sont séparées entre nos images et COCO.

`reports/hsv_eval.md` note la couleur HSV sur un tiers des feux rouge, jaune et vert, les groupes pHash restant ensemble. Les seuils de `config.yaml` ne sont pas changés par ce script.

## Pipeline

Écrits, sans entraînement : `src/acquisition.py`, `src/feu.py`, `src/franchissement.py`, `src/vehicules.py` (ByteTrack, `configs/bytetrack.yaml`, sans poids), `src/plaque.py`, `src/pipeline.py`, `src/preuve.py`. La ligne d'arrêt, la zone du feu et la tolérance de l'orange sont dans `config.yaml`. Les tests sont dans `tests/`. `ocr_plaque.py` et le générateur de plaques ne sont pas écrits.
