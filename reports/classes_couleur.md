# Classes de couleur des feux

- Généré : 2026-11-24 19:50
- Source : `data/raw/traffic_lights`. Aucun label n'a été supprimé ni réécrit.
- La copie `data/interim/feux_couleur/` reste en place pour l'évaluation HSV.
- Le détecteur traité reste à une seule classe `traffic_light`.

## Treize classes d'origine

| Id | Nom d'origine | Boîtes | Fichiers | Proposition | Pourquoi |
| --- | --- | --- | --- | --- | --- |
| 0 | go 0 | 3525 | 1850 | autre | Le nom « go » est un état, pas une couleur. Sur les fichiers à 6 chiffres, la classe 0 n'a jamais été une couleur. |
| 1 | go_left | 263 | 172 | autre | Flèche vers la gauche. |
| 2 | go_right | 14 | 14 | autre | Flèche vers la droite. |
| 3 | green | 648 | 463 | vert | Le nom est la couleur verte. |
| 4 | off | 3 | 3 | autre | Feu éteint. |
| 5 | off 4 | 501 | 323 | autre | Feu éteint. Le « 4 » est un ancien numéro collé au nom. |
| 6 | red | 690 | 494 | rouge | Le nom est la couleur rouge. |
| 7 | stop 2 | 4390 | 2201 | autre | État « stop », pas une couleur annotée. Ne pas le ranger en rouge sans revoir les images. |
| 8 | stop_left | 1283 | 971 | autre | Flèche d'arrêt. |
| 9 | wait_on | 247 | 246 | autre | État d'attente. Le nom ne dit pas orange. |
| 10 | warn 3 | 131 | 78 | autre | Avertissement. Souvent proche de l'ambre, mais le nom n'est pas « yellow ». |
| 11 | warn_left | 26 | 15 | autre | Flèche d'avertissement. |
| 12 | yellow | 58 | 50 | orange | « yellow » est le feu ambre, appelé orange ici. |

## Totaux de la proposition

Ces totaux comptent toutes les boîtes, y compris la classe 0 des fichiers à 6 chiffres, qui n'est pas une couleur.

| Groupe | Boîtes |
| --- | --- |
| rouge | 690 |
| orange | 58 |
| vert | 648 |
| autre | 10383 |

## Classe 0 à part

- Fichiers à 6 chiffres qui ne contiennent que la classe 0 : 1211. Boîtes : 2278.
- Autres boîtes de classe 0 (nom d'origine « go 0 », dans les fichiers S2TLD) : 1247.
- Les 1 211 fichiers à 6 chiffres, s'ils sont dans ce compte, n'ont jamais eu de rouge, d'orange ou de vert. Les laisser en « autre ».

Seules trois classes portent un nom de couleur : `red` → rouge, `yellow` → orange, `green` → vert. Le reste est un état, une flèche ou un feu éteint. Les ranger dans une couleur serait une supposition.
