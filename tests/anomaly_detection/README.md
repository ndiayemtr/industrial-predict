# 2.4.9 — Tests automatisés de la détection d'anomalies

## Bug métier documenté avant correction

Le 7 octobre 2026, le test
`test_each_negative_weight_is_rejected_despite_positive_total` a révélé que
`UnifiedAnomalyScorer.build` acceptait chacun des trois poids négatifs tant que
leur somme restait positive. Les six sous-cas (trois poids, entrée vide ou non
vide) échouaient car aucune `ValueError` n'était levée.

Reproduction numérique sur le code non corrigé :

```python
source = pd.DataFrame({
    "statistical_anomaly": [True, False],
    "robust_zscore_anomaly": [False, True],
    "isolation_forest_anomaly": [False, True],
})
UnifiedAnomalyScorer().build(source, statistical_weight=-0.1)
```

Les autres poids valent 0.35 et 0.40, la somme vaut 0.65. Les scores observés
étaient -0.15384615384615385 et 1.1538461538461537 : le premier signal diminuait
le score, et les résultats sortaient du contrat [0, 1] d'`AnomalyResult`.

Correction appliquée après cette documentation : rejeter tout poids individuel < 0 par `ValueError`, avant
le retour sur DataFrame vide. Conserver les poids nuls individuels lorsque la
somme reste strictement positive, la normalisation et les poids par défaut.
Le test de régression vérifie chacun des trois paramètres indépendamment.

Aucun autre bug métier révélé par les tests. Lors du premier lancement, un mock
Isolation Forest renvoyait des listes au lieu des tableaux NumPy attendus ;
cette erreur du test a été corrigée sans modifier le détecteur.

## Couverture

53 tests `unittest`, sans base de données pour ce dossier. Les cas paramétrés
utilisent `subTest` et ne sont pas comptés comme tests distincts par le runner.

| Fichier | Cas principaux |
| --- | --- |
| `test_schemas.py` | Scores 0 et 1 inclus, valeurs hors intervalle rejetées |
| `test_statistical_detector.py` | Vide, normal/anomalie, seuil strict, std NaN/nul, colonnes et paramètres invalides |
| `test_zscore_detector.py` | Z-score avec std échantillon, robust z-score/MAD, outlier, variance/MAD nuls, singleton, capteurs isolés, seuils |
| `test_isolation_forest_detector.py` | Outlier réel, features personnalisées/manquantes, exclusion des NaN et valeurs non numériques, moins de deux lignes, contamination, reproductibilité |
| `test_unified_score.py` | Huit combinaisons des signaux, signaux absents/NA, seuil inclusif, poids normalisés/nuls/négatifs |
| `test_sensor_detector.py` | Trois détecteurs réels et score final, normal/anomalie forte, transmission exacte des paramètres et frames intermédiaires |
| `test_equipment_detector.py` | Plusieurs équipements, tous les compteurs, ratios, scores max/moyen et flags, colonnes requises |
| `test_explainer.py` | Vide, raisons absentes, cinq raisons seules ou combinées, colonnes facultatives absentes |

Les entrées non vides restent inchangées, y compris leurs indices. Les tests de
Z-score entrelacent deux capteurs avec des indices répétés. Isolation Forest est
exécuté réellement pour la détection et la reproductibilité ; un mock vérifie
précisément les lignes utilisées pour le fit et le scoring. Le mock renvoie les
tableaux NumPy du contrat scikit-learn. Aucun nouvel ignore ou `expectedFailure`.

## Exécution depuis la racine du dépôt (PowerShell)

```powershell
$env:PYTHONPATH = 'backend;tests'
$env:DEBUG = 'false'
backend/.venv/Scripts/python.exe -m unittest discover -s tests/anomaly_detection -t tests -v
backend/.venv/Scripts/python.exe -m unittest discover -s tests
Push-Location backend
try {
    .venv/Scripts/python.exe -m compileall app
} finally {
    Pop-Location
}
```

Le virtualenv du backend doit contenir les dépendances du projet, notamment
pandas, NumPy, scikit-learn et Pydantic. `DEBUG=false` neutralise dans le processus
de tests la valeur d'environnement invalide `DEBUG=release` rencontrée lors de
la validation précédente, sans modifier les fichiers de configuration.

## Validation du 7 octobre 2026

| Vérification | Réussis | Échecs | Erreurs | Ignorés |
| --- | ---: | ---: | ---: | ---: |
| Détection d'anomalies | 53 | 0 | 0 | 0 |
| Suite complète (377 tests) | 374 | 0 | 0 | 3 |

Les trois tests ignorés préexistants nécessitent `DASHBOARD_TEST_DATABASE_URL`
(PostgreSQL). `python -m compileall app`, depuis `backend` avec le Python du
virtualenv, réussit (code de sortie 0).

Seul `backend/app/anomaly_detection/unified_score.py` a été modifié côté métier
pour le bug décrit ci-dessus. Aucune route API ni modèle SQLAlchemy modifié.
Aucun commit effectué.
