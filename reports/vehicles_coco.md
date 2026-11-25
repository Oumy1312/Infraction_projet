# COCO 2017 filtré — non téléchargé

- Généré : 2026-11-24 18:58
- FiftyOne 1.22.1 est installé. Le script `scripts/04_coco_vehicles.py` est prêt : 4 800 images train et 1 200 validation, graine 42, classes car, bus, truck, motorcycle, export YOLO dans `data/raw/vehicles_coco/`.
- Le téléchargement a été lancé, puis arrêté. L'archive `annotations_trainval2017.zip` (environ 241 Mo, indispensable avant de choisir les images) arrivait à environ 13 Ko/s par FiftyOne, et à environ 5 Ko/s par un essai direct vers `http://images.cocodataset.org`. À ce débit, l'archive seule prendrait plusieurs heures, avant les 6 000 images.
- Aucune image n'a été exportée. Il n'y a donc pas de nombre d'annotations ni de distribution de tailles à comparer aux véhicules actuels.
- Le dossier `data/raw/vehicles_coco/` a été retiré : il ne contenait qu'une archive partielle. Rien n'a été mélangé à `data/processed/vehicles`.
- HTTPS vers ce site échoue (certificat). Aucun contournement de certificat n'a été utilisé.
