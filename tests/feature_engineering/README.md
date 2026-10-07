# 2.3.10 — Tests automatisés du Feature Engineering

44 tests `unittest`, sans base de données, couvrent les huit modules demandés.
Les cas paramétrés utilisent `subTest` : ils ne sont pas comptés comme des tests
distincts dans le bilan du runner.

| Fichier | Couverture |
| --- | --- |
| `test_lag_features.py` | Lags 1/2/3, lags personnalisés ou absents, paramètres invalides, isolation des capteurs |
| `test_trend_features.py` | Pente par observation, fenêtres partielles, séries constantes, fenêtre < 2 |
| `test_variability_features.py` | Range, CV, moyenne nulle et statistiques manquantes |
| `test_rate_features.py` | Taux positif/négatif/nul, intervalles <= 0 et valeurs manquantes |
| `test_multiscale_features.py` | Moyennes et écarts-types échantillon, fenêtres 3/5/10 et personnalisées, fenêtre < 1 |
| `test_quality_features.py` | Flags qualité, OR des doublons, flags absents ou partiels |
| `test_equipment_features.py` | Agrégation par équipement, capteurs distincts, nombre de valeurs, moyenne, écart-type, ratios |
| `test_feature_pipeline.py` | Pipeline réel, colonnes finales, calculs numériques, ordre temporel, timestamps identiques, paramètres |

Chaque module couvre le DataFrame vide. Les modules exigeant des colonnes
couvrent leur absence : `ValueError` pour Variability, Rate et Equipment,
`KeyError` pour Lag, Trend, MultiScale et le pipeline, selon leur contrat actuel.
Quality accepte l'absence de toutes les colonnes de flags et produit `False`.
Les calculs temporels sont vérifiés avec des séries entrelacées, des cadences
différentes et des indices répétés. Les valeurs attendues sont déterminées
indépendamment ; le pipeline multi-capteurs est aussi comparé aux exécutions
séparées de chaque série. Les entrées non vides restent inchangées.

## Exécution depuis la racine du dépôt (PowerShell)

```powershell
$env:PYTHONPATH = 'backend;tests'
$env:DEBUG = 'false'
backend/.venv/Scripts/python.exe -m unittest discover -s tests/feature_engineering -t tests -v
backend/.venv/Scripts/python.exe -m unittest discover -s tests
Push-Location backend
try {
    .venv/Scripts/python.exe -m compileall app
} finally {
    Pop-Location
}
```

`DEBUG=false` est limité au processus PowerShell ; aucun fichier de configuration
n'est modifié. Les fixtures existantes de la suite complète utilisent SQLite en
mémoire par défaut. Les trois tests PostgreSQL restent ignorés lorsque
`DASHBOARD_TEST_DATABASE_URL` n'est pas renseigné.

## Validation du 7 octobre 2026

| Vérification | Réussis | Échecs | Erreurs | Ignorés |
| --- | ---: | ---: | ---: | ---: |
| Feature Engineering | 44 | 0 | 0 | 0 |
| Suite complète (324 tests) | 321 | 0 | 0 | 3 |

`python -m compileall app`, exécuté avec le Python du virtualenv depuis `backend`,
réussit (code de sortie 0).

La première exécution de la suite complète a donné 160 réussites et 6 erreurs
d'import (166 cas comptabilisés, aucun échec ni test ignoré). La configuration
recevait `DEBUG=release`, valeur invalide pour un booléen. La relance avec
`DEBUG=false` a permis de découvrir et d'exécuter toute la suite. Il s'agit d'un
problème d'environnement, sans correction du code métier.

Aucun bug métier détecté. Aucun test `expectedFailure` ni nouveau skip ajouté.
Aucune route API, aucun modèle SQLAlchemy ni module métier modifié.
