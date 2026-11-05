# Rapport de réorganisation

- Source : `C:\Users\user\Desktop\Infraction`
- Mode : apply (only: originaux, polygone, quarantine, vehicles)
- Généré : 2026-11-05 11:44
- Le dossier source n'est pas modifié. Les copies n'ont lieu qu'avec `--apply`.
- Un fichier déjà présent à destination est ignoré.

- Sélection `--only` : originaux, polygone, quarantine, vehicles.
- Les polygones purs vont dans leur dossier prévu sous `data/raw/_a_trier/`.
- Les boîtes de classe 0 et les fichiers mixtes de `_a_trier` ne sont pas copiés.
- `traffic_lights`, `plates_detection` et `plates_chars` ne sont pas copiés par cette sélection.

## Volumes d'images prévus

| Destination | Images |
| --- | --- |
| _a_trier | 1631 |
| plates_detection | 1596 |
| quarantine | 1 |
| traffic_lights | 3672 |
| vehicles | 3000 |

## Statuts

| Statut | Fichiers |
| --- | --- |
| copié | 6619 |
| hors sélection, non copié | 13188 |

## Images négatives

Les labels vides du split train sont conservés avec les feux (images négatives).

- `train/labels/2020-03-30-11_39_03-883268374_jpg.rf.875502c3c0262a166610459ab99ee509.txt` — image `2020-03-30-11_39_03-883268374_jpg.rf.875502c3c0262a166610459ab99ee509.jpg` — motif `_jpg.rf.` : oui
- `train/labels/2020-03-30-11_44_51-161684229_jpg.rf.2ae62164d774dcdc594c72d0851e935a.txt` — image `2020-03-30-11_44_51-161684229_jpg.rf.2ae62164d774dcdc594c72d0851e935a.jpg` — motif `_jpg.rf.` : oui
- `train/labels/2020-03-30-12_02_12-042615407_jpg.rf.9ce7d385abf32192baa6718e859799c7.txt` — image `2020-03-30-12_02_12-042615407_jpg.rf.9ce7d385abf32192baa6718e859799c7.jpg` — motif `_jpg.rf.` : oui

## Polygones

- Fichiers contenant au moins un polygone : 308
- Lignes de polygone : 320
- Aucune conversion en rectangle n'a été faite. Les fichiers sont copiés tels quels dans `data/raw/_a_trier/`.

## Classe 0 laissée à trier

- Fichiers d'annotation : 1631
- Indice roboflow lu dans les YAML, non utilisé pour choisir le dataset : data (2).yaml=aucun ; data.yaml=s2tld
- Le motif `_jpg.rf.` est noté dans `reports/a_trier.csv` et sur les planches.

Planches contact :

- `reports/contact_test__bbox_classe0__rf.jpg`
- `reports/contact_test__mixte__rf.jpg`
- `reports/contact_test__polygone__rf.jpg`
- `reports/contact_train__bbox_classe0__rf.jpg`
- `reports/contact_train__bbox_classe0__sans_rf.jpg`
- `reports/contact_train__mixte__rf.jpg`
- `reports/contact_train__polygone__rf.jpg`
- `reports/contact_train__polygone__sans_rf.jpg`
- `reports/contact_valid__bbox_classe0__rf.jpg`
- `reports/contact_valid__polygone__rf.jpg`
- `reports/contact_valid__polygone__sans_rf.jpg`

## Inventaire source (résumé)

| Dossier | Split | Images | Labels | Sans label | Sans image | Doublons |
| --- | --- | --- | --- | --- | --- | --- |
| dataset | (racine) | 1596 | 1596 | 0 | 0 | 0 |
| test | test | 42 | 42 | 0 | 0 | 0 |
| test_img | (racine) | 1 | 0 | 1 | 0 | 0 |
| train | train | 5177 | 5177 | 0 | 0 | 0 |
| valid | valid | 84 | 84 | 0 | 0 | 0 |
| vehicle dataset | train | 2100 | 2100 | 0 | 0 | 0 |
| vehicle dataset | valid | 900 | 900 | 0 | 0 | 0 |

Le détail des noms en doublon est dans `reports/inventaire_splits.md`.

