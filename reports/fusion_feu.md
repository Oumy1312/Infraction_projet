# Fusion HSV v3 et CNN

- Généré : 2026-11-25 21:10
- Bande et règle fixées avant cette mesure. Une seule passe sur les 440 boîtes tenues à part. `config.yaml` n'a pas été modifié.

## Pourquoi les teintes 11 à 21

Chiffres calculés seulement sur l'ajustement (70 %), pas sur les 440.
La teinte médiane est celle des pixels de saturation ≥ 60 et de valeur ≥ 80.

- Rouges d'ajustement : 495 boîtes.
  - 11-21 : 278 (56.2%).
  - ailleurs : 146 (29.5%).
  - 0-10 ou 160-179 : 42 (8.5%).
  - 22-32 : 29 (5.9%).
- Oranges d'ajustement : 35 boîtes.
  - 22-32 : 22 (62.9%).
  - ailleurs : 13 (37.1%).

Sur l'ajustement, 278 rouges sur 495 ont leur teinte médiane dans 11-21, et 42 dans 0-10 ou 160-179. Les oranges tombent surtout dans 22-32 (22 sur 35) : 0 ont leur médiane dans 11-21. La bande n'est pas un trou vide. C'est la zone mesurée de beaucoup de feux annotés rouges, juste avant celle des oranges. La classer « douteux » évite de l'appeler rouge, et fait baisser le rappel du rouge. Elle n'a pas été déplacée après la mesure sur les 440.

## Règle de fusion

- rouge si HSV v3 et la CNN disent tous les deux rouge ;
- vert si les deux disent vert ;
- orange si au moins un des deux dit orange et qu'aucun ne dit rouge ;
- sinon douteux.
- Un douteux ne déclenche pas d'infraction.

## Évaluation

### HSV v3

- Précision globale : 83.2% (366/440).
- Orange ou vert lus rouge : 1 / 245 (0.4%).

| Couleur | Précision | Rappel |
| --- | --- | --- |
| rouge | 99.2% | 66.7% |
| orange | 100.0% | 82.6% |
| vert | 91.9% | 97.7% |

| Vrai \ prédit | rouge | orange | vert | douteux | inconnu | autre |
| --- | --- | --- | --- | --- | --- | --- |
| rouge | 130 | 0 | 17 | 48 | 0 | 0 |
| orange | 0 | 19 | 2 | 2 | 0 | 0 |
| vert | 1 | 0 | 217 | 0 | 4 | 0 |

### CNN

- Précision globale : 96.8% (426/440).
- Orange ou vert lus rouge : 0 / 245 (0.0%).

| Couleur | Précision | Rappel |
| --- | --- | --- |
| rouge | 100.0% | 97.4% |
| orange | 92.0% | 100.0% |
| vert | 100.0% | 95.9% |

| Vrai \ prédit | rouge | orange | vert | douteux | inconnu | autre |
| --- | --- | --- | --- | --- | --- | --- |
| rouge | 190 | 2 | 0 | 0 | 0 | 3 |
| orange | 0 | 23 | 0 | 0 | 0 | 0 |
| vert | 0 | 0 | 213 | 0 | 0 | 9 |

### Fusion

- Précision globale : 83.0% (365/440).
- Orange ou vert lus rouge : 0 / 245 (0.0%).

| Couleur | Précision | Rappel |
| --- | --- | --- |
| rouge | 100.0% | 66.7% |
| orange | 92.0% | 100.0% |
| vert | 100.0% | 95.5% |

| Vrai \ prédit | rouge | orange | vert | douteux | inconnu | autre |
| --- | --- | --- | --- | --- | --- | --- |
| rouge | 130 | 2 | 0 | 63 | 0 | 0 |
| orange | 0 | 23 | 0 | 0 | 0 | 0 |
| vert | 0 | 0 | 212 | 10 | 0 | 0 |

## McNemar apparié

Chaque boîte est une paire : juste ou faux pour les deux méthodes. Le test exact est binomial sur les paires discordantes.

| Comparaison | Seulement A juste | Seulement B juste | p (McNemar exact) |
| --- | --- | --- | --- |
| HSV v3 contre CNN | 5 | 65 | < 0,0001 |
| HSV v3 contre fusion | 5 | 4 | 1,0000 |
| CNN contre fusion | 61 | 0 | < 0,0001 |
