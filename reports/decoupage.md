# Découpage train / val / test

- Généré : 2026-11-24 17:09
- Graine : 42. Parts visées : 70 % / 20 % / 10 %.
- Fuite : même MD5, ou dHash à distance ≤ 4, restent ensemble.
- Le découpage d'origine de `vehicle dataset` n'est pas repris.
- Véhicules : van et threewheel retirés des labels. Feux : toutes les classes d'origine deviennent `traffic_light`. Plaques : classe `plate`.

## vehicles

Ancien découpage, avant la révision van → car. Les chiffres à jour sont dans `reports/vehicules_revise.md`.

- Images retenues alors : 2061.
- train : 1416 images (68.7 %).
- val : 432 images (21.0 %).
- test : 213 images (10.3 %).

## traffic_lights

- Images retenues : 4883.
- Découpage initial (graine 42, dHash) : train 3418, val 977, test 488. Il laissait 449 numéros consécutifs entre train et test.
- Découpage refait pour garder ensemble les quasi-doublons pHash et les numéros proches. Le plus gros groupe fait 3885 images, donc le 70/20/10 n'est pas tenable. Détail dans `reports/fuites.md`.
- train : 3885 images (79.6 %).
- val : 510 images (10.4 %).
- test : 488 images (10.0 %).
- Annotations, une seule classe `traffic_light` :
  - traffic_light : train 9756, val 1089, test 934.
- Labels vides (images négatives) : 3. Après le regroupement : train 0, val 2, test 1.

## plates_detection

- Images retenues : 2016. Groupes de quasi-doublons : 49.
- Boîtes retirées par le mapping : 0.
- train : 1412 images (70.0 %).
- val : 403 images (20.0 %).
- test : 201 images (10.0 %).
- Annotations :
  - plate : train 1422, val 416, test 201.
- Deux paires pHash entre sous-ensembles ont été réunies après coup (une image val → train, une image test → val). Détail dans `reports/fuites.md`.
- Plaques d'aire < 0.001 : 16. Conservées. La médiane des plaques est 0,036.

