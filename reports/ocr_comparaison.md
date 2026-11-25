# Comparaison des lectures de plaque

- Généré : 2026-11-25 22:54
- Chaque ligne dit ce qu'elle mesure. Aucun de ces chiffres n'est une précision globale.
- Intervalle de confiance : bootstrap, 1 000 tirages avec remise, quantiles 2,5 % et 97,5 %, graine 42.
- CER = distance de Levenshtein / longueur de la référence.
- La qualité suffisante est le critère de `docs/critere_qualite_plaque.md`, fixé avant cette mesure.
- Les plaques réelles ne servent pas à l'entraînement. Une plaque marquée illisible est exclue.
- Synthétique : la part `eval` de `data/synthetic/plaques`. Le cyclomoteur n'y est pas généré, donc pas de ligne moto.

Sur ce fichier, les 2 000 images synthétiques tenues à part passent le critère de qualité : les deux sous-ensembles ont le même effectif. Le seuil n'a pas été modifié après ce constat.

## Composition des 150 plaques réelles, avant toute transcription

Ce tableau ne mesure pas une lecture. Il compte les images selon le critère fixé et selon la source (`moped` = moto).

| Véhicule | Groupe | Images |
| --- | --- | --- |
| moto | qualité suffisante | 5 |
| voiture | en dessous du critère | 11 |
| voiture | qualité suffisante | 134 |

## Chiffre qui n'est pas une lecture de plaque entière

Dans `reports/ocr_chars.md`, l'exactitude de la CNN porte sur des caractères synthétiques déjà segmentés, et seulement quand le nombre de contours égalait le texte posé. Ce n'est pas la précision globale, ni un score de plaque entière, ni un score réel.

### segmentation + CNN — synthétique tenu à part

Synthétique, plaque entière, part tenue à part, générateur déjà écrit dans `etiquettes.csv`. Ce n'est pas le score des caractères déjà segmentés.

| Sous-ensemble | N | Plaque entière exacte | IC 95 % | CER | IC 95 % |
| --- | --- | --- | --- | --- | --- |
| toutes | 2000 | 47.3 % | 45.4 % – 49.5 % | 17.4 % | 16.3 % – 18.4 % |
| qualité suffisante | 2000 | 47.3 % | 45.4 % – 49.5 % | 17.4 % | 16.3 % – 18.4 % |

Écarts, 12 premiers :

| Image | Référence | Lecture |
| --- | --- | --- |
| 00010.jpg | 12067ث40 | 120674 |
| 00020.jpg | 18141ذ4 |  |
| 00030.jpg | 73342ض78 | 3ز2ضه |
| 00040.jpg | 89241ي8 | 89241ي |
| 00050.jpg | 32ز9 | 329 |
| 00080.jpg | 63938و61 | 63938و6 |
| 00110.jpg | 124ن6 | 1246 |
| 00140.jpg | 71024ص7 | 710247 |
| 00150.jpg | 8ت7 | 87 |
| 00160.jpg | 6572ف13 | 6572ف1 |
| 00200.jpg | 4ق3 | ق |
| 00220.jpg | 6ق4 | ق |

### segmentation + CNN — réel

Réel, plaque entière, transcriptions saisies dans `data/test_plaques/verite.csv`. Voiture = toute source sauf `moped`. Moto = source `moped`.

| Sous-ensemble | N | Plaque entière exacte | IC 95 % | CER | IC 95 % |
| --- | --- | --- | --- | --- | --- |
| toutes | 0 | — | — | — | — |
| qualité suffisante | 0 | — | — | — | — |
| voitures, toutes | 0 | — | — | — | — |
| motos, toutes | 0 | — | — | — | — |
| voitures, qualité suffisante | 0 | — | — | — | — |
| motos, qualité suffisante | 0 | — | — | — | — |

### CRNN — synthétique tenu à part

Synthétique, plaque entière, part tenue à part, générateur déjà écrit dans `etiquettes.csv`. Ce n'est pas le score des caractères déjà segmentés.

| Sous-ensemble | N | Plaque entière exacte | IC 95 % | CER | IC 95 % |
| --- | --- | --- | --- | --- | --- |
| toutes | 2000 | 94.3 % | 93.2 % – 95.2 % | 0.8 % | 0.7 % – 1.0 % |
| qualité suffisante | 2000 | 94.3 % | 93.2 % – 95.2 % | 0.8 % | 0.7 % – 1.0 % |

Écarts, 12 premiers :

| Image | Référence | Lecture |
| --- | --- | --- |
| 00080.jpg | 63938و61 | 63938و6 |
| 00160.jpg | 6572ف13 | 6572ف1 |
| 00430.jpg | 24115أ79 | 24115أ74 |
| 00480.jpg | 9007ب55 | 9007ب5 |
| 00880.jpg | 55633ن42 | 55633ن4 |
| 01020.jpg | 73111ذ3 | 73111ز3 |
| 01050.jpg | 4690ش10 | 4690ش1 |
| 01120.jpg | 2241ع86 | 2241ع80 |
| 01150.jpg | 47127د7 | 47127د1 |
| 01490.jpg | 94012ح16 | 94012ح1 |
| 01530.jpg | 46110م38 | 46110م3 |
| 01640.jpg | 14671ك58 | 14671ك5 |

### CRNN — réel

Réel, plaque entière, transcriptions saisies dans `data/test_plaques/verite.csv`. Voiture = toute source sauf `moped`. Moto = source `moped`.

| Sous-ensemble | N | Plaque entière exacte | IC 95 % | CER | IC 95 % |
| --- | --- | --- | --- | --- | --- |
| toutes | 0 | — | — | — | — |
| qualité suffisante | 0 | — | — | — | — |
| voitures, toutes | 0 | — | — | — | — |
| motos, toutes | 0 | — | — | — | — |
| voitures, qualité suffisante | 0 | — | — | — | — |
| motos, qualité suffisante | 0 | — | — | — | — |

