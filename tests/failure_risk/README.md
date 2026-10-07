# 2.5.11 — Tests automatisés du modèle de risque de panne

## Bug métier documenté avant correction

Le 7 octobre 2026, le premier lancement des tests a donné 69 réussites,
1 échec, 0 erreur et 0 test ignoré (70 tests). Le cas
`test_repeated_indices_do_not_contaminate_labels_between_equipment`
a révélé une contamination des labels et métadonnées dans `FailureLabeler`.

Reproduction sur le code non corrigé : concaténer, sans `ignore_index=True`,
deux DataFrames contenant chacun une mesure à l'indice 0, respectivement pour
les équipements 10 et 20. Ajouter une seule maintenance corrective, future de
1 heure, pour l'équipement 10. Résultat attendu : labels `[1, 0]`, prochaine
panne et délai seulement sur la première ligne. Résultat observé : `[1, 1]`.

Cause : les écritures `result.at[index, ...]` ciblent toutes les lignes portant
le même indice lorsqu'il n'est pas unique. Les indices répétés sont courants
après concaténation de séries ; un équipement sans panne reçoit ainsi une
cible et des informations futures provenant d'un autre équipement.

Correction appliquée après cette documentation : écrire les trois colonnes de résultat par position de
ligne avec `iat`, en conservant les indices et l'ordre d'origine. La recherche
de la prochaine panne, les conversions UTC et le contrat d'horizon restent
inchangés. Les tests de régression couvriront les indices répétés entre
équipements et entre mesures d'un même équipement.

Aucun autre bug métier révélé par le premier lancement. Les cas de décalages
UTC, changement d'heure, timestamps naïfs interprétés en UTC et exclusion des
colonnes de leakage passent.

## Couverture

72 tests `unittest`, sans base de données pour ce dossier. Les cas paramétrés
utilisent `subTest` et ne sont pas comptés séparément par le runner.

| Fichier | Cas principaux |
| --- | --- |
| `test_failure_labeler.py` | Horizon invalide/exact/dépassé, données vides, colonnes manquantes, corrective/non corrective, panne passée/simultanée, prochaine panne, métadonnées, UTC et changement d'heure, indices répétés |
| `test_supervised_dataset.py` | Dataset vide, colonnes requises, labels positifs/négatifs int8, horizon transmis, résumé et indices répétés |
| `test_failure_risk_preparer.py` | X/y, exclusion explicite des données futures/maintenance, IDs/timestamp/codes, numériques/booléens et types nullables, texte exclu, cible absente, vide |
| `test_time_splitter.py` | Vide, entrée non triée, trois partitions chronologiques, ratios personnalisés/invalides, validation vide, arrondis, timestamp absent, décalages timezone |
| `test_baseline_classifier.py` | Fit réel, prédictions, probabilités de classe 1, indices conservés, X/y invalides, classe unique, prédiction avant fit |
| `test_random_forest_classifier.py` | Fit réel, prédictions, probabilités, importances triées, hyperparamètres effectivement transmis aux arbres, erreurs X/y et feature_names |
| `test_evaluator.py` | Accuracy/precision/recall/F1 indépendants, matrice binaire fixe, ROC-AUC, classe unique, probabilités absentes, longueurs invalides, y_true vide |
| `test_risk_score.py` | Probabilités 0 à 1, scores 0 à 100, quatre niveaux, seuils exacts 0.25/0.50/0.75, valeurs hors intervalle, série vide |
| `test_prediction_explainer.py` | Tri, top_n, validation, colonnes absentes, vide, pourcentages, résumé et arrondi |

Les modèles scikit-learn sont entraînés sur une petite fixture déterministe,
sans mock. Les tests vérifient les résultats, les noms et indices des Series
produites et la préservation des entrées. Les métriques ont des valeurs attendues
calculées indépendamment et un cas asymétrique distingue précision et rappel.
Les attentes d'exclusion ne sont pas dérivées d'`EXCLUDED_COLUMNS` : toutes les
colonnes sensibles prévues sont aussi testées sous forme numérique pour éviter
que leur rejet dépende uniquement du type datetime ou texte.

Les dates naïves suivent le contrat actuel de `pd.to_datetime(..., utc=True)` :
elles sont interprétées comme UTC. Les offsets différents et le changement
d'heure sont comparés en temps écoulé réel. La panne à l'instant exact de la
mesure n'est pas future ; l'extrémité de l'horizon est incluse. Les métadonnées
de panne restent NA lorsque la panne est hors horizon, selon le contrat actuel.

## Exécution depuis la racine du dépôt (PowerShell)

```powershell
$env:PYTHONPATH = 'backend;tests'
$env:DEBUG = 'false'
backend/.venv/Scripts/python.exe -m unittest discover -s tests/failure_risk -t tests -v
backend/.venv/Scripts/python.exe -m unittest discover -s tests
Push-Location backend
try {
    .venv/Scripts/python.exe -m compileall app
} finally {
    Pop-Location
}
```

Les dépendances du projet doivent être disponibles dans le virtualenv du backend,
notamment pandas, NumPy et scikit-learn. `DEBUG=false` neutralise dans le processus
de tests la valeur d'environnement invalide `DEBUG=release` rencontrée lors des
validations précédentes, sans modifier les fichiers de configuration.

## Validation du 7 octobre 2026

| Vérification | Réussis | Échecs | Erreurs | Ignorés |
| --- | ---: | ---: | ---: | ---: |
| Risque de panne | 72 | 0 | 0 | 0 |
| Suite complète (449 tests) | 446 | 0 | 0 | 3 |

Les trois tests PostgreSQL préexistants sont ignorés faute de
`DASHBOARD_TEST_DATABASE_URL`. Aucun nouveau skip ni `expectedFailure` ajouté.
`python -m compileall app`, depuis `backend` avec le Python du virtualenv,
réussit (code de sortie 0).

Seul `backend/app/data_pipeline/failure_labeler.py` est modifié côté métier pour
le bug documenté ci-dessus. Aucune route API ni modèle SQLAlchemy modifié.
Aucun commit effectué.
