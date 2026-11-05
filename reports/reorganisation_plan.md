# Plan de réorganisation (dry-run)

- Source : `C:\Users\user\Desktop\Infraction`
- Généré : 2026-11-05 01:18
- Script : `scripts/00_analyze_mess.py`
- Mode : analyse seule. Aucun fichier de la source n'a été copié, déplacé, modifié ou supprimé.
- Les dossiers `data/raw/...` du projet restent vides. Ce document est une proposition à valider avant toute copie.
- Volume parcouru : 19807 fichiers, 9900 images, 9899 annotations, 1.1 Go.
- Une annotation compte un `.txt`, `.xml` ou `.json` de boîtes. `classes.txt`, `obj.names`, `obj.data` et les README sont comptés à part.

## a. Inventaire du premier niveau

| Élément | Type | Images | Annotations | Extensions | Taille |
| --- | --- | --- | --- | --- | --- |
| dataset | dossier | 1596 | 1596 | .txt (1596), .jpg (1594), .jpeg (2) | 168.3 Mo |
| test | dossier | 42 | 42 | .jpg (42), .txt (42) | 2.3 Mo |
| test_img | dossier | 1 | 0 | .jpg (1) | 38.0 Ko |
| train | dossier | 5177 | 5177 | .jpg (5177), .txt (5177) | 312.6 Mo |
| valid | dossier | 84 | 84 | .jpg (84), .txt (84) | 4.5 Mo |
| vehicle dataset | dossier | 3000 | 3000 | .txt (3001), .jpg (2084), .jpeg (861), .png (55) | 380.1 Mo |
| data (2).yaml | fichier | 0 | 0 | .yaml | 88 o |
| data.yaml | fichier | 0 | 0 | .yaml | 362 o |
| obj.names | fichier | 0 | 0 | .names | 14 o |
| README.dataset.txt | fichier | 0 | 0 | .txt | 125 o |
| README.roboflow.txt | fichier | 0 | 0 | .txt | 977 o |
| yolov4-obj.cfg | fichier | 0 | 0 | .cfg | 12.0 Ko |
| yolov4-obj.weights | fichier | 0 | 0 | .weights | 244.2 Mo |
| TOTAL |  | 9900 | 9899 | .txt (9902), .jpg (8982), .jpeg (863), .png (55), .yaml (2), .cfg (1), .names (1), .weights (1) | 1.1 Go |

### Dossiers qui contiennent directement les fichiers

| Dossier | Images directes | Annotations directes | Extensions (tout le sous-arbre) | Taille du sous-arbre |
| --- | --- | --- | --- | --- |
| dataset/dataset | 1596 | 1596 | .txt (1596), .jpg (1594), .jpeg (2) | 168.3 Mo |
| test/images | 42 | 0 | .jpg (42) | 2.3 Mo |
| test/labels | 0 | 42 | .txt (42) | 6.0 Ko |
| test_img | 1 | 0 | .jpg (1) | 38.0 Ko |
| train/images | 5177 | 0 | .jpg (5177) | 312.1 Mo |
| train/labels | 0 | 5177 | .txt (5177) | 512.5 Ko |
| valid/images | 84 | 0 | .jpg (84) | 4.5 Mo |
| valid/labels | 0 | 84 | .txt (84) | 10.7 Ko |
| vehicle dataset/train/images | 2100 | 0 | .jpg (1435), .jpeg (622), .png (43) | 271.9 Mo |
| vehicle dataset/train/labels | 0 | 2100 | .txt (2100) | 99.6 Ko |
| vehicle dataset/valid/images | 900 | 0 | .jpg (649), .jpeg (239), .png (12) | 108.0 Mo |
| vehicle dataset/valid/labels | 0 | 900 | .txt (900) | 42.7 Ko |

## b. Fichiers de classes

### data (2).yaml

- Type : yaml
- Nombre de classes : 1
- Noms : plate
- Lecture des noms : plates_detection=5. une seule classe de plaque : plate

| Clé | Déclaré | Interprétation | Chemin résolu | Existe | Emplacement |
| --- | --- | --- | --- | --- | --- |
| train | ../train/images | relatif au fichier qui le déclare | C:\Users\user\Desktop\train\images | non | hors de la source |
| train | ../train/images | préfixe « .. » retiré, depuis le dossier du fichier | C:\Users\user\Desktop\Infraction\train\images | oui | dans la source |
| val | ../valid/images | relatif au fichier qui le déclare | C:\Users\user\Desktop\valid\images | non | hors de la source |
| val | ../valid/images | préfixe « .. » retiré, depuis le dossier du fichier | C:\Users\user\Desktop\Infraction\valid\images | oui | dans la source |
| test | ../test/images | relatif au fichier qui le déclare | C:\Users\user\Desktop\test\images | non | hors de la source |
| test | ../test/images | préfixe « .. » retiré, depuis le dossier du fichier | C:\Users\user\Desktop\Infraction\test\images | oui | dans la source |

### data.yaml

- Type : yaml
- Nombre de classes : 13
- workspace : hellosongdo
- project : s2tld
- version : 1
- license : CC BY 4.0
- url : https://universe.roboflow.com/hellosongdo/s2tld/dataset/1
- Noms : go 0, go_left, go_right, green, off, off 4, red, stop 2, stop_left, wait_on, warn 3, warn_left, yellow
- Lecture des noms : traffic_lights=9. couleurs de feux : green, red, yellow états de feux : go, off, stop, wait, wait_on, warn

| Clé | Déclaré | Interprétation | Chemin résolu | Existe | Emplacement |
| --- | --- | --- | --- | --- | --- |
| train | ../train/images | relatif au fichier qui le déclare | C:\Users\user\Desktop\train\images | non | hors de la source |
| train | ../train/images | préfixe « .. » retiré, depuis le dossier du fichier | C:\Users\user\Desktop\Infraction\train\images | oui | dans la source |
| val | ../valid/images | relatif au fichier qui le déclare | C:\Users\user\Desktop\valid\images | non | hors de la source |
| val | ../valid/images | préfixe « .. » retiré, depuis le dossier du fichier | C:\Users\user\Desktop\Infraction\valid\images | oui | dans la source |
| test | ../test/images | relatif au fichier qui le déclare | C:\Users\user\Desktop\test\images | non | hors de la source |
| test | ../test/images | préfixe « .. » retiré, depuis le dossier du fichier | C:\Users\user\Desktop\Infraction\test\images | oui | dans la source |

### obj.names

- Type : names
- Nombre de classes : 1
- Noms : license_plate
- Lecture des noms : plates_detection=5. une seule classe de plaque : license_plate

Ce fichier ne déclare pas de chemin train/val/test.

### vehicle dataset/classes.txt

- Type : names
- Nombre de classes : 6
- Noms : car, threewheel, bus, truck, motorbike, van
- Lecture des noms : vehicles=9. classes de véhicules : bus, car, motorbike, threewheel, truck, van

Ce fichier ne déclare pas de chemin train/val/test.

## Documentation lue

### README.dataset.txt

- # s2tld > 2024-03-21 7:24pm
- https://universe.roboflow.com/hellosongdo/s2tld
- License: CC BY 4.0

### README.roboflow.txt

- s2tld - v1 2024-03-21 7:24pm
- ==============================
- visit https://github.com/roboflow/notebooks
- The dataset includes 4883 images.
- Dd are annotated in YOLOv8 format.
- The following pre-processing was applied to each image:
- No image augmentation techniques were applied.

Le README annonce 4883 images. Les dossiers d'images locaux visés par le YAML s2tld en contiennent 5303 (test/images, train/images, valid/images).

## c. Format d'annotation

Le format est déduit en lisant les annotations, pas seulement leur extension. YOLO et Darknet partagent le rectangle normalisé `classe x y largeur hauteur`. Le dossier est appelé Darknet quand l'image et le `.txt` sont côte à côte, et Ultralytics quand `images/` et `labels/` sont séparés.

### dataset/dataset

- Organisation : Darknet : images et annotations dans le même dossier
- Dossier d'images associé : `dataset/dataset` (1596 images)
- Images sans annotation : 0
- Échantillon Pillow :
  - IMG-20200725-WA0000.jpg : JPEG 720×1280 RGB
  - IMG-20200725-WA0001.jpg : JPEG 720×1280 RGB
  - IMG-20200725-WA0002.jpg : JPEG 720×1280 RGB

**Darknet — YOLO txt normalisé (rectangle classe x y largeur hauteur)**

- Fichiers : 1596
- Boîtes ou polygones : 1596
- Images liées par le nom : 1596
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×1596
- Noms de fichiers : autre (997), WhatsApp (WA) (599)
- Exemples : IMG-20200725-WA0000.txt, IMG-20200725-WA0001.txt, IMG-20200725-WA0002.txt, IMG-20200725-WA0004.txt, IMG-20200725-WA0037.txt
- Première ligne lue : `0 0.866667 0.557813 0.225000 0.104688`

### test/labels

- Organisation : Ultralytics : dossiers images/ et labels/ séparés
- Dossier d'images associé : `test/images` (42 images)
- Images sans annotation : 0
- Échantillon Pillow :
  - 28137980_jpg.rf.b81b74d77acb4be9502a5cf77fe3b85a.jpg : JPEG 640×640 RGB
  - 28138008_jpg.rf.9ef3e189795b0b86f0e46e4cbd990095.jpg : JPEG 640×640 RGB
  - 28139190_jpg.rf.ab802e61442eacba423293138e12ac91.jpg : JPEG 640×640 RGB

**YOLO Ultralytics — YOLO txt normalisé (rectangle classe x y largeur hauteur)**

- Fichiers : 8
- Boîtes ou polygones : 8
- Images liées par le nom : 8
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×8
- Noms de fichiers : Roboflow (.rf.) (8)
- Exemples : 28139190_jpg.rf.ab802e61442eacba423293138e12ac91.txt, 28187580_jpg.rf.552c741313bbb45b76f5a2360bd29834.txt, 28552578_jpg.rf.ae24740bada2ae0a4685af85ad1de534.txt, 28679267_jpg.rf.787b956aa69b101904a6576b8db31d7c.txt, 28694641_jpg.rf.023a96fc375250f78e0df4446af439f8.txt
- Première ligne lue : `0 0.32578125 0.6859375 0.13671875 0.040625`

**rectangle et polygone dans le même fichier**

- Fichiers : 1
- Boîtes ou polygones : 2
- Images liées par le nom : 1
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×2
- Noms de fichiers : Roboflow (.rf.) (1)
- Exemples : 28773537_jpg.rf.e69fe97027df8201b1902a2ea7aa3fa6.txt
- Première ligne lue : `0 0.93203125 0.24609375 0.0828125 0.01796875`

**YOLO polygone normalisé (classe + paires x y)**

- Fichiers : 33
- Boîtes ou polygones : 34
- Images liées par le nom : 33
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×34
- Noms de fichiers : Roboflow (.rf.) (33)
- Exemples : 28137980_jpg.rf.b81b74d77acb4be9502a5cf77fe3b85a.txt, 28138008_jpg.rf.9ef3e189795b0b86f0e46e4cbd990095.txt, 28139244_jpg.rf.040f7f01efc7e365b33be50a2289c71f.txt, 28139586_jpg.rf.6db5ebe7455601e53a04b49965bed281.txt, 28161463_jpg.rf.21489864e6315da462cd7b035fc4b368.txt
- Première ligne lue : `0 0.3620548609375 0.6908055562500001 0.21051944374999998 0.6842731484375 0.2061791671875 0.72476851875 0.3593541671875 0.7342888890625 0.3620548609375 0.6908055562500001`

### train/labels

- Organisation : Ultralytics : dossiers images/ et labels/ séparés
- Dossier d'images associé : `train/images` (5177 images)
- Images sans annotation : 0
- Échantillon Pillow :
  - 000000_jpg.rf.ff1da1cf4f1c3988c422fbe99ff15fb5.jpg : JPEG 640×640 RGB
  - 000001_jpg.rf.1d352407fc565c111b06f79c6347d26b.jpg : JPEG 640×640 RGB
  - 000002_jpg.rf.fc9583ad3e9dbe03dad95dd09b769214.jpg : JPEG 640×640 RGB

**fichier txt vide**

- Fichiers : 3
- Boîtes ou polygones : 0
- Images liées par le nom : 3
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : aucune
- Noms de fichiers : Roboflow (.rf.) (3)
- Exemples : 2020-03-30-11_39_03-883268374_jpg.rf.875502c3c0262a166610459ab99ee509.txt, 2020-03-30-11_44_51-161684229_jpg.rf.2ae62164d774dcdc594c72d0851e935a.txt, 2020-03-30-12_02_12-042615407_jpg.rf.9ce7d385abf32192baa6718e859799c7.txt

**YOLO Ultralytics — YOLO txt normalisé (rectangle classe x y largeur hauteur)**

- Fichiers : 4959
- Boîtes ou polygones : 11860
- Images liées par le nom : 4959
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×3606, 1×263, 2×14, 3×648, 4×3, 5×501, 6×690, 7×4390, 8×1283, 9×247, 10×131, 11×26, 12×58
- Noms de fichiers : Roboflow (.rf.) (4959)
- Exemples : 000000_jpg.rf.ff1da1cf4f1c3988c422fbe99ff15fb5.txt, 000001_jpg.rf.1d352407fc565c111b06f79c6347d26b.txt, 000002_jpg.rf.fc9583ad3e9dbe03dad95dd09b769214.txt, 000003_jpg.rf.16c4fb5281592a3807fc6f5ded6d22e1.txt, 000004_jpg.rf.c4824c171dde7688056cb5b91305ef44.txt
- Première ligne lue : `8 0.159375 0.21484375 0.02109375 0.07890625`

**rectangle et polygone dans le même fichier**

- Fichiers : 2
- Boîtes ou polygones : 12
- Images liées par le nom : 2
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×12
- Noms de fichiers : Roboflow (.rf.) (2)
- Exemples : Trafic-routier-Maroc-Autoroute_jpg.rf.f3531ea6d7cac31e0e7808fc36dba5f8.txt, une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt
- Première ligne lue : `0 0.34375 0.815625 0.0671875 0.02890625`

**YOLO polygone normalisé (classe + paires x y)**

- Fichiers : 213
- Boîtes ou polygones : 220
- Images liées par le nom : 213
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×220
- Noms de fichiers : Roboflow (.rf.) (213)
- Exemples : 28137646_jpg.rf.4a0295f9025e0eec63b2a703f97cebff.txt, 28137661_jpg.rf.fb0f304badd0ac1371ea5e840c175831.txt, 28137667_jpg.rf.fd6f5d1b5a0c4a6ee8f3b08bc3372991.txt, 28137725_jpg.rf.5e1ede87a0838f8e71a33975343381b1.txt, 28137753_jpg.rf.79a8cc9dadb0237a548ccbe86f25d8c7.txt
- Première ligne lue : `0 0.377425 0.757203703125 0.23413611093750003 0.7550740734375 0.235034028125 0.790752778125 0.3767513890625 0.794647221875 0.377425 0.757203703125`

### valid/labels

- Organisation : Ultralytics : dossiers images/ et labels/ séparés
- Dossier d'images associé : `valid/images` (84 images)
- Images sans annotation : 0
- Échantillon Pillow :
  - 28137703_jpg.rf.fa4c6acefc37be030521a7428896e060.jpg : JPEG 640×640 RGB
  - 28137973_jpg.rf.42c7ef8f798e24b58032c548df276b3b.jpg : JPEG 640×640 RGB
  - 28139057_jpg.rf.6194b4725e24326369a924aa87b0e862.jpg : JPEG 640×640 RGB

**YOLO Ultralytics — YOLO txt normalisé (rectangle classe x y largeur hauteur)**

- Fichiers : 25
- Boîtes ou polygones : 25
- Images liées par le nom : 25
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×25
- Noms de fichiers : Roboflow (.rf.) (25)
- Exemples : 28137973_jpg.rf.42c7ef8f798e24b58032c548df276b3b.txt, 28164815_jpg.rf.8f529e1454051ab0023e4848323b2d4c.txt, 28171260_jpg.rf.22a9a255ec529b6b388f4a063f4f8699.txt, 28408350_jpg.rf.8dee5a7cc3f7056328b917dce5128932.txt, 28459160_jpg.rf.a86fb82492e8e46ca4a50cf967f46336.txt
- Première ligne lue : `0 0.3515625 0.72578125 0.15234375 0.04609375`

**YOLO polygone normalisé (classe + paires x y)**

- Fichiers : 59
- Boîtes ou polygones : 61
- Images liées par le nom : 59
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×61
- Noms de fichiers : Roboflow (.rf.) (59)
- Exemples : 28137703_jpg.rf.fa4c6acefc37be030521a7428896e060.txt, 28139057_jpg.rf.6194b4725e24326369a924aa87b0e862.txt, 28139107_jpg.rf.7f55f6e3ff6a31fe61a199d767dff564.txt, 28140016_jpg.rf.1d95f35d786872d0c7643f3dd2be52d9.txt, 28160996_jpg.rf.f818ea24e942761a0f171020a0d95365.txt
- Première ligne lue : `0 0.515090909375 0.596506346875 0.328655390625 0.5990634703125 0.3239735734375 0.6484880109375 0.51338795 0.650760225 0.515090909375 0.596506346875`

### vehicle dataset/train/labels

- Organisation : Ultralytics : dossiers images/ et labels/ séparés
- Dossier d'images associé : `vehicle dataset/train/images` (2100 images)
- Images sans annotation : 0
- Échantillon Pillow :
  - 00043_GMC Savana Van 2012.jpg : JPEG 596×417 RGB
  - 00077.jpg : JPEG 3552×2153 RGB
  - 00116.jpg : JPEG 786×492 RGB

**YOLO Ultralytics — YOLO txt normalisé (rectangle classe x y largeur hauteur)**

- Fichiers : 2100
- Boîtes ou polygones : 2685
- Images liées par le nom : 2100
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×461, 1×482, 2×403, 3×478, 4×483, 5×378
- Noms de fichiers : autre (2100)
- Exemples : 00043_GMC Savana Van 2012.txt, 00077.txt, 00116.txt, 00175_Ford E-Series Wagon Van 2012.txt, 00241.txt
- Première ligne lue : `5 0.499161 0.503597 0.971477 0.767386`

### vehicle dataset/valid/labels

- Organisation : Ultralytics : dossiers images/ et labels/ séparés
- Dossier d'images associé : `vehicle dataset/valid/images` (900 images)
- Images sans annotation : 0
- Échantillon Pillow :
  - 00110.jpg : JPEG 773×573 RGB
  - 00262.jpg : JPEG 600×427 RGB
  - 00790.jpg : JPEG 750×469 RGB

**YOLO Ultralytics — YOLO txt normalisé (rectangle classe x y largeur hauteur)**

- Fichiers : 900
- Boîtes ou polygones : 1150
- Images liées par le nom : 900
- Annotations sans image : 0
- Ids de classes (id × nombre de boîtes) : 0×201, 1×227, 2×185, 3×151, 4×216, 5×170
- Noms de fichiers : autre (900)
- Exemples : 00110.txt, 00262.txt, 00790.txt, 00826.txt, 01000_GMC Savana Van 2012.txt
- Première ligne lue : `0 0.507115 0.527051 0.910737 0.851658`

## d. Proposition d'affectation

Destinations prévues, encore vides : `data/raw/vehicles`, `data/raw/traffic_lights`, `data/raw/plates_detection`, `data/raw/plates_chars`. La valeur `incertain` signifie qu'il faut votre réponse avant de copier.

| Dossier | Verdict | Confiance | Fichiers d'annotation |
| --- | --- | --- | --- |
| dataset | plates_detection — copier le dossier entier vers data/raw/plates_detection/ | haute | 1596 |
| test | incertain | faible | 42 |
| test_img | incertain — images sans annotation | faible | 0 |
| train | mélange — copier selon les sous-groupes, pas le dossier entier | voir sous-groupes | 5177 |
| valid | incertain | faible | 84 |
| vehicle dataset | vehicles — copier le dossier entier vers data/raw/vehicles/ | haute | 3000 |

### Sous-groupes

| Dossier | Format | Annotations | Images | Dataset | Confiance | Destination proposée |
| --- | --- | --- | --- | --- | --- | --- |
| dataset/dataset | YOLO txt normalisé (rectangle classe x y largeur hauteur) | 1596 | 1596 | plates_detection | haute | data/raw/plates_detection/ (dossier entier) |
| test/labels | YOLO txt normalisé (rectangle classe x y largeur hauteur) | 8 | 8 | incertain | faible | en attente de votre réponse |
| test/labels | rectangle et polygone dans le même fichier | 1 | 1 | incertain | faible | en attente de votre réponse |
| test/labels | YOLO polygone normalisé (classe + paires x y) | 33 | 33 | incertain | faible | en attente de votre réponse |
| train/labels | fichier txt vide | 3 | 3 | incertain | faible | en attente de votre réponse |
| train/labels | YOLO txt normalisé (rectangle classe x y largeur hauteur) | 4959 | 4959 | traffic_lights | haute | data/raw/traffic_lights/ (ces fichiers seulement) |
| train/labels | rectangle et polygone dans le même fichier | 2 | 2 | incertain | faible | en attente de votre réponse |
| train/labels | YOLO polygone normalisé (classe + paires x y) | 213 | 213 | incertain | faible | en attente de votre réponse |
| valid/labels | YOLO txt normalisé (rectangle classe x y largeur hauteur) | 25 | 25 | incertain | faible | en attente de votre réponse |
| valid/labels | YOLO polygone normalisé (classe + paires x y) | 59 | 59 | incertain | faible | en attente de votre réponse |
| vehicle dataset/train/labels | YOLO txt normalisé (rectangle classe x y largeur hauteur) | 2100 | 2100 | vehicles | haute | data/raw/vehicles/ (dossier entier) |
| vehicle dataset/valid/labels | YOLO txt normalisé (rectangle classe x y largeur hauteur) | 900 | 900 | vehicles | haute | data/raw/vehicles/ (dossier entier) |
| test_img | image sans annotation | 0 | 1 | incertain | faible | en attente de votre réponse |

### Justification

**dataset/dataset — YOLO txt normalisé (rectangle classe x y largeur hauteur)** → `plates_detection` (haute)

- obj.names couvre les ids observés (0=license_plate).
- une seule classe de plaque : license_plate
- indices chiffrés : plates_detection=5

**test/labels — YOLO txt normalisé (rectangle classe x y largeur hauteur)** → `incertain` (faible)

- data (2).yaml couvre les ids observés (0=plate).
- data.yaml : la classe 0 vaut « go 0 », mais le fichier décrit 13 classes et ces annotations n'utilisent que la classe 0.
- Plusieurs fichiers de classes peuvent revendiquer la classe 0. Pas d'affectation automatique.

**test/labels — rectangle et polygone dans le même fichier** → `incertain` (faible)

- data (2).yaml couvre les ids observés (0=plate).
- data.yaml : la classe 0 vaut « go 0 », mais le fichier décrit 13 classes et ces annotations n'utilisent que la classe 0.
- Plusieurs fichiers de classes peuvent revendiquer la classe 0. Pas d'affectation automatique.

**test/labels — YOLO polygone normalisé (classe + paires x y)** → `incertain` (faible)

- data (2).yaml couvre les ids observés (0=plate).
- data.yaml : la classe 0 vaut « go 0 », mais le fichier décrit 13 classes et ces annotations n'utilisent que la classe 0.
- Plusieurs fichiers de classes peuvent revendiquer la classe 0. Pas d'affectation automatique.

**train/labels — fichier txt vide** → `incertain` (faible)

- Format : fichier txt vide.
- Ces fichiers ne sont pas affectés automatiquement.

**train/labels — YOLO txt normalisé (rectangle classe x y largeur hauteur)** → `traffic_lights` (haute)

- data (2).yaml (1 classe, hypothèse plates_detection) ne couvre pas ces ids (8254 boîtes hors plage).
- data.yaml couvre les ids observés (0=go 0, 1=go_left, 2=go_right, 3=green, 4=off, 5=off 4, 6=red, 7=stop 2, 8=stop_left, 9=wait_on, 10=warn 3, 11=warn_left, 12=yellow).
- couleurs de feux : green, red, yellow
- états de feux : go, off, stop, wait, wait_on, warn
- le README cite le projet s2tld, le même que ce fichier YAML
- indices chiffrés : traffic_lights=11

**train/labels — rectangle et polygone dans le même fichier** → `incertain` (faible)

- data (2).yaml couvre les ids observés (0=plate).
- data.yaml : la classe 0 vaut « go 0 », mais le fichier décrit 13 classes et ces annotations n'utilisent que la classe 0.
- Plusieurs fichiers de classes peuvent revendiquer la classe 0. Pas d'affectation automatique.

**train/labels — YOLO polygone normalisé (classe + paires x y)** → `incertain` (faible)

- data (2).yaml couvre les ids observés (0=plate).
- data.yaml : la classe 0 vaut « go 0 », mais le fichier décrit 13 classes et ces annotations n'utilisent que la classe 0.
- Plusieurs fichiers de classes peuvent revendiquer la classe 0. Pas d'affectation automatique.

**valid/labels — YOLO txt normalisé (rectangle classe x y largeur hauteur)** → `incertain` (faible)

- data (2).yaml couvre les ids observés (0=plate).
- data.yaml : la classe 0 vaut « go 0 », mais le fichier décrit 13 classes et ces annotations n'utilisent que la classe 0.
- Plusieurs fichiers de classes peuvent revendiquer la classe 0. Pas d'affectation automatique.

**valid/labels — YOLO polygone normalisé (classe + paires x y)** → `incertain` (faible)

- data (2).yaml couvre les ids observés (0=plate).
- data.yaml : la classe 0 vaut « go 0 », mais le fichier décrit 13 classes et ces annotations n'utilisent que la classe 0.
- Plusieurs fichiers de classes peuvent revendiquer la classe 0. Pas d'affectation automatique.

**vehicle dataset/train/labels — YOLO txt normalisé (rectangle classe x y largeur hauteur)** → `vehicles` (haute)

- classes.txt couvre les ids observés (0=car, 1=threewheel, 2=bus, 3=truck, 4=motorbike, 5=van).
- classes de véhicules : bus, car, motorbike, threewheel, truck, van
- le chemin du dossier contient « vehicle »
- indices chiffrés : vehicles=13

**vehicle dataset/valid/labels — YOLO txt normalisé (rectangle classe x y largeur hauteur)** → `vehicles` (haute)

- classes.txt couvre les ids observés (0=car, 1=threewheel, 2=bus, 3=truck, 4=motorbike, 5=van).
- classes de véhicules : bus, car, motorbike, threewheel, truck, van
- le chemin du dossier contient « vehicle »
- indices chiffrés : vehicles=13

**test_img** → `incertain` (faible)

- 1 image(s) et aucune annotation.
- Le nom du fichier seul ne suffit pas à choisir un dataset.

## e. Collisions

### Chemins déclarés par plusieurs fichiers de classes

| Clé | Chemin déclaré | Fichiers |
| --- | --- | --- |
| test | ../test/images | data (2).yaml, data.yaml |
| train | ../train/images | data (2).yaml, data.yaml |
| val | ../valid/images | data (2).yaml, data.yaml |

Chemins résolus qui existent et qui sont visés par plusieurs déclarations :

| Chemin | Déclarations |
| --- | --- |
| C:\Users\user\Desktop\Infraction\test\images | data (2).yaml:test, data.yaml:test |
| C:\Users\user\Desktop\Infraction\train\images | data (2).yaml:train, data.yaml:train |
| C:\Users\user\Desktop\Infraction\valid\images | data (2).yaml:val, data.yaml:val |

### Noms d'images identiques entre dossiers de premier niveau

Aucun nom d'image en commun entre des dossiers de premier niveau différents.

### Même nom à l'intérieur d'un dossier de premier niveau

Aucun doublon interne de nom d'image.

## f. Quarantaine

Les fichiers ci-dessous sont des modèles ou des configurations de modèle pré-entraînés. Ils ne doivent pas servir à l'entraînement et ne doivent pas être copiés dans `data/`. Après votre validation, l'étape 2 les copiera dans `quarantine/`.
Les `.weights`, `.pt` et `.onnx` n'ont pas été ouverts : seule la taille sur le disque a été lue.

| Fichier | Taille | Note |
| --- | --- | --- |
| yolov4-obj.cfg | 12.0 Ko | texte de configuration, classes=1, 1, 1. Ce n'est pas un poids, mais c'est un modèle pré-entraîné à mettre en quarantaine et à ne pas utiliser pour l'entraînement. |
| yolov4-obj.weights | 244.2 Mo | contenu non lu (poids pré-entraîné) — quarantaine, ne pas utiliser pour l'entraînement |

## g. Incertain — questions

1. Ces annotations n'utilisent que la classe 0, et plusieurs fichiers de classes peuvent la revendiquer (data (2).yaml : classe 0 = « plate » (1 classe, piste plates_detection); data.yaml : classe 0 = « go 0 » (13 classes, piste traffic_lights)). Doivent-elles aller dans traffic_lights, plates_detection ou plates_chars ?
  - test/labels — YOLO polygone normalisé (classe + paires x y) — 33 fichiers, environ 33 images
  - test/labels — YOLO txt normalisé (rectangle classe x y largeur hauteur) — 8 fichiers, environ 8 images
  - test/labels — rectangle et polygone dans le même fichier — 1 fichiers, environ 1 images
  - train/labels — YOLO polygone normalisé (classe + paires x y) — 213 fichiers, environ 213 images
  - train/labels — rectangle et polygone dans le même fichier — 2 fichiers, environ 2 images
  - valid/labels — YOLO polygone normalisé (classe + paires x y) — 59 fichiers, environ 59 images
  - valid/labels — YOLO txt normalisé (rectangle classe x y largeur hauteur) — 25 fichiers, environ 25 images

2. Que faut-il faire des éléments suivants, qui restent incertains ?
  - train/labels — fichier txt vide — 3 fichiers. Exemples : 2020-03-30-11_39_03-883268374_jpg.rf.875502c3c0262a166610459ab99ee509.txt, 2020-03-30-11_44_51-161684229_jpg.rf.2ae62164d774dcdc594c72d0851e935a.txt, 2020-03-30-12_02_12-042615407_jpg.rf.9ce7d385abf32192baa6718e859799c7.txt
  - test_img — 1 image(s) sans annotation. Exemples : car.jpg

3. Le dataset « Moroccan Vehicle Registration Plates » (plaques / caractères) n'a pas été reconnu : aucune liste de classes du type chiffre ou lettre. Est-il absent de ce dossier, ou correspond-il à l'un des groupes incertains ci-dessus ?

4. Dans les YAML, les chemins du type `../train/images` sortent du dossier source une fois résolus tels quels, et ce dossier externe n'existe pas. En retirant le préfixe `..`, on retombe sur les dossiers locaux train/images, valid/images et test/images. Confirmez-vous que ce sont bien ces dossiers locaux qui sont visés ?

5. Le README s2tld annonce 4883 images, mais les dossiers locaux visés en contiennent 5303. Confirmez-vous que la différence vient d'un autre dataset mélangé dans train/, valid/ ou test/ ?

6. Je propose de copier les fichiers de la racine (data (2).yaml, data.yaml, obj.names, README.dataset.txt, README.roboflow.txt) dans configs/, pas dans data/raw/. vehicle dataset/classes.txt est déjà dans un dossier de données et suivrait ce dossier vers data/raw/. Confirmez-vous cet emplacement pour l'étape 2 ?
