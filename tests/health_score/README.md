# 2.6.12 — Tests automatisés du Health Score

48 tests `unittest` couvrent les neuf modules métier, les schémas API, le service
et `POST /api/v1/equipments/{equipment_id}/health-score`. Les cas paramétrés
utilisent `subTest` et ne sont pas comptés séparément par le runner.

Les références `README_AI.md`, `docs/project-status.md` et `docs/architecture.md`
ont été lues avant modification. Le périmètre reste limité aux tests.

| Fichier | Couverture |
| --- | --- |
| `test_components.py` | Failure/Anomaly : bornes, intermédiaires, arrondi, valeurs invalides ; qualité : valid/warning/invalid, mélange, comptes négatifs, total nul ; maintenance : pénalités seules/cumulées et plancher ; dataclasses immuables et poids par défaut |
| `test_aggregator.py` | Résultat 78.5, poids par défaut/personnalisés, composantes hors limites, poids négatifs, somme différente de 1, arrondi |
| `test_classifier_explainer.py` | Dix bornes exactes des niveaux, valeurs hors intervalle, explications triées, top_n et composantes invalides |
| `test_calculator.py` | Orchestration réelle, composants et résultat final, extrêmes, poids personnalisés, propagation des erreurs |
| `test_api_schemas.py` | Payload valide, bornes fermées, comptes et total qualité, champs requis, valeurs par défaut, sérialisation de HealthScoreRead |
| `test_service.py` | Délégation avec autospec, mapping de composantes distinctes, équipement absent, intégration repository/calculateur réels |
| `test_route.py` | HTTP 200/404/422, structure exacte, validation des champs, flags facultatifs |

Les résultats attendus sont fixés indépendamment, sans réimplémenter le calcul.
La fixture principale produit les composantes 80, 90, 70 et 60, le score 78.5
et le niveau `good`. Les tests HTTP utilisent l'application réelle, son service,
son repository et son calculateur ; seule la dépendance `get_db` est remplacée
par la session isolée de `dashboard.support.DatabaseCase`. Les overrides sont
restaurés après chaque test. Cette fixture utilise SQLite en mémoire par défaut.
Les tests du service avec mocks vérifient séparément les arguments transmis et
le mapping de quatre composantes distinctes.

Toutes les combinaisons de flags maintenance sont testées. Les pénalités actuelles
totalisent au maximum 80 ; un test augmente temporairement une pénalité via
`patch.object` pour exercer le plancher défensif à zéro, sans modifier le métier.

## Exécution depuis la racine du dépôt (PowerShell)

```powershell
$env:PYTHONPATH = 'backend;tests'
$env:DEBUG = 'false'
backend/.venv/Scripts/python.exe -m unittest discover -s tests/health_score -t tests -v
backend/.venv/Scripts/python.exe -m unittest discover -s tests
Push-Location backend
try {
    .venv/Scripts/python.exe -m compileall app
} finally {
    Pop-Location
}
```

`DEBUG=false` neutralise dans le processus de tests la valeur d'environnement
invalide `DEBUG=release` rencontrée précédemment. Aucun fichier de configuration
n'est modifié.

## Validation du 9 octobre 2026

| Vérification | Réussis | Échecs | Erreurs | Ignorés |
| --- | ---: | ---: | ---: | ---: |
| Health Score | 48 | 0 | 0 | 0 |
| Suite complète (497 tests) | 494 | 0 | 0 | 3 |

Les trois tests ignorés préexistants nécessitent PostgreSQL via
`DASHBOARD_TEST_DATABASE_URL`. Aucun nouveau skip ni `expectedFailure` ajouté.
`python -m compileall app` depuis `backend` avec le virtualenv réussit (code 0).

Aucun bug détecté dans les cas couverts. Aucun module métier, contrat API ou
modèle SQLAlchemy modifié. Les changements préexistants dans la route
`backend/app/api/routes/equipment.py` et les fichiers API/service Health Score
ont été conservés sans modification. Aucun commit effectué.
