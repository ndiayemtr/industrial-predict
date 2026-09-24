# 2.2.9 — Qualité et nettoyage des données capteurs

Depuis `backend`, avec Python 3.12, pandas et les dépendances du backend :

```powershell
python -m unittest discover -s ../tests/data_cleaning -t ../tests -v
python -m unittest discover -s ../tests -v
python -m compileall app
```

La suite suit le pattern `unittest` existant. Elle utilise des DataFrames en
mémoire, des dates UTC fixes et les huit composants réels, sans mocks ni base.
Chaque scénario possède des résultats attendus explicites. Les combinaisons de
configuration du cleaner sont également comparées au rapport correspondant.

## Couverture

- Classification good/suspect/estimated/bad/missing, inconnus, normalisation,
  valeurs finies et inf/-inf/nan ; filtrage avec/sans warnings et dataset vide.
- Doublons d'identifiant et de couple capteur/timestamp, absence de collision
  entre capteurs et comptages des groupes de doublons.
- Gaps : cadence régulière, trou, cadences distinctes par capteur, seuil exact,
  capteur avec une observation et multiplicateur invalide, même à vide.
- Silence : silence avéré, récent, seuil exact, plusieurs cadences, fuseau du
  temps de référence, conversion UTC, multiplicateur invalide et dataset vide.
- IQR : bornes attendues, outliers, séparation des capteurs, index pandas répétés,
  valeurs constantes, multiplicateur configurable/invalide et dataset vide.
- Nettoyage : qualités invalides, warnings, suppression configurable des deux
  types de doublons, conservation/suppression d'outliers, ordre des étapes,
  entrées vides ou entièrement invalides, absence de mutation des entrées.
- Rapport : compte initial/final/supprimé, anomalies détectées mais conservées,
  chevauchement des causes et les 16 combinaisons des quatre options booléennes.

## Conventions constatées

Le détecteur de doublons marque **tous** les membres d'un groupe (`keep=False`).
Le cleaner supprime donc tous ces membres lorsque l'option est active, et non
seulement les copies supplémentaires. Les tests rendent cette convention explicite.

Les compteurs d'anomalies du rapport portent sur le dataset initial ; ils ne sont
pas des nombres de suppressions par étape et peuvent se chevaucher. Le total
supprimé doit toujours être `initial_row_count - final_row_count`.

La politique numérique teste la finitude. Le filtre de qualité et le cleaner
actuels classent/suppriment selon le libellé quality ; ils n'appellent pas cette
politique numérique. Les tests ne prétendent donc pas qu'un `good` de valeur inf
sera supprimé par le cleaner : cette intégration n'est pas spécifiée ici.

## Bugs reproduits — aucune correction métier

1. **Contamination des bornes IQR avec index pandas répétés.** Concaténer deux
   séries sans `ignore_index=True` produit des index communs 0..4. Le détecteur
   écrit avec `result.loc[group.index, ...]`, ce qui touche aussi les lignes de
   l'autre capteur. Pour les valeurs [1,2,3,4,100], la borne supérieure attendue 7
   est écrasée par 1006, calculée pour [1000,1001,1002,1003,1004]. Test :
   `test_duplicate_dataframe_indexes_do_not_mix_sensors`. Recommandation : rendre
   les affectations indépendantes des labels d'index partagés, puis vérifier la
   séparation des bornes et indicateurs sans imposer un prétraitement aux appelants.
2. **Validation du fuseau ignorée à vide.** `SilentSensorDetector.detect` retourne
   avant de valider reference_time lorsque le DataFrame est vide. Un datetime
   sans timezone est donc accepté contrairement à la règle demandée. Test :
   `test_reference_timezone_required_even_on_empty_data`. Recommandation : valider
   le temps de référence avant le retour anticipé.

Les échecs restent visibles, sans `expectedFailure` ni skip. Aucun code métier,
modèle SQLAlchemy ou route API n'est modifié, et aucun commit n'est effectué.
