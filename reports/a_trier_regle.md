# Règle proposée pour _a_trier

- Généré : 2026-11-24 16:31
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

## Contrôle avant application

Dry-run : aucune copie. Quarante images aléatoires par catégorie (graine 42), toutes les images dont le rapport l/h est entre 0,9 et 1,3, et les incertains. La classe prévue est écrite sur chaque image.

- Référence feux : 1036 boîtes avec l/h ≥ 1 (boîtier horizontal ou carré), dont 949 au-dessus du seuil 1.111. Ces boîtes, si elles étaient seules dans un fichier de classe 0, partiraient en plaques.
- Bande 0,9–1,3 : 26 fichiers (plaques 14, feux 4, incertains 8).
- Risque de feu horizontal classé plaque : 11 fichiers. Critère : proposé en plaques, et soit une boîte de l/h entre le seuil et 2,5 avec une aire ≤ p90 des feux (0.00225), soit un nom de type S2TLD avec l/h ≤ 2,5.

## Planches

Les planches `contact_regle_` reprennent l'échantillon de la règle. Les planches `contact_verif_` sont le contrôle demandé avant application.

- `reports/contact_regle_plates_detection.jpg`
- `reports/contact_regle_traffic_lights.jpg`
- `reports/contact_regle_incertain.jpg`
- `reports/contact_regle_ambigus.jpg`
- `reports/contact_verif_plates_detection.jpg`
- `reports/contact_verif_traffic_lights.jpg`
- `reports/contact_verif_incertain.jpg`
- `reports/contact_verif_ratio_09_13.jpg`
- `reports/contact_verif_incertains.jpg`
- `reports/contact_verif_feux_horizontaux.jpg`
- `reports/contact_verif_ratio_06_09.jpg`
- `reports/contact_rev_changements.jpg`
- `reports/contact_rev_plates_detection.jpg`
- `reports/contact_rev_traffic_lights.jpg`

## Étape 1b — seuil révisé (non appliqué)

Le seuil l/h > 1,11 n'est pas validé : quatre plaques presque carrées partiraient en feux. Rien n'est copié.

### Histogramme des boîtes de classe 0

Toutes les boîtes de classe 0 des fichiers de `_a_trier` : 2721 boîtes. Tranches de 0,1, de 0 à 6. Figure : `reports/hist_ratio.png`.

| Tranche l/h | Boîtes |
| --- | --- |
| 0.0–0.1 | 0 |
| 0.1–0.2 | 244 |
| 0.2–0.3 | 1935 |
| 0.3–0.4 | 79 |
| 0.4–0.5 | 7 |
| 0.5–0.6 | 11 |
| 0.6–0.7 | 3 |
| 0.7–0.8 | 0 |
| 0.8–0.9 | 2 |
| 0.9–1.0 | 8 |
| 1.0–1.1 | 5 |
| 1.1–1.2 | 8 |
| 1.2–1.3 | 6 |
| 1.3–1.4 | 10 |
| 1.4–1.5 | 8 |
| 1.5–1.6 | 12 |
| 1.6–1.7 | 8 |
| 1.7–1.8 | 13 |
| 1.8–1.9 | 9 |
| 1.9–2.0 | 11 |
| 2.0–2.1 | 9 |
| 2.1–2.2 | 10 |
| 2.2–2.3 | 12 |
| 2.3–2.4 | 15 |
| 2.4–2.5 | 11 |
| 2.5–2.6 | 22 |
| 2.6–2.7 | 14 |
| 2.7–2.8 | 15 |
| 2.8–2.9 | 22 |
| 2.9–3.0 | 28 |
| 3.0–3.1 | 23 |
| 3.1–3.2 | 17 |
| 3.2–3.3 | 25 |
| 3.3–3.4 | 22 |
| 3.4–3.5 | 23 |
| 3.5–3.6 | 13 |
| 3.6–3.7 | 13 |
| 3.7–3.8 | 15 |
| 3.8–3.9 | 13 |
| 3.9–4.0 | 9 |
| 4.0–4.1 | 3 |
| 4.1–4.2 | 0 |
| 4.2–4.3 | 1 |
| 4.3–4.4 | 1 |
| 4.4–4.5 | 0 |
| 4.5–4.6 | 0 |
| 4.6–4.7 | 1 |
| 4.7–4.8 | 1 |
| 4.8–4.9 | 1 |
| 4.9–5.0 | 0 |
| 5.0–5.1 | 0 |
| 5.1–5.2 | 0 |
| 5.2–5.3 | 0 |
| 5.3–5.4 | 1 |
| 5.4–5.5 | 0 |
| 5.5–5.6 | 1 |
| 5.6–5.7 | 0 |
| 5.7–5.8 | 0 |
| 5.8–5.9 | 0 |
| 5.9–6.0 | 0 |
| > 6 | 1 |

- Boîtes au-dessus de 6 : 1.
- Médiane de fichier la plus haute parmi les préfixes à 6 chiffres : 0.628.
- Médiane de fichier la plus basse parmi les autres préfixes : 0.802.
- Intervalle vide entre ces deux médianes de fichier : 0.628 à 0.802. Aucun fichier n'a sa médiane dans cet intervalle.

### Bande 0,6–0,9

3 images ont une médiane l/h entre 0,6 et 0,9. Planche : toutes les 3 images. Classe affichée = groupe actuel (seuil 1,11).

- Plaques 0, feux 1, incertains 2.

### Préfixe de source

Le préfixe de famille regroupe les noms du même jeu (MA-2014-moped, Morocco_license_plate, marokko, identifiant numérique). Les parts sont celles des groupes actuels, seuil 1,11. Le ratio moyen est la moyenne des médianes de fichier.

| Préfixe | Fichiers | l/h moyen | Plaques | Feux | Incertains | Pureté |
| --- | --- | --- | --- | --- | --- | --- |
| id_6_chiffres | 1211 | 0.237 | 0 (0 %) | 1211 (100 %) | 0 (0 %) | uniquement feux |
| id_8_chiffres | 363 | 2.749 | 356 (98 %) | 0 (0 %) | 7 (2 %) | mixte |
| morocco | 11 | 2.545 | 11 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| marokko | 9 | 2.613 | 8 (89 %) | 1 (11 %) | 0 (0 %) | mixte |
| T | 6 | 3.518 | 6 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| download | 4 | 2.284 | 4 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| unnamed | 4 | 2.010 | 4 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| MA-2014-moped | 3 | 0.929 | 0 (0 %) | 2 (67 %) | 1 (33 %) | mixte |
| ma_ | 3 | 3.223 | 3 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| MA_Moped | 2 | 0.860 | 0 (0 %) | 0 (0 %) | 2 (100 %) | uniquement incertains |
| auto-ecole | 2 | 2.012 | 2 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| 28377180-1- | 1 | 2.954 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| 28408427-1- | 1 | 2.264 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| 28408429-1- | 1 | 1.921 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| 29070966-1- | 1 | 2.950 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| 420123591_925103558666380_30171006332642 | 1 | 5.554 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| 474879887_18029719742563274_217600736199 | 1 | 4.794 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| Morocco_license_plate | 1 | 1.004 | 0 (0 %) | 1 (100 %) | 0 (0 %) | uniquement feux |
| OIP | 1 | 3.344 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| Trafic-routier-Maroc-Autoroute | 1 | 2.193 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| autoroute-du-maroc-berchid00885-2-166083 | 1 | 2.333 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| o9lyqyhcx4u | 1 | 2.946 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| renting-cars-morocco-guide-900x600 | 1 | 2.531 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |
| une-scene-de-rue-dans-la-ville-de-casabl | 1 | 3.174 | 1 (100 %) | 0 (0 %) | 0 (0 %) | uniquement plaques |

Un préfixe « uniquement feux » ne contient que des fichiers déjà classés feux. Un préfixe « uniquement plaques » ne contient que des fichiers déjà classés plaques. Les dix incertains sont des plaques au regard des images, mais ils restent dans la colonne Incertains de ce tableau parce que la règle 1,11 ne les a pas encore déplacés.

Le seul préfixe qui ne contient que des feux, une fois les plaques carrées remises à leur place, est `id_6_chiffres` (1 211 fichiers). `Morocco_license_plate` apparaît « uniquement feux » parce que son unique fichier a un l/h de 1,004 et que le seuil 1,11 l'a envoyé en feux : c'est une des quatre plaques presque carrées. `marokko` et `MA-2014-moped` sont mixtes pour la même raison (une ou deux plaques carrées classées feux). `MA_Moped` ne contient que les deux incertains, qui sont des plaques. `id_8_chiffres` est mixte seulement à cause de sept incertains, sans aucun feu.

### Règle révisée proposée

(a) Nouveau seuil : médiane l/h du fichier **supérieure à 0.70** → `plates_detection`, sinon `traffic_lights`. L'histogramme des 2721 boîtes a un vide : aucune boîte entre 0,7 et 0,8. En dessous, 2 279 boîtes (le pic est 0,2–0,3). Au-dessus, les plaques, y compris les presque carrées des tranches 0,8–1,1. Le même vide existe sur les médianes de fichier : les préfixes à 6 chiffres s'arrêtent à 0.628, les autres commencent à 0.802. Le 0,70 est au milieu. Le 1,11 est trop haut : il coupe dans ces plaques presque carrées et en envoie quatre en feux. Les tranches vides au-delà de 4 sont des plaques larges peu nombreuses, pas un second seuil.

(b) Une règle par préfixe donne exactement le même partage sur ces 1 631 fichiers : identifiant à 6 chiffres → `traffic_lights` ; tout autre préfixe → `plates_detection`. Elle est plus sûre si un futur lot recouvre les rapports, parce qu'elle ne dépend pas d'une plaque carrée ou d'un feu un peu large. Les deux règles sont d'accord aujourd'hui. La règle de préfixe est celle à retenir si une seule règle doit décider.

(c) Nouvelle répartition, non appliquée :

| Catégorie | Fichiers |
| --- | --- |
| plates_detection | 420 |
| traffic_lights | 1211 |
| incertain | 0 |

Images qui changent de groupe par rapport à l/h > 1,11 : 14.

| Passage | Fichiers |
| --- | --- |
| incertain → plates_detection | 10 |
| traffic_lights → plates_detection | 4 |

Les dix fichiers aujourd'hui incertains sont des plaques. Proposition : les envoyer vers `plates_detection`. La conversion polygone → rectangle (min/max des points, normalisé entre 0 et 1) se fera plus tard dans `data/interim/`. Elle n'est pas faite ici. Les originaux restent intacts.

Planches de la règle révisée : toutes les images qui changent de groupe, puis 40 images au hasard (graine 42) par nouveau groupe. Le bandeau indique la nouvelle classe. La légende rappelle l'ancienne quand elle diffère.

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

