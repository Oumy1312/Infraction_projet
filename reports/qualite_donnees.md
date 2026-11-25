# Qualité des données

- Généré : 2026-11-24 17:07
- Lecture de `data/interim` pour les labels et de `data/raw` pour les images.
- Correction automatique : une boîte dont une coordonnée sort de [0, 1] mais reste dans [-0.02, 1.02] est ramenée dans [0, 1]. Une boîte de taille nulle est retirée.
- Au-delà de cette tolérance, la boîte est listée et laissée telle quelle.

- Labels lus : 9899.
- Boîtes rognées : 178.
- Boîtes de taille nulle retirées : 0.
- Boîtes hors tolérance, non corrigées : 0.
- Labels vides après contrôle : 3.
- Images illisibles : 0.
- Labels sans image : 0.
- Images sans label : 0.
- Lignes de label illisibles : 0.

## Annotations par classe

Identifiants encore ceux des fichiers d'origine. Le mapping véhicules est appliqué plus tard, au découpage.

- vehicles : 3835 boîtes (0 → 662, 1 → 709, 2 → 588, 3 → 629, 4 → 699, 5 → 548).
- traffic_lights : 11779 boîtes (0 → 3525, 1 → 263, 2 → 14, 3 → 648, 4 → 3, 5 → 501, 6 → 690, 7 → 4390, 8 → 1283, 9 → 247, 10 → 131, 11 → 26, 12 → 58).
- plates_detection : 2039 boîtes (0 → 2039).
- _incertains : aucune annotation.

## Taille des boîtes (aire relative)

- vehicles : n=3835, min=0.00082, p10=0.04948, médiane=0.42658, p90=0.77244.
- traffic_lights : n=11779, min=0.00004, p10=0.00030, médiane=0.00093, p90=0.00242.
- plates_detection : n=2039, min=0.00012, p10=0.00562, médiane=0.03633, p90=0.09302.

Seuil « très petite » : aire relative < 0.001. Ces boîtes sont conservées.

- Motos (classe 4 d'origine, motorbike) sous le seuil : 0.
- Plaques sous le seuil : 16.

Mesure complémentaire, par classe, après rognage. Aire relative = largeur × hauteur.

- car : médiane 0,402, minimum 0,00082 (1 boîte sous 0,001).
- motorbike : médiane 0,303, minimum 0,00113, 18 boîtes sous 0,005, aucune sous 0,001.
- bus : médiane 0,468. truck : médiane 0,479.
- plaques : médiane 0,036, 16 boîtes sous 0,001, minimum 0,00012.

Résultat surprenant : les boîtes véhicules couvrent souvent une grande part de l'image (médiane véhicules 0,43). Ce jeu ressemble à des photos d'objets cadrés, pas à des véhicules lointains vus depuis une caméra de feu. Les motos ne sont pas les petites boîtes attendues. Les 16 petites plaques sont conservées.

## Doublons exacts (MD5)

- vehicles : 55 groupe(s) de fichiers identiques.
  - data/raw/vehicles/train/images/00077.jpg et 1 autre(s)
  - data/raw/vehicles/train/images/3d-render-autorickshaw-isolated-on-260nw-1396796471.jpg et 1 autre(s)
  - data/raw/vehicles/train/images/car276.jpg et 1 autre(s)
  - data/raw/vehicles/train/images/lorry115.jpeg et 1 autre(s)
  - data/raw/vehicles/train/images/lorry16.jpeg et 2 autre(s)
  - data/raw/vehicles/train/images/lorry194.jpeg et 1 autre(s)
  - data/raw/vehicles/train/images/lorry285.jpeg et 1 autre(s)
  - data/raw/vehicles/train/images/lorry295.jpeg et 1 autre(s)
  - data/raw/vehicles/train/images/lorry296.jpeg et 2 autre(s)
  - data/raw/vehicles/train/images/lorry301.jpeg et 1 autre(s)
  - data/raw/vehicles/train/images/lorry335.jpeg et 1 autre(s)
  - data/raw/vehicles/train/images/lorry48.jpeg et 2 autre(s)
  - data/raw/vehicles/train/images/lorry495.jpeg et 1 autre(s)
  - data/raw/vehicles/train/images/lorry57.jpeg et 2 autre(s)
  - data/raw/vehicles/train/images/srilankalorry0.jpeg et 2 autre(s)
- traffic_lights : aucun doublon exact.
- plates_detection : 38 groupe(s) de fichiers identiques.
  - data/raw/plates_detection/dataset/images/dataset/IMG_0029 (4).jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0030 (4).jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0091.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0092.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0093.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0094.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0095.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0096.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0097.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0098.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0099.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0100.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0101.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0102.jpg et 1 autre(s)
  - data/raw/plates_detection/dataset/images/dataset/IMG_0103.jpg et 1 autre(s)
- _incertains : aucun doublon exact.

## Listes

### Boîtes hors tolérance

- Aucun.

### Labels vides

- `data/interim/traffic_lights/train/labels/2020-03-30-11_39_03-883268374_jpg.rf.875502c3c0262a166610459ab99ee509.txt`
- `data/interim/traffic_lights/train/labels/2020-03-30-11_44_51-161684229_jpg.rf.2ae62164d774dcdc594c72d0851e935a.txt`
- `data/interim/traffic_lights/train/labels/2020-03-30-12_02_12-042615407_jpg.rf.9ce7d385abf32192baa6718e859799c7.txt`

### Images illisibles

- Aucun.

### Labels sans image

- Aucun.

### Images sans label

- Aucun.

### Lignes illisibles

- Aucun.

### Très petites motos et plaques (30 premières)

- `plaque très petite aire=0.00091 data/interim/plates_detection/test/labels/28694641_jpg.rf.023a96fc375250f78e0df4446af439f8.txt`
- `plaque très petite aire=0.00085 data/interim/plates_detection/train/labels/28188971_jpg.rf.4e2cfacc50ead6f2deafa1387628062c.txt`
- `plaque très petite aire=0.00085 data/interim/plates_detection/train/labels/28225430_jpg.rf.6993fb2d403841916f67dd2a570b4032.txt`
- `plaque très petite aire=0.00087 data/interim/plates_detection/train/labels/Trafic-routier-Maroc-Autoroute_jpg.rf.f3531ea6d7cac31e0e7808fc36dba5f8.txt`
- `plaque très petite aire=0.00046 data/interim/plates_detection/train/labels/autoroute-du-maroc-berchid00885-2-1660835788_jpg.rf.a3a33e4916132e2cd17311ee1f7c3d08.txt`
- `plaque très petite aire=0.00087 data/interim/plates_detection/train/labels/une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt`
- `plaque très petite aire=0.00060 data/interim/plates_detection/train/labels/une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt`
- `plaque très petite aire=0.00021 data/interim/plates_detection/train/labels/une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt`
- `plaque très petite aire=0.00039 data/interim/plates_detection/train/labels/une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt`
- `plaque très petite aire=0.00012 data/interim/plates_detection/train/labels/une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt`
- `plaque très petite aire=0.00016 data/interim/plates_detection/train/labels/une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt`
- `plaque très petite aire=0.00033 data/interim/plates_detection/train/labels/une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt`
- `plaque très petite aire=0.00018 data/interim/plates_detection/train/labels/une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt`
- `plaque très petite aire=0.00055 data/interim/plates_detection/valid/labels/28161386_jpg.rf.2e76b3a1ca61ea428bfbc5ca862d81a3.txt`
- `plaque très petite aire=0.00098 data/interim/plates_detection/valid/labels/28691541_jpg.rf.0e722413b0354a54dff712e5df776117.txt`
- `plaque très petite aire=0.00083 data/interim/plates_detection/valid/labels/28700343_jpg.rf.f10a5a8da4b29a207116c53876e9e1a6.txt`

