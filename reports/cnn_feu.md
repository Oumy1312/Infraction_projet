# CNN de l'état du feu

- Généré : 2026-11-25 01:14
- Modèle de zéro, 48×48, CPU, 8 époques, 6.3 min (plafond 15).
- Ajustement 70 % / évaluation 30 %. Les images déjà réparties par `06_eval_hsv.py` gardent leur côté. Graine 42.
- Pondération de la perte : rouge 4.14, orange 58.50, vert 4.81, autre 0.28.
- Effectifs d'ajustement : rouge 495, orange 35, vert 426, autre 7234.

## Évaluation, quatre classes

- Précision globale : 84.3% (3026 / 3589).
- Orange lu comme rouge : 0.

| Vrai \ prédit | rouge | orange | vert | autre |
| --- | --- | --- | --- | --- |
| rouge | 190 | 2 | 0 | 3 |
| orange | 0 | 23 | 0 | 0 |
| vert | 0 | 0 | 213 | 9 |
| autre | 147 | 26 | 376 | 2600 |

## Couleurs seulement, face au HSV

Mêmes boîtes rouge, orange et vert de l'évaluation. HSV v1 est `config.yaml`, HSV v2 est `configs/hsv_v2.yaml`.

- CNN : 96.8% (426 / 440), orange lu comme rouge 0.
- HSV v1 : 79.3%, orange lu comme rouge 0.
- HSV v2 : 94.1%, orange lu comme rouge 2.

### CNN

| Vrai \ prédit | rouge | orange | vert | inconnu | autre |
| --- | --- | --- | --- | --- | --- |
| rouge | 190 | 2 | 0 | 0 | 3 |
| orange | 0 | 23 | 0 | 0 | 0 |
| vert | 0 | 0 | 213 | 0 | 9 |

### HSV v1

| Vrai \ prédit | rouge | orange | vert | inconnu | autre |
| --- | --- | --- | --- | --- | --- |
| rouge | 122 | 61 | 12 | 0 | 0 |
| orange | 0 | 18 | 2 | 3 | 0 |
| vert | 0 | 0 | 209 | 13 | 0 |

### HSV v2

| Vrai \ prédit | rouge | orange | vert | inconnu | autre |
| --- | --- | --- | --- | --- | --- |
| rouge | 178 | 0 | 17 | 0 | 0 |
| orange | 2 | 19 | 2 | 0 | 0 |
| vert | 1 | 0 | 217 | 4 | 0 |

Poids : `data/models/feu_cnn.pt`.
