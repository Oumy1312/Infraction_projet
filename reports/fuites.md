# Fuites train / val / test

- Généré : 2026-11-24 18:07
- Hash : pHash imagehash, 64 bits. Quasi-identique : distance de Hamming <= 5.
- Numéros proches : identifiants à 6 chiffres dont l'écart est de 1 à 2. Un écart de 5 relierait 3 899 feux en deux blocs d'environ 1 950 images, impossibles à répartir en 70/20/10. L'écart 2 laisse des groupes dont le plus gros tient dans train.
- Graine du nouveau découpage des feux : 42.

## Avant

- vehicles : train 1416, val 432, test 213. Paires pHash entre sous-ensembles : aucune.
- traffic_lights : train 3418, val 977, test 488. Paires pHash entre sous-ensembles : test/train 115, test/val 15, train/val 257.
- plates_detection : train 1411, val 403, test 202. Paires pHash entre sous-ensembles : test/val 1, train/val 1. Ces deux paires ont été réunies ensuite, sans refaire tout le découpage : `VID-20200725-WA0372 02.jpg` val → train, `IMG-20200725-WA0309.jpg` test → val. Effectifs après : train 1412, val 403, test 201. Plus aucune paire pHash entre sous-ensembles.
- Feux, numéros consécutifs (écart 1) dans deux sous-ensembles : test/train 449, test/val 169, train/val 942.
- Feux, numéros proches (écart <= 2) dans deux sous-ensembles : test/train 511, test/val 187, train/val 1049.

## Après le regroupement des feux

Les paires à distance <= 5 forment une chaîne. 4 249 hashs sont distincts sur 4 883 images, et 400 paires tirées au hasard dans le plus gros groupe ont une distance médiane de 30 (minimum 6, aucune <= 5). Ce n'est pas une image répétée : chaque image est proche de ses voisines, et la fermeture transitive relie 3 885 images. Couper ce groupe remettrait au moins une paire <= 5 dans deux sous-ensembles. Le 70/20/10 est donc impossible si les quasi-doublons restent ensemble.

Le plus gros groupe (3 885) est dans train. Les 998 images restantes remplissent d'abord la cible de test, puis val.

- Premier placement, fuites déjà à zéro : train 3885, val 743, test 255.
- Rééquilibrage : 681 images déplacées.
- traffic_lights : train 3885 (79.6%), val 510 (10.4%), test 488 (10.0%).
- 682 groupes. Tailles des plus gros : 3885, 52, 26, 15, 14, 13, 13, 12.
- Paires pHash entre sous-ensembles : aucune.
- Numéros consécutifs entre sous-ensembles : aucune.
- Numéros proches (écart <= 2) entre sous-ensembles : aucune.

Les jeux vehicles n'ont pas été redécoupés. Les deux paires de plaques signalées dans Avant ont été réunies, voir cette section.

Planche de 30 exemples (état avant, priorité aux paires train/test) : `reports/contact_fuites.jpg`.
