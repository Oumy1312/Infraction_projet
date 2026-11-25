# Réalisme du générateur

- Généré : 2026-11-25 22:25
- Plaques réelles mesurées dans `data/processed/plates_detection` : 2016.
- Ancien générateur, échantillon des images déjà écrites : 1000.
- Générateur ajusté, échantillon non enregistré dans le jeu d'entraînement : 1000.
- L'inventaire des lettres n'a pas été modifié. Il est lu dans `configs/plaque_format.yaml`.
- Le jeu des 20 000 plaques déjà produit n'est pas régénéré : la CNN de référence a été entraînée dessus.
- Le générateur ajusté tire une plaque réelle au hasard et reprend sa largeur, sa hauteur, sa luminosité et son contraste. Il ajoute ensuite, chacune avec une chance sur deux : flou de mouvement, compression JPEG, réduction puis agrandissement, ombre, perspective, bruit de fond, plaque sale ou rayée.

| Mesure | Réel | Ancien générateur | Générateur ajusté |
| --- | --- | --- | --- |
| Rapport largeur/hauteur | 2.7 (p10 1.3, p50 2.8, p90 3.9) | 3.3 (p10 3.3, p50 3.3, p90 3.3) | 2.6 (p10 1.3, p50 2.7, p90 3.9) |
| Luminosité (moyenne des gris) | 120.5 (p10 66.8, p50 121.5, p90 173.4) | 186.9 (p10 148.2, p50 189.6, p90 221.8) | 123.7 (p10 73.5, p50 124.8, p90 173.0) |
| Contraste (écart-type des gris) | 60.4 (p10 34.3, p50 61.5, p90 83.5) | 58.6 (p10 46.3, p50 57.6, p90 72.5) | 52.7 (p10 31.6, p50 54.0, p90 71.4) |
| Largeur (px) | 249.1 (p10 79.0, p50 232.5, p90 444.0) | 360.0 (p10 360.0, p50 360.0, p90 360.0) | 245.2 (p10 79.9, p50 231.0, p90 438.0) |
| Hauteur (px) | 102.9 (p10 29.0, p50 89.0, p90 198.0) | 110.0 (p10 110.0, p50 110.0, p90 110.0) | 103.7 (p10 30.0, p50 89.0, p90 199.0) |

La moyenne est suivie des 10e, 50e et 90e centiles. Le contraste ajusté reste un peu sous le réel : caler un écart-type élevé dans une image codée de 0 à 255 écrête les extrêmes.

## Effet de chaque dégradation sur les 150 plaques réelles

Aucune transcription réelle n'est saisie. L'effet de chaque dégradation sur les 150 plaques n'est donc pas calculé. Relancer `python scripts/04_synth_plates.py --realisme` après la saisie : le script appliquera chaque dégradation à part et donnera la plaque entière exacte et le CER, pour la segmentation+CNN et pour le CRNN.

