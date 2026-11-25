# Copie selon la règle validée

- Généré : 2026-11-24 16:52
- Mode : apply.
- Source non modifiée. quarantine/ non touché. Aucun poids ouvert.
- Règle : préfixe de 6 chiffres → feu, sinon plaque. Contrôle : médiane l/h > 0,70 → plaque, sinon feu. Désaccord → `_incertains`.
- Fichiers mixtes : séparation ligne par ligne au seuil 0,70. Original dans `data/raw/_originaux/mixtes`.

## Décisions fichier

- Feux déjà identifiés (y compris images négatives) : 3672.
- _a_trier vers traffic_lights : 1211.
- _a_trier vers plates_detection : 417.
- _a_trier vers _incertains : 0.
- Fichiers mixtes séparés : 3.
- Images dataset/ : 1596. Labels dataset/ : 1596.

## Statuts

- copié : 13801
- label dérivé écrit : 3

## Fichiers par destination

- _originaux / image : 3
- _originaux / label : 3
- plates_detection / image : 2016
- plates_detection / label : 2016
- traffic_lights / image : 4883
- traffic_lights / label : 4883

## Contrôle dataset/

- Fichiers label de dataset/ : 1596.
- obj.names : license_plate.
- Identifiants de classe : {0: 1596}.
- Contrôle : la classe 0 de dataset/ est la plaque. Les labels sont copiés sans changer l'identifiant.

## Fichiers mixtes

- train/labels/Trafic-routier-Maroc-Autoroute_jpg.rf.f3531ea6d7cac31e0e7808fc36dba5f8.txt → plates_detection 2
- train/labels/une-scene-de-rue-dans-la-ville-de-casablanca-au-maroc-2c9e9mf_jpg.rf.ef9cc1e74fd8f5e228e53a8020bfedc7.txt → plates_detection 10
- test/labels/28773537_jpg.rf.e69fe97027df8201b1902a2ea7aa3fa6.txt → plates_detection 2

## Divergences préfixe / ratio

- Aucune divergence. Le préfixe et le rapport 0,70 donnent le même groupe pour chaque fichier non mixte.

## Poids source (non ouvert)

- Avant : 256015980 octets, mtime 2026-11-04T23:50:35Z
- Après : 256015980 octets, mtime 2026-11-04T23:50:35Z
- Inchangé : oui.

Journal : `reports/copie_journal.csv`.

