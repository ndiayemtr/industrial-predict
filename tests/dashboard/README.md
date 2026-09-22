# Tests automatisés Dashboard — 1.4.16.7

Depuis `backend`, avec Python 3.12 et les dépendances de
`backend/requirements.txt` installées :

```powershell
python -m unittest discover -s ../tests -v
python -m compileall app
```

La suite utilise `unittest` (bibliothèque standard), SQLAlchemy et le TestClient
FastAPI déjà disponibles dans les dépendances du backend. Aucun paquet de test
supplémentaire n'est nécessaire.

## Organisation et isolation

- `support.py` : base neuve par test, fixtures Company/Site/Equipment/Sensor,
  horloge UTC fixe et doubles typés des agrégats pour les tests du service.
- `test_repository.py` : vraies requêtes SQL sur des données insérées ; périmètres,
  catégories libres, bornes temporelles, dernières mesures, maintenances, sommes
  et absence de multiplication des lignes entre les deux branches.
- `test_service.py` : validation avec les vrais repositories de périmètre ;
  agrégats simulés pour tester ratios, catégories, jours vides, dates, âge,
  couvertures, distinction zéro/null et structure du résultat.
- `test_route.py` : appels HTTP à l'application et route réelles, avec dépendance
  de session remplacée et service utilisant les mêmes agrégats simulés ; réponse
  sérialisée, codes 200/400/404/422 et messages de validation.

`DATABASE_URL` est remplacée en mémoire avant l'import de l'application. La suite
ne se connecte jamais à la base configurée dans `.env` et ne modifie aucun modèle.
Chaque test possède sa session et sa transaction, annulée lors du nettoyage.
L'horloge et les dépendances FastAPI sont restaurées après chaque test.

Par défaut, SQLite en mémoire exécute les tests SQL avec clés étrangères activées.
SQLite ne reproduit pas les dates avec fuseau de PostgreSQL ni sa fonction
`timezone()` : aucun contournement dans le code métier, aucun faux résultat SQL
n'est utilisé pour prétendre tester ces comportements. La requête journalière est
compilée pour PostgreSQL dans un test dédié, et son exécution native reste un test
explicitement ignoré tant que PostgreSQL n'est pas configuré.

## Exécution PostgreSQL

Pour exécuter tous les tests SQL sur une base PostgreSQL dédiée aux tests :

```powershell
$env:DASHBOARD_TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/industrial_predict_test'
python -m unittest discover -s ../tests -v
```

Le compte doit pouvoir créer un schéma. Chaque test crée un schéma au nom unique,
redirige les tables SQLAlchemy vers ce schéma et annule la transaction contenant
le schéma et les données à la fin. Aucun `drop_all()` ni nettoyage des tables
existantes n'est exécuté. Une URL PostgreSQL configurée mais inaccessible fait
échouer les tests ; aucun repli silencieux sur SQLite.

Le test PostgreSQL vérifie le regroupement par jour UTC avec une session réglée
sur `America/New_York`, les bornes exclusives, l'isolation, puis le chemin complet
repository/service/schémas avec remplissage des jours vides et calcul d'âge.

## Couverture métier

Les cas couvrent les vingt points demandés : isolation entreprise/site/équipement,
rejets des périmètres incohérents, périodes invalides et naïves, équipements sans
capteur, couverture sans double comptage, qualités inconnues, `[start, end)`,
jours vides, ordre timestamp puis id, capteurs sans relevé, maintenances ouvertes
et en retard, completed sans date, part corrective, arrêts 30/0/null, coûts
partiels, zéro intervention contre valeurs absentes et indépendance des agrégats
Measurement/MaintenanceRecord. S'y ajoutent les valeurs négatives, l'infini positif
pour le coût, les périodes futures, les catégories inconnues et les erreurs HTTP.

## Écarts constatés, sans correction métier

1. La note 1.4.16.1 prévoit de différer le KPI monétaire sans convention de devise
   commune. Le service actuel retourne `total_cost` même avec `currency=None`.
   Les tests vérifient le calcul et l'absence de devise inventée ; ils ne valident
   pas une convention monétaire qui n'existe pas dans le modèle.
2. La note prévoit de signaler les mesures futures comme incohérentes. Elles sont
   exclues des derniers relevés, mais aucun champ du dashboard ne rend ce signal
   visible. Les tests vérifient l'exclusion, pas un signal absent du contrat.

Aucun bug d'agrégation ou de validation n'a été mis en évidence par les tests
exécutés. Aucun fichier applicatif n'est modifié. La compilation SQL seule ne
remplace pas l'exécution du test PostgreSQL.

Les avertissements existants sur `datetime.utcnow()` dans les modèles et sur
`httpx` dans le TestClient Starlette ne sont pas corrigés dans cette étape.
