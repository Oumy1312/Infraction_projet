# Annoter une vidéo de Marrakech

Les images viennent de `scripts/08_extract_frames.py`. Le pas, en secondes, se règle avec `--every`. Les images vont dans `data/test_scenes/images`. Les labels YOLO vont dans `data/test_scenes/labels`, avec le même nom de fichier et l'extension `.txt`.

## Classes

Une ligne de label : `classe centre_x centre_y largeur hauteur`, coordonnées normalisées entre 0 et 1.

| Id | Classe |
| --- | --- |
| 0 | car |
| 1 | bus |
| 2 | truck |
| 3 | motorcycle |
| 4 | traffic_light |
| 5 | plate |

Ce sont les noms de `data/test_scenes/data.yaml`. On annote le véhicule qui peut franchir la ligne, le feu qui le concerne, et la plaque si elle est lisible. Une image sans objet a un fichier label vide.

## Infractions réelles

Le fichier `data/test_scenes/infractions_verite.csv` est indépendant des boîtes. Une ligne décrit un intervalle de temps, pas une image.

Colonnes : `video`, `temps_debut_s`, `temps_fin_s`, `vehicule`, `feu_rouge_oui_non`, `remarque`.

- `video` est le nom du fichier vidéo, sans le dossier.
- `temps_debut_s` et `temps_fin_s` entourent le franchissement, en secondes depuis le début de la vidéo.
- `vehicule` reprend la classe : car, bus, truck ou motorcycle.
- `feu_rouge_oui_non` vaut `oui` seulement si le feu qui commande cette voie était rouge au moment du franchissement. `non` sert à noter un franchissement qui n'est pas une infraction.
- `remarque` est libre : feu masqué, plaque illisible, cas douteux.

`scripts/09_eval_pipeline.py` ne compte comme vérité positive que les lignes `oui`. La tolérance, en secondes, élargit l'intervalle pour associer une détection.
