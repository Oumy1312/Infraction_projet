# Règle proposée pour _a_trier

- Généré : 2026-11-05 11:42
- Aucun fichier n'a été copié ni déplacé.
- Un polygone est converti en boîte englobante seulement pour le rapport largeur/hauteur et l'aire.
- Fichiers mesurés : 1631.

## Références géométriques

Plaques : toutes les boîtes des labels de `dataset/`. Feux : toutes les boîtes des labels train/valid/test déjà routés vers `traffic_lights` (rectangles qui contiennent une classe autre que 0). Les trois labels vides n'ajoutent pas de boîte.

- Plaques : 1596 boîtes, l/h médian 3.788 (p10 1.759, p90 5.521), aire médiane 0.04463.
- Feux : 9501 boîtes, l/h médian 0.233 (p10 0.200, p90 1.111), aire médiane 0.00087.

## Règle

Le rapport largeur/hauteur sépare les références : le p90 des feux (1,11) est sous le p10 des plaques de `dataset/` (1,76). L'aire est calculée et affichée, mais elle ne décide pas : une plaque cadrée de loin a une petite aire, proche de celle d'un feu.

- `traffic_lights` si le format est une boîte et le rapport l/h médian est inférieur ou égal à 1.111.
- `plates_detection` si le rapport l/h médian est supérieur à 1.111. Le p10 des plaques de `dataset/` (1.759) n'est pas le seuil : les plaques de `_a_trier` sont souvent moins larges que ces gros plans, tout en restant au-dessus des feux.
- `incertain` si le format est un polygone et le rapport tombe du côté des feux, ou si aucune boîte mesurable n'existe. Le polygone contredit alors le seuil.
- L'ambiguïté vaut 1 sur le seuil et diminue quand le rapport s'en éloigne. Elle sert à choisir les 10 cas limites.

Cette règle n'est pas appliquée. `_a_trier` n'est pas réécrit.

## Effectifs proposés

| Catégorie | Fichiers |
| --- | --- |
| plates_detection | 406 |
| traffic_lights | 1215 |
| incertain | 10 |

| Format | Plaques | Feux | Incertain |
| --- | --- | --- | --- |
| boite | 108 | 1215 | 0 |
| polygone | 295 | 0 | 10 |
| mixte | 3 | 0 | 0 |
| autre | 0 | 0 | 0 |

## Cas qui contredisent la règle (11)

Un fichier contredit le seuil s'il est un polygone dont le rapport l/h est du côté des feux, si au moins la moitié de ses boîtes est de l'autre côté du seuil, ou s'il est proposé en plaques avec une classe autre que 0. Les polygones sous le seuil sont laissés incertains.

| Label | Proposition | Format | l/h | Contradiction |
| --- | --- | --- | --- | --- |
| train/labels/28161190_jpg.rf.5705d4f0fe3d1d5d9d7b7b15dc61780a.txt | incertain | polygone | 0.845 | polygone dont le rapport l/h est du côté des feux |
| train/labels/28189908_jpg.rf.c0028a8831b7031dcfcde743f176be46.txt | incertain | polygone | 0.909 | polygone dont le rapport l/h est du côté des feux |
| train/labels/28209250_jpg.rf.34146104178b7435354546d271355375.txt | incertain | polygone | 1.092 | polygone dont le rapport l/h est du côté des feux |
| train/labels/28289489_jpg.rf.96b7a04cf4be95aad31fb7229bebf6b8.txt | incertain | polygone | 1.057 | polygone dont le rapport l/h est du côté des feux |
| train/labels/28376480_jpg.rf.001542d59901077df125420cb1c2abe2.txt | incertain | polygone | 0.958 | polygone dont le rapport l/h est du côté des feux |
| train/labels/MA_Moped_6_Rabat_MC26_JEC_jpg.rf.0bf94acb47c9bbd6cabe34f13315a559.txt | incertain | polygone | 0.802 | polygone dont le rapport l/h est du côté des feux |
| valid/labels/28161099_jpg.rf.2bfc1fe26068717ceaf36ba92abaf5bf.txt | incertain | polygone | 1.042 | polygone dont le rapport l/h est du côté des feux |
| valid/labels/28161386_jpg.rf.2e76b3a1ca61ea428bfbc5ca862d81a3.txt | plates_detection | polygone | 1.434 | au moins la moitié des boîtes est de l'autre côté du seuil |
| valid/labels/28408470_jpg.rf.82e4cce469796772512fdbc5c69153cc.txt | incertain | polygone | 0.992 | polygone dont le rapport l/h est du côté des feux |
| valid/labels/MA-2014-moped-55_010171_v-DL_jpeg.rf.23c30ffed9a054ece0da0b78093783b0.txt | incertain | polygone | 0.900 | polygone dont le rapport l/h est du côté des feux |
| valid/labels/MA_Moped_26_Marrakech_JEC_jpg.rf.016c0106527b89fcafcea81e05f4438e.txt | incertain | polygone | 0.918 | polygone dont le rapport l/h est du côté des feux |

## Groupes préfixe × résolution

- Groupes : 1631.
- Groupes d'un seul fichier : 1631.
- Groupes de plusieurs fichiers : 0.
- Le préfixe est le nom avant `_jpg.rf.`. Sans ce motif, le préfixe indique `(sans _jpg.rf.)` puis le nom avant un autre `.rf.` s'il existe.
- Le tableau complet est `reports/a_trier_groupes.csv`. Les mesures fichier par fichier sont dans `reports/a_trier_mesures.csv`.

Répartition par résolution, tous préfixes confondus :

| Résolution | Fichiers | Préfixes | l/h | Aire | Boîtes | Polygones | Mixtes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 640x640 | 1631 | 1631 | 0.243 | 0.00165 | 1323 | 305 | 3 |

## Planches

Trente images aléatoires par catégorie proposée, graine 42. La planche des ambigus montre les 10 fichiers à la frontière, du plus ambigu au moins ambigu.

- `reports/contact_regle_plates_detection.jpg`
- `reports/contact_regle_traffic_lights.jpg`
- `reports/contact_regle_incertain.jpg`
- `reports/contact_regle_ambigus.jpg`

## Contenu de dataset/

- Images : 1596 (.jpeg 2, .jpg 1594).
- Labels : 1596.
- Images sans label : 0.
- Labels sans image : 0.
- Sous-dossiers d'images : dataset.
- Format des labels : yolo_bbox 1596.
- Classes présentes (identifiants) : 0.
- `obj.names` : license_plate.
- `yolov4-obj.cfg` : classes=1, 1, 1. Le fichier de poids n'est pas ouvert.
- `data (2).yaml` : names=['plate'] ; chemins train=../train/images, val=../valid/images, test=../test/images.
- Ces chemins YAML visent `../train/images`, `../valid/images` et `../test/images`. Ils ne décrivent pas le dossier `dataset/`.
- Correspondance : `dataset/` est le jeu Darknet de plaques (`obj.names` = license_plate, une classe dans le `.cfg`, labels YOLO à une classe). `data (2).yaml` décrit aussi une classe `plate`, mais ses chemins ne pointent pas vers ce dossier.

