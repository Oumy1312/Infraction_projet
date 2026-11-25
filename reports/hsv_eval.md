# Évaluation HSV des feux

- Généré : 2026-11-25 00:50
- Classes utilisées : `red` → rouge, `yellow` → orange, `green` → vert. Les autres classes d'origine ne sont pas notées.
- Séparation par image, graine 42. Les groupes pHash (distance <= 5) restent ensemble : 70 % ajustement, 30 % évaluation.
- Les seuils de `config.yaml` n'ont pas été modifiés. Les chiffres ci-dessous sont ceux de l'évaluation.

## Volume

- Boîtes couleur : 1396 sur 978 images.
- Plus gros groupes pHash : 51, 26, 15, 14, 13, 13.
- Ajustement : 956 boîtes, 685 images.
- Évaluation : 440 boîtes, 293 images.

## Évaluation

- Précision globale (couleur prédite = couleur annotée) : 79.3% (349 / 440).

| Vrai \ prédit | rouge | orange | vert | inconnu |
| --- | --- | --- | --- | --- |
| rouge | 122 | 61 | 12 | 0 |
| orange | 0 | 18 | 2 | 3 |
| vert | 0 | 0 | 209 | 13 |

| Classe | Précision | Prédictions |
| --- | --- | --- |
| rouge | 100.0% | 122 |
| orange | 22.8% | 79 |
| vert | 93.7% | 223 |

## Erreurs

- Erreurs : 91.
- Cause principale : 61 rouges annotés sont lus comme orange. 69 erreurs portent une boîte trop petite. 12 rouges sont lus comme vert. 16 prédictions restent « inconnu » (pas assez de pixels dans les seuils).
- Aucune erreur ne se classe comme feu éteint, flou ou reflet avec ces seuils.
- boîte trop petite, rouge lu comme orange : 48.
- rouge lu comme orange : 13.
- boîte trop petite, rouge lu comme vert : 12.
- pas assez de pixels dans les seuils : 9.
- boîte trop petite, pas assez de pixels dans les seuils : 7.
- boîte trop petite, orange lu comme vert : 2.

Planche de 30 erreurs : `reports/contact_hsv_erreurs.jpg`.

## Seuils

Proposition établie seulement sur l'ajustement (70 %), non appliquée, où elle passerait de 83.3% à 96.7%. L'évaluation n'a pas servi à choisir ces valeurs.

```yaml
min_ratio: 0.03
rouge hue: [[0, 20], [160, 179]], sat_min 60, val_min 80
orange hue: [[22, 32]], sat_min 60, val_min 80
vert hue: [[40, 95]], sat_min 30, val_min 60
```
