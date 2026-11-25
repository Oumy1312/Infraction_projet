# Contrôles avant entraînement

- Généré : 2026-11-24 18:07
- Source Infraction et quarantine/ non lus pour écriture. Aucun poids. Aucun entraînement.

## Classes d'origine des feux

Elles sont encore dans `data/raw/traffic_lights` et dans `data/interim/traffic_lights`. Le détecteur de `data/processed/traffic_lights` reste à une classe `traffic_light`.

Noms S2TLD, identifiant d'origine :

- 0 : go 0
- 1 : go_left
- 2 : go_right
- 3 : green
- 4 : off
- 5 : off 4
- 6 : red
- 7 : stop 2
- 8 : stop_left
- 9 : wait_on
- 10 : warn 3
- 11 : warn_left
- 12 : yellow

Rouge = 6, vert = 3, jaune = 12. Les autres noms sont des états (go, stop, off, warn), pas une couleur.

Copies dans `data/interim/feux_couleur/` : 4883 labels, 4883 images liées au fichier brut, 0 images copiées. `classes.txt` reprend les 13 noms.

1 211 fichiers n'ont que la classe 0 et un nom à 6 chiffres. Pour ceux-là, la classe 0 n'est pas « go » : aucune couleur n'a été annotée. Elle ne se retrouve pas dans la source, parce qu'elle n'y a jamais été écrite.

## Van et threewheel

Rien n'est réécrit. Les boîtes van (classe 5) et threewheel (classe 1) ont été retirées des labels de `data/processed/vehicles` lors du découpage.

- Images gardées : 2061.
- Parmi elles, images qui avaient des boîtes van : 32, soit 35 boîtes. Ces boîtes ne sont plus dans le label : elles deviennent du fond.
- Parmi elles, images qui avaient des boîtes threewheel : 61, soit 91 boîtes. Elles deviennent du fond elles aussi.
- Images laissées hors du jeu parce qu'elles ne contenaient que ces classes : 939. Leurs boîtes van : 513. Leurs boîtes threewheel : 618. Elles sont dans `data/raw/vehicles_exclus/`.

Proposition, non appliquée : `van` → `car` dans les labels des images gardées, `threewheel` reste exclu. Les boîtes threewheel des images gardées resteraient alors du fond.

## Images sans feu

- Labels vides dans les jeux bruts : 3, tous dans traffic_lights. Aucune image sans feu dans vehicles ni plates_detection : ces photos n'ont pas d'annotation de feu, donc elles ne peuvent pas servir de négatif vérifié.
- Après le regroupement des feux : train 0, val 2, test 1.
- Il n'existe pas d'autre image sans feu. Rien n'a été ajouté, et rien n'a été retiré.
- La proportion de train est 0. La recopier sur val et test retirerait les 3 seules images sans feu, alors que la demande est d'en avoir dans val et test. Elles y sont. Train n'en a plus, parce que ces 3 images ne font pas partie du grand groupe de quasi-doublons.

Planche des 3 images au label vide : `reports/contact_negatifs.jpg`.

## GPU

`torch 2.11.0+cpu`. `torch.cuda.is_available()` est faux, `torch.version.cuda` est vide. Pas de GPU utilisable ici. Le notebook `notebooks/train_colab.ipynb` est écrit et n'a pas été exécuté. Aucun entraînement.

