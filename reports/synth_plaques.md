# Plaques synthétiques

- Généré : 2026-11-25 21:47
- Nombre : 20000. Graine : 42. Dossier : `data/synthetic/plaques/`.
- Le texte de chaque plaque est tiré de `configs/plaque_format.yaml`. Toutes les valeurs y sont À VALIDER.
- Le cyclomoteur est `non_decrit` : aucune plaque de ce type n'est générée.
- Part tenue à part : un index sur dix (`eval`), le reste `train`.
- Plaques dont la segmentation retrouve exactement le nombre de caractères posés : 10554/20000 (52.8 %).
- Ces caractères segmentés, et seulement ceux-là, sont dans `chars_train.npz` et `chars_eval.npz`.
- Altérations : fond clair sali, rayures, bruit, flou, luminosité, rotation, perspective, compression JPEG.
- Planche : `reports/planche_plaques_synthetiques.jpg`. Polices : `reports/polices.md`.
