# Datasets

- Mode du dernier passage : apply (only: originaux, polygone, quarantine, vehicles)
- Généré : 2026-11-05 11:44
- Les comptes d'images sont ceux du plan de copie (fichiers prévus, ou copiés si `--apply`).
- La licence est laissée à « à vérifier » tant qu'elle n'a pas été confirmée hors du fichier YAML.
- `data/raw/plates_chars/` n'est pas alimenté : le dataset caractères est considéré absent.

## Vehicle Dataset for YOLO

- Lien : à vérifier (Kaggle)
- Dossier local : `data/raw/vehicles/`
- Classes : car, threewheel, bus, truck, motorbike, van
- Images : 3000
- Licence : à vérifier
- `classes.txt` est copié avec ce dossier.

## S2TLD

- Lien : https://universe.roboflow.com/hellosongdo/s2tld/dataset/1
- Dossier local : `data/raw/traffic_lights/`
- Classes : go 0, go_left, go_right, green, off, off 4, red, stop 2, stop_left, wait_on, warn 3, warn_left, yellow
- Images : 3672 (rectangles avec au moins une classe autre que 0, plus 3 image(s) négative(s))
- Licence : à vérifier
- Le YAML d'origine mentionne CC BY 4.0. Ce n'est pas repris comme licence confirmée.
- Les fichiers qui n'ont que la classe 0 ne sont pas dans ce dossier.

## Moroccan License Plate Detection

- Lien : à vérifier (Kaggle)
- Dossier local : `data/raw/plates_detection/`
- Classes : license_plate
- Images : 1596
- Licence : à vérifier
- Organisation d'origine conservée : image et annotation côte à côte (Darknet).

## Moroccan Vehicle Registration Plates (caractères)

- Lien : à vérifier (Kaggle)
- Dossier local : aucun. Dataset considéré absent tant qu'il n'est pas confirmé.
- Classes : —
- Images : 0
- Licence : à vérifier

## Fichiers laissés à trier

- Dossier local : `data/raw/_a_trier/`
- Images : 1631
- Détail : `reports/a_trier.csv` et `reports/contact_*.jpg`
- Les polygones sont copiés sans conversion.

## Originaux et quarantaine

- YAML, `obj.names` et README : `data/raw/_originaux/`
- Poids, configurations et `test_img/car.jpg` : `quarantine/`
