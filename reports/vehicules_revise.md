# Véhicules révisés

- Généré : 2026-11-24 19:56
- Les feux et les plaques n'ont pas été redécoupés.
- `van` (classe d'origine 5) est réécrit `car` (classe 0).
- Toute image qui contient au moins une boîte `threewheel` est retirée du jeu, autres boîtes comprises. Elle reste dans `data/raw/vehicles_exclus/threewheel/`.
- Découpage 70/20/10, graine 42. Doublons MD5 et pHash (distance de Hamming <= 5) dans le même sous-ensemble.

## Effectifs

- Images lues dans `data/interim/vehicles` : 3000.
- Images retirées parce qu'elles contiennent un threewheel : 519.
- Parmi elles, présentes dans l'ancien jeu traité : 61.
- Images van seulement, remises dans le jeu : 481 images, 511 boîtes, toutes devenues car.
- Images gardées qui avaient déjà une autre classe et des boîtes van : 29 images, 31 boîtes van devenues car.
- Les 6 boîtes van restantes étaient sur des images threewheel : elles sont sorties avec ces images.
- Copies threewheel manquantes ajoutées dans vehicles_exclus : 0.
- Images écrites : 2481.

## Découpage

- Groupes de quasi-doublons : 2431. Plus gros : 3, 3, 3, 3, 3, 3, 3, 2.
- Paires pHash entre sous-ensembles après placement : aucune.

| Sous-ensemble | Images | Part |
| --- | --- | --- |
| train | 1737 | 70.0% |
| val | 496 | 20.0% |
| test | 248 | 10.0% |

## Annotations

| Classe | train | val | test | total |
| --- | --- | --- | --- | --- |
| car | 841 | 243 | 93 | 1177 |
| bus | 420 | 110 | 39 | 569 |
| truck | 377 | 126 | 115 | 618 |
| motorcycle | 477 | 141 | 49 | 667 |

Les images threewheel seules (celles qui ne sont pas revenues) restent dans `data/raw/vehicles_exclus/threewheel/`. Rien n'a été supprimé de ce dossier.
