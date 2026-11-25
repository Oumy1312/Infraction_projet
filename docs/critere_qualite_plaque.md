# Critère de qualité d'une plaque

Rédigé avant le calcul des distributions réelles et avant l'évaluation des lectures. Les seuils ne se règlent pas après avoir vu les scores.

Le format n'est pas validé. La longueur maximale utilisée ici est seulement celle de `configs/plaque_format.yaml` : 5 chiffres, 1 lettre, 2 chiffres, soit 8 caractères.

Une plaque est de qualité suffisante si les quatre conditions sont vraies en même temps.

1. Largeur du recadrage au moins 96 px. Huit caractères à 12 px chacun : en dessous, le passage vers l'entrée 32×128 agrandit trop les traits pour les séparer.
2. Hauteur du recadrage au moins 24 px. En dessous, un jambage n'a plus assez de rangées.
3. Netteté au moins 50, mesurée par la variance du Laplacien sur le recadrage en niveaux de gris. En dessous, le bord des traits se confond avec un fond lisse. Ce plancher est un seuil de cahier des charges, pas un quantile du jeu.
4. Plaque non coupée : la boîte ne touche pas le bord de l'image d'origine. La marge est de 1 px. Si la boîte atteint ce bord, un caractère peut être hors champ.

L'évaluation publie toujours deux chiffres, calculés à part : les plaques de qualité suffisante, qui sont la cible du cahier des charges, et toutes les plaques.

Voiture et moto sont séparées par le nom de fichier, pas par l'image. La source `moped` est une moto. Toute autre source est comptée voiture. Une photo de deux-roues dont le nom ne contient pas `moped` reste dans les voitures : le fichier ne donne pas d'autre marque.

Une plaque marquée illisible dans l'outil d'annotation est exclue des deux chiffres. Elle n'entre pas dans l'entraînement.
