# Évaluation HSV v2

- Généré : 2026-11-25 01:07
- Seuils lus dans `configs/hsv_v2.yaml`. `config.yaml` n'a pas été modifié.
- Une seule passe sur les 30 % tenus à part (mêmes groupes pHash que `reports/hsv_eval.md`, graine 42). Aucun seuil n'a été repris ensuite.

## Volume

- Évaluation : 440 boîtes.
- Précision globale v2 : 94.1% (414 / 440).
- v1 sur les mêmes boîtes, pour mémoire : 79.3% (349 / 440).

## Matrice v2

| Vrai \ prédit | rouge | orange | vert | inconnu |
| --- | --- | --- | --- | --- |
| rouge | 178 | 0 | 17 | 0 |
| orange | 2 | 19 | 2 | 0 |
| vert | 1 | 0 | 217 | 4 |

- Orange lu comme rouge : 2 (v1 sur les mêmes boîtes : 0).

## Filtre min_ratio et taille

- Boîtes écartées par min_ratio : 4 / 440 (0.9%).
- Précision sans filtre de taille : 94.1% (414 / 440).
- Précision avec filtre de taille (côté d'au moins 8 px et aire d'au moins 0,0004) : 98.0% (193 / 197).

## Bruit de détecteur

- Chaque boîte d'évaluation est décalée et redimensionnée de 10 à 20 % (graine 42), une seule fois, avec les seuils v2.
- Précision : 93.9% (413 / 440).
- Orange lu comme rouge sous ce bruit : 2.

| Vrai \ prédit | rouge | orange | vert | inconnu |
| --- | --- | --- | --- | --- |
| rouge | 178 | 0 | 17 | 0 |
| orange | 2 | 18 | 3 | 0 |
| vert | 1 | 0 | 217 | 4 |

## Compromis

Orange lu comme rouge augmente : 0 en v1, 2 en v2. La teinte rouge étendue jusqu'à 20 absorbe des lampes orange.

Compromis proposé, non appliqué : laisser un intervalle « douteux » entre les deux teintes, par exemple rouge jusqu'à 10, douteux de 11 à 21, orange à partir de 22. « douteux » ne doit jamais être classé rouge, ni compter comme une infraction.

## Clarifications

Le 98,0 % (193/197) est le filtre de taille, pas `min_ratio`.
Une boîte est écartée par ce filtre si son petit côté fait moins de 8 px, ou si son aire fait moins de 0,0004 de l'image.
Sur 440 boîtes, ce filtre en écarte 243. Il en reste 197.
`min_ratio` n'écarte que 4 boîtes : le meilleur masque coloré n'atteint pas 3 % des pixels. Ce n'est pas le même filtre, et la précision qui en résulte n'est pas 98 %.

| Filtre | Boîtes restantes | Précision HSV v2 |
| --- | --- | --- |
| aucun | 440 | 94.1% (414/440) |
| min_ratio (boîtes non écartées) | 436 | 95.0% (414/436) |
| taille (côté ≥ 8 px et aire ≥ 0,0004) | 197 | 98.0% (193/197) |

Précision et rappel du rouge, sur les 440 boîtes :

| Méthode | Précision rouge | Rappel rouge |
| --- | --- | --- |
| HSV v2 | 98.3% (178/181) | 91.3% (178/195) |
| CNN | 100.0% (190/190) | 97.4% (190/195) |

Les 17 rouges lus verts par HSV v2 sont dans `reports/contact_rouge_vert.jpg`, avec la teinte médiane des pixels saturés, la taille de la boîte et la cause probable.
