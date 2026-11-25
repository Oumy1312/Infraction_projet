# CNN des caractères

- Généré : 2026-11-25 21:50
- Réseau écrit de zéro. Aucun poids extérieur, aucun YOLO.
- Appareil : cpu. Époques terminées : 12/12. Durée : 2.6 min. Limite demandée : 20.0 min.
- Caractères d'entraînement : 49449. Caractères de la part tenue à part : 5593.
- Classes (38) lues dans `configs/plaque_format.yaml`, statut À VALIDER.
- Poids : `data\models\ocr_chars.pt`.

L'exactitude ci-dessous porte sur des caractères déjà segmentés, appariés de gauche à droite parce que le nombre de contours égalait le texte posé. Ce n'est pas une lecture de plaque réelle.

| Époque | Perte | Exactitude sur la part tenue à part | Secondes |
| --- | --- | --- | --- |
| 1 | 1.5839 | 88.8 % | 14 |
| 2 | 0.6911 | 95.2 % | 27 |
| 3 | 0.5750 | 97.4 % | 40 |
| 4 | 0.4969 | 98.4 % | 53 |
| 5 | 0.4477 | 96.6 % | 65 |
| 6 | 0.4223 | 98.7 % | 79 |
| 7 | 0.3880 | 99.0 % | 91 |
| 8 | 0.3664 | 98.8 % | 105 |
| 9 | 0.3488 | 98.5 % | 118 |
| 10 | 0.3340 | 98.2 % | 131 |
| 11 | 0.3164 | 99.0 % | 145 |
| 12 | 0.3047 | 99.1 % | 157 |

