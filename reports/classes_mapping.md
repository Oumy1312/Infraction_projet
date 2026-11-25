# Mapping des classes véhicules

- Généré : 2026-11-24 16:54
- Rien n'est supprimé de `data/raw/vehicles`.
- Choix appliqué par défaut : `van` exclu, `threewheel` exclu.
- Les images qui contiennent ces classes sont copiées dans `data/raw/vehicles_exclus/<classe>/` avec un label réduit à ces boîtes.
- Une image qui contient aussi une voiture, un bus, un camion ou une moto reste dans le jeu d'entraînement, sans les boîtes exclues.

## classes.txt

```
car
threewheel
bus
truck
motorbike
van
```

- Correspond au jeu attendu (car, threewheel, bus, truck, motorbike, van) : oui.

## Effectifs d'origine

| Identifiant | Nom d'origine | Boîtes | Décision | Identifiant cible |
| --- | --- | --- | --- | --- |
| 0 | car | 662 | gardé | 0 car |
| 1 | threewheel | 709 | exclu | — |
| 2 | bus | 588 | gardé | 1 bus |
| 3 | truck | 629 | gardé | 2 truck |
| 4 | motorbike | 699 | gardé | 3 motorcycle |
| 5 | van | 548 | exclu | — |

## Images qui contiennent la classe

Comptage sur `data/raw/vehicles`, une image peut compter dans plusieurs classes.

| Classe | Images | Boîtes |
| --- | --- | --- |
| car | 590 | 662 |
| threewheel | 519 | 709 |
| bus | 504 | 588 |
| truck | 504 | 629 |
| motorbike | 538 | 699 |
| van | 515 | 548 |

Résultat surprenant : aucune classe n'est rare. Les six classes occupent chacune environ 500 images sur 3 000. Le déséquilibre motos/bus annoncé pour l'entraînement ne se voit pas dans ce jeu. Le point faible attendu est la taille des motos, pas leur nombre. Pas de rééchantillonnage proposé sur cette base.

## Pourquoi ce défaut

Les classes cibles demandées sont car, bus, truck et motorcycle. `motorbike` est renommé `motorcycle` pour coller à ce vocabulaire. `van` et `threewheel` n'ont pas de classe cible : les fusionner dans car ou truck changerait le sens des boîtes. Ils sont donc mis à part.

Autre choix possible, non appliqué : fusionner `van` dans `truck` ou dans `car`. Le dire explicitement pour changer le défaut.

## Copies d'exclusion

- Fichiers label threewheel copiés : 519.
- Fichiers label van copiés : 515.
- Nouveaux labels écrits : {'threewheel': 519, 'van': 515}.

Les feux S2TLD et les feux de classe 0 seule seront, au découpage, une seule classe `traffic_light`. Le détecteur localise le feu ; la couleur rouge, orange ou vert est décidée ensuite par HSV, pas par ces identifiants. Les labels d'origine dans `data/raw` gardent leurs classes.

Les plaques restent la classe 0, nommée `plate`, dans leur propre `data.yaml`.

Fichier machine : `configs/classes_vehicles.yaml`.

