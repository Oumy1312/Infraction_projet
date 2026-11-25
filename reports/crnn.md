# CRNN

- Généré : 2026-11-25 22:54
- Réseau écrit de zéro : convolutions, BiLSTM, perte CTC. Aucun poids pré-entraîné. Aucune plaque réelle.
- Entrée : niveaux de gris 32×128. Alphabet lu dans `configs/plaque_format.yaml` (38 caractères, plus le blanc CTC).
- Appareil : cpu. Dernière époque : 12. Durée de cette session : 16.1 min.
- Synthétique d'entraînement : 18000. Synthétique tenu à part : 2000.

Les chiffres ci-dessous sont des plaques entières synthétiques tenues à part. Ce n'est pas une précision sur les plaques réelles, ni l'exactitude de la CNN sur des caractères déjà segmentés.

| Époque | Perte | Plaque entière exacte | CER | Secondes |
| --- | --- | --- | --- | --- |
| 1 | 4.859 | 0.0 % | 83.0 % | 117 |
| 2 | 1.418 | 3.0 % | 28.7 % | 236 |
| 3 | 0.831 | 15.7 % | 19.2 % | 355 |
| 4 | 0.497 | 42.8 % | 13.3 % | 426 |
| 5 | 0.285 | 66.4 % | 7.0 % | 507 |
| 6 | 0.172 | 50.1 % | 11.8 % | 572 |
| 7 | 0.116 | 84.7 % | 2.8 % | 637 |
| 8 | 0.076 | 91.2 % | 1.4 % | 703 |
| 9 | 0.062 | 87.5 % | 2.1 % | 769 |
| 10 | 0.052 | 87.7 % | 2.1 % | 835 |
| 11 | 0.042 | 88.0 % | 2.1 % | 901 |
| 12 | 0.038 | 94.3 % | 0.8 % | 967 |

