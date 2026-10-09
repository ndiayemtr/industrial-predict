# 2.7 — Tests automatisés de Predictions Persistence

45 tests `unittest` couvrent la validation, le repository, le service,
les trois méthodes de persistance et l'historique HTTP des équipements.
Les cas paramétrés utilisent `subTest` et ne comptent pas séparément.
Les trois références obligatoires ont été lues avant toute modification :
`README_AI.md`, `docs/project-status.md`, `docs/architecture.md`.

| Fichier | Couverture |
| --- | --- |
| `test_schemas.py` | Create valide/complet, identifiants positifs, horizon positif, champs facultatifs, trois PredictionType, Read depuis les attributs ORM |
| `test_repository.py` | Create/relecture, JSON imbriqué, get_by_id, historique par équipement/type, dernière prédiction, pagination, count_all, tous les filtres, ordre et timestamps égaux |
| `test_service.py` | Mapping create, équipement absent, commit/refresh, pagination et transmission exacte des filtres, intégration SQL réelle |
| `test_persistence.py` | Mapping et relecture des anomalies/risques/health scores, scores, alertes, niveaux, horizon, métadonnées, details/components, validations et équipement absent |
| `test_route.py` | Endpoint réel 200/404/422, structure exacte, pagination, filtres seuls/combinés, total filtré, page vide, équipement sans historique, validation des query params |

## Fixtures et déterminisme

`support.py` réutilise `dashboard.support.DatabaseCase`, avec des actifs connus,
une session attachée à une transaction externe et une base SQLite en mémoire
par défaut. Les commits du service ne valident pas la transaction externe,
qui est annulée au nettoyage de la fixture. Aucune donnée de développement
n'est utilisée. Les dates des prédictions et `created_at` sont fixées ; les
tests n'affirment pas de valeur dépendant de l'horloge système pour les défauts.

Le jeu d'historique comprend plusieurs types, niveaux, alertes True/False/NULL,
deux timestamps identiques et un autre équipement. Les attentes vérifient
explicitement `predicted_at DESC, id DESC`, les bornes temporelles inclusives,
`is_alert=False` et la cohérence entre items et total pour chaque filtre.

Les tests HTTP utilisent l'application, le service et le repository réels.
Seul `get_db` est remplacé par la session isolée ; les overrides sont restaurés
après chaque test. Les tests unitaires du service utilisent des autospecs pour
vérifier les arguments transmis, la création, le commit et le refresh.

## PostgreSQL

`test_postgresql_timezone_offsets_compare_instants` nécessite une connexion
PostgreSQL de test via `DASHBOARD_TEST_DATABASE_URL`. Il vérifie qu'une date avec
offset +05:30 et une date UTC représentant le même instant correspondent aux
bornes du filtre `timestamptz`. Ce cas est explicitement ignoré sous SQLite,
qui perd les offsets ; il n'est pas simulé comme un succès SQLite.

La fixture PostgreSQL existante crée un schéma temporaire dans une transaction
annulée après le test. Les autres tests de ce dossier peuvent aussi s'exécuter
sur PostgreSQL avec cette même variable. La migration Alembic n'est pas appliquée
à une base de développement : les tests SQL utilisent `Base.metadata.create_all`
selon la convention des fixtures existantes.

## Commandes depuis la racine (PowerShell)

```powershell
$env:PYTHONPATH = 'backend;tests'
$env:DEBUG = 'false'
backend/.venv/Scripts/python.exe -m unittest discover -s tests/predictions -t tests -v
backend/.venv/Scripts/python.exe -m unittest discover -s tests
Push-Location backend
try {
    .venv/Scripts/python.exe -m compileall app
} finally {
    Pop-Location
}
```

`DEBUG=false` neutralise dans le processus de tests la variable invalide
`DEBUG=release` rencontrée lors des validations précédentes. Aucun fichier de
configuration n'est modifié. Pour les tests spécifiques PostgreSQL, définir
`DASHBOARD_TEST_DATABASE_URL` vers une base dédiée avant le lancement.

## Validation du 9 octobre 2026

| Suite | Réussis | Échecs | Erreurs | Ignorés |
| --- | ---: | ---: | ---: | ---: |
| Predictions (45 tests) | 44 | 0 | 0 | 1 |
| Backend complète (542 tests) | 538 | 0 | 0 | 4 |

Les quatre tests ignorés nécessitent PostgreSQL : trois préexistants et le cas
timezone décrit ci-dessus. `python -m compileall app` depuis `backend` réussit
(code de sortie 0).

Aucun bug métier détecté dans les cas couverts. Les erreurs du premier lancement
étaient dans les tests : accès par dictionnaire à un objet Page et lecture d'un
ID ORM après détachement. Elles ont été corrigées dans les tests uniquement.
Aucun `expectedFailure` ajouté.

Seuls les huit fichiers de `tests/predictions/` sont créés pour cette tâche.
Aucun module métier, contrat API, modèle SQLAlchemy ou migration modifié.
Les changements préexistants de l'implémentation 2.7 ont été préservés.
Aucun commit effectué.
