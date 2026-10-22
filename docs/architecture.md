# Architecture - Industrial Predict AI

## Vue générale

```text
Frontend Angular
        |
        v
REST API FastAPI
        |
        v
     Services
     /      \
    v        v
Repositories  ML / Predictive Analytics
    |        |
    v        v
PostgreSQL   Models / Scoring / Recommendation Engine
```

## Frontend

Le socle Angular standalone UI 1.1 à UI 1.8 est livré et fusionné dans `main` : Shell Nebular,
Sidebar, Header global, routing avec chargement différé, page 404 et gestion
accessible du focus. Dashboard V1 et Companies MVP sont livrés dans `main`.
Sites et Équipements MVP sont intégrés dans `main` (référence locale `a76e49c`).
Sensors MVP est intégré dans `main` à `20293a4`. Measurements MVP en lecture
seule est implémenté sur `feature/frontend-measurements` à `43d12fa`, en préparation
de livraison UI 7.6. Maintenance, Prédictions et Recommandations restent des
placeholders, distincts des agrégats Dashboard et du ML backend.

L'architecture présente sépare `layout` (structure globale), `features` (pages
métier), `shared` (présentation réutilisable et pages transversales) et `core`
(configuration HTTP, services et modèles de références). Le dossier `core`
est implémenté ; `features/dashboard`, `features/companies`, `features/sites`, `features/equipments`
ainsi que `features/sensors` et `features/measurements` existent.

UI 1.7 a livré quatre composants de présentation dans
`shared/components/` : PageHeader, LoadingState, EmptyState et ErrorState.
Ils sont implémentés et testés, indépendants du backend et
des modules métier. Leurs contrats figurent dans
`frontend-architecture.md` ; les règles visuelles figurent dans `ui-design.md`.

UI 2.1 à UI 2.8 ont livré et validé le Dashboard V1, fusionné dans `main`
via `f3f6f2c` et publié sur GitHub (référence `23e28e5`) :
page standalone lazy → façade locale → DashboardApiService → agrégats existants
de `GET /api/v1/dashboard`. `ReferenceDataApiService` consomme les CRUD paginés
existants pour entreprises, sites et équipements. Les composants de présentation
ne calculent aucun nouveau KPI et ne font aucun appel HTTP.
`provideHttpClient()` est configuré ; l'URL relative `/api/v1` et le proxy
Angular historique vers `http://127.0.0.1:8000` restent présents (D014).
Le démarrage permanent [DEV](../infra/development/README.md) utilise désormais
Angular 4201 et un proxy contrôlé vers FastAPI 8001, puis PostgreSQL 5434 /
`industrial_predict_dev`, sans repli vers 8000.
Le reverse proxy de production reste à configurer et n'est pas livré ici.
La route Dashboard n'a pas d'autorisation multi-entreprises démontrée ; sélection
et filtrage ne remplacent pas authentification/RBAC. Cette livraison ne constitue
pas une préparation à la production SaaS multi-tenant.
Les fonctionnalités ML backend ci-dessous restent livrées, mais leur consommation
est hors périmètre Dashboard V1. UI 2.8 a clôturé la documentation Dashboard.
Companies MVP couvre liste/recherche serveur paginée, détail, création et
modification. La liste suit page → façade locale → CompaniesApiService ; le
GET liste réutilise ReferenceDataApiService. Détail et formulaire partagé
création/modification ont des états locaux et utilisent le même service API.
CompanyRead, Page et ReferencePageQuery sont réutilisés ; CompanyCreate et
CompanyUpdate décrivent les écritures. Les routes Companies sont différées
par `loadChildren`, puis `loadComponent`, sous le Shell existant.

POST crée une entreprise ; PATCH ne transmet que les champs modifiés et ne
part pas sans changement. Un succès déclenche un toast Nebular et une navigation
vers le détail, avec confirmation textuelle persistante. L'overlay est configuré
au niveau application. Aucun DELETE n'est exposé par l'UI ou le service Angular :
la cascade backend justifie son exclusion du MVP. L'endpoint DELETE reste
accessible directement dans l'API existante.

L'intégration FastAPI réelle UI 3.7 est limitée aux lectures ; les écritures
POST/PATCH ont été simulées. Ni autorisation multi-entreprises ni sécurité de
production SaaS multi-tenant ne sont démontrées. UI 3.1 à UI 3.7.1 sont terminées ;
UI 3.8 a finalisé les documents avant la fusion Companies `537822c`.
Les tests historiques (348 tests Angular,
trois suites séquentielles réussies en UI 3.7.1), les observations responsive et
les limites sont détaillés dans [project-status.md](project-status.md).
L'architecture frontend actuelle figure dans
[frontend-architecture.md](frontend-architecture.md) ;
[etape-ui-3.1-companies.md](etape-ui-3.1-companies.md) conserve la conception
initiale et les écarts d'implémentation. Aucun backend ni contrat modifié ici.

Sites suit la même séparation page/façade locale/service de transport, avec
un formulaire propre à la feature, des pages création/édition distinctes et un
PATCH différentiel limité à name/code/description. Entreprise non transférable,
aucun DELETE frontend ; ces restrictions UI ne sécurisent pas l'API backend.
La validation réelle Angular/FastAPI/PostgreSQL et les limites sont décrites dans
le [statut Sites](project-status.md#sites-mvp---livraison-préparée-ui-48), sans
réexécution en UI 4.8. Aucun contrôle d'authentification ou d'autorisation
multi-tenant n'est actuellement livré.

Équipements réutilise les modèles core et le transport de références via
EquipmentsApiService. La liste utilise une façade locale, les pages détail,
création et édition orchestrent leurs états et EquipmentForm est partagé.
La résolution réelle Equipment -> Site -> Company est indépendante du contexte URL.
POST inclut site_id validé, jamais company_id ; PATCH ne contient que les six
champs éditables modifiés. Aucun transfert ou DELETE frontend. Les descendants
et données prédictives ne sont ni chargés ni inventés dans cette fiche.
Voir l'[architecture implémentée](frontend-architecture.md#équipements-mvp---architecture-implémentée-ui-5)
et le [bilan de livraison](ui-5.8-equipments-delivery.md) pour les références,
les preuves réelles/simulées et les limites de sécurité. Aucun backend modifié.

Sensors possède ses DTO stricts et SensorsApiService (GET paginé/détail, POST,
PATCH), une façade locale de liste et un formulaire partagé création/édition.
La chaîne Sensor -> Equipment -> Site -> Company est vérifiée sur les données
réelles ; les références indisponibles ne font pas disparaître la fiche Sensor.
L'API Sensors ne reçoit jamais company_id/site_id depuis Angular. La whitelist
PATCH ne contient que name/code/status/description réellement modifiés ; parent,
type et unité immuables en édition. Code globalement unique, aucun DELETE
frontend. Les liens Equipment <-> Sensors utilisent les parents réels, sans
transférer les filtres entre modules. Aucune mesure ou prédiction inventée.

B-SEN-01 rétablit SensorRepository.get_by_code par égalité exacte globale dans
`4defbe9`, avec tests isolés ; B-SEN-02/03 restent ouverts. Les restrictions UI
n'interdisent pas directement les opérations backend plus permissives.
L'[architecture Sensors](frontend-architecture.md#sensors-mvp---architecture-implémentée-ui-6)
décrit les flux ; le [statut Sensors](project-status.md#sensors-mvp---livraison-préparée-ui-68)
centralise preuves, réserves et limite de validation PostgreSQL.
[UI 6.8](ui-6.8-sensors-delivery.md) conserve la préparation historique Sensors,
intégrée dans main à 20293a4.

Measurements suit page -> façade locale -> MeasurementsApiService pour la liste,
et états locaux pour le détail. Le service expose seulement GET paginé avec
sensor_id obligatoire et GET détail, aucun POST/PATCH/DELETE frontend. Les
contrats temporels spécialisés backend restent distincts et inutilisés.
Quatre choix explicites valident Sensor -> Equipment -> Site -> Company ; les
parents de contexte ne partent pas dans la query Measurements. Qualité déclarée
parmi cinq valeurs et périodes UTC [début, fin) filtrent la pagination serveur.

Les horodatages restent des chaînes ISO avec offsets et microsecondes, sans
Date/toISOString ; l'affichage UTC est explicite. L'unité est celle du Sensor
actuel, pas un snapshot garanti. Une référence indisponible conserve la mesure.
Sensor -> Measurements utilise les quatre ids réels et page=1/page_size=20 ;
liste/détail/retour préservent leur contexte. Styles d'actions existants réutilisés.
Aucun graphique, polling, flux temps réel ou calcul prédictif fictif.

L'[architecture Measurements](frontend-architecture.md#measurements-mvp---architecture-implémentée-ui-7)
détaille les flux ; le [statut Measurements](project-status.md#measurements-mvp---livraison-préparée-ui-76)
centralise les preuves historiques et dettes : 1 482 tests/build/605,65 kB, GET
réels et SQL concordants, 40 lignes conservées, empreintes des huit tables
inchangées. Ni la chaîne UI ni la recette DEV ne fournissent une autorisation
multi-tenant. [UI 7.6](ui-7.6-measurements-delivery.md) prépare la livraison sans
nouveau test, build, accès PostgreSQL ou changement backend.

## Backend

```text
app/
├── api/
│   └── routes/
├── models/
├── schemas/
├── repositories/
├── services/
├── core/
├── data_pipeline/
└── ml/
```

## Modèle métier

```text
Company
└── Site
    └── Equipment
        ├── Sensor
        │   └── Measurement
        ├── MaintenanceRecord
        ├── PredictionRecord
        └── MaintenanceRecommendation
```

## Entités principales

### Company

Représente une entreprise cliente de la plateforme.

Une entreprise peut posséder zéro à plusieurs sites.

### Site

Représente un site industriel appartenant à une entreprise.

Un site possède un ou plusieurs équipements.

### Equipment

Représente un actif industriel surveillé.

Un équipement peut posséder :

- plusieurs capteurs ;
- plusieurs enregistrements de maintenance ;
- plusieurs prédictions ;
- plusieurs recommandations de maintenance.

### Sensor

Représente un capteur associé à un équipement.

Il collecte les données utilisées par les fonctions d'analyse et de prédiction.

### Measurement

Représente une mesure remontée par un capteur.

Les mesures constituent la principale source de données du pipeline analytique et ML.

### MaintenanceRecord

Représente une intervention de maintenance réalisée ou planifiée sur un équipement.

Les maintenances correctives sont notamment utilisées pour :

- générer les labels de panne ;
- calculer le Remaining Useful Life.

### PredictionRecord

Représente une prédiction persistée pour un équipement.

Types de prédictions supportés :

- `anomaly`
- `failure_risk`
- `health_score`
- `rul`

Cette entité permet notamment :

- l'historisation des prédictions ;
- les filtres par type, niveau, alerte et période ;
- l'utilisation des prédictions par le moteur de recommandations.

### MaintenanceRecommendation

Représente une recommandation de maintenance générée à partir des signaux prédictifs disponibles.

Une recommandation contient notamment :

- une priorité ;
- un type de recommandation ;
- un titre ;
- une raison ;
- une action recommandée ;
- les signaux utilisés ;
- la date de génération.

## Architecture applicative

Le backend suit le principe :

```text
Route
→ Service
→ Repository
→ Database
```

Les routes HTTP ne doivent pas contenir de logique métier.

### Routes API

Responsabilités :

- exposition des endpoints HTTP ;
- validation des paramètres ;
- injection des dépendances ;
- conversion des erreurs métier en codes HTTP ;
- sérialisation des réponses.

Les routes ne doivent pas contenir de logique métier ou ML.

### Services

Responsabilités :

- orchestration métier ;
- validation fonctionnelle ;
- coordination entre plusieurs repositories ;
- coordination avec les composants ML ;
- génération et persistance des prédictions ou recommandations.

### Repositories

Responsabilités :

- accès aux données ;
- requêtes SQLAlchemy ;
- création, lecture et filtrage des entités ;
- pagination ;
- agrégations lorsque nécessaire.

La logique métier ne doit pas être placée dans les repositories.

### Models

Les modèles SQLAlchemy représentent les entités persistées dans PostgreSQL.

Ils définissent notamment :

- les colonnes ;
- les contraintes ;
- les clés étrangères ;
- les relations entre entités.

### Schemas

Les schémas Pydantic sont utilisés pour :

- validation des entrées API ;
- validation des sorties ;
- contrats entre couches applicatives ;
- typage des structures métier.

## Pipeline prédictif

```text
Measurements
    ↓
Data Pipeline
    ↓
Feature Preparation
    ↓
ML Models
    ├── Anomaly Detection
    ├── Failure Risk
    ├── Health Score
    └── Remaining Useful Life
    ↓
PredictionRecord
    ↓
Recommendation Engine
    ↓
MaintenanceRecommendation
```

## Data Pipeline

Le dossier :

```text
app/data_pipeline/
```

contient les composants de préparation des datasets utilisés par les modèles ML.

Responsabilités principales :

- génération de labels ;
- construction de datasets supervisés ;
- préparation des données temporelles ;
- calcul du Remaining Useful Life ;
- gestion des observations censurées lorsque nécessaire.

## Machine Learning

Le dossier :

```text
app/ml/
```

contient les composants ML et analytiques.

La logique ML doit rester indépendante de la couche API.

### Anomaly Detection

Objectif : détecter des comportements anormaux dans les mesures des capteurs.

Approches utilisées :

- Z-score classique ;
- Z-score robuste ;
- Isolation Forest ;
- score d'anomalie unifié.

### Failure Risk

Objectif : estimer la probabilité qu'une panne corrective survienne dans un horizon donné.

Composants principaux :

- génération des labels de panne ;
- préparation du dataset supervisé ;
- baseline classifier ;
- Random Forest ;
- évaluation ;
- score de risque ;
- niveaux de risque ;
- explicabilité.

### Health Score

Objectif : produire un indicateur synthétique de l'état de santé d'un équipement.

Composantes principales :

- Failure Health ;
- Anomaly Health ;
- Data Quality Health ;
- Maintenance Health.

Le Health Score final est obtenu par agrégation pondérée.

### Remaining Useful Life

Objectif : estimer le nombre d'heures restantes avant la prochaine panne corrective connue.

Définition V1 :

```text
RUL(t) =
temps entre l'instant t
et la prochaine maintenance corrective connue
du même équipement
```

Principes :

- uniquement les maintenances correctives ;
- `started_at` obligatoire ;
- calcul par équipement ;
- unité : heures ;
- les observations sans panne future connue sont censurées ;
- les observations censurées sont exclues de l'entraînement V1.

Modèles :

- baseline `DummyRegressor` avec stratégie médiane ;
- `RandomForestRegressor`.

Évaluation :

- MAE ;
- RMSE ;
- R².

Classification RUL :

```text
critical : <= 24 h
warning  : <= 72 h
watch    : <= 168 h
healthy  : > 168 h
```

## Persistance des prédictions

Les résultats analytiques importants sont persistés dans `PredictionRecord`.

Flux :

```text
ML / Analytics
      ↓
PredictionService
      ↓
PredictionRepository
      ↓
prediction_records
```

La persistance permet :

- l'historisation ;
- la consultation des dernières prédictions ;
- les filtres ;
- la pagination ;
- l'exploitation par le moteur de recommandations.

## Recommendation Engine

Le moteur de recommandations transforme les signaux prédictifs en action de maintenance compréhensible.

Entrées possibles :

- anomaly score ;
- failure probability ;
- Health Score ;
- RUL.

Flux :

```text
PredictionRecord
      ↓
RecommendationService
      ↓
RecommendationPriorityResolver
      ↓
RecommendationEngine
      ↓
RecommendationExplainer
      ↓
MaintenanceRecommendation
```

## Priorités de recommandation

```text
critical
high
medium
low
```

La priorité la plus sévère déterminée par les signaux disponibles prévaut.

Ordre :

```text
critical > high > medium > low
```

## Types de recommandations

Types actuellement supportés :

- `urgent_maintenance`
- `inspection`
- `planned_maintenance`
- `monitoring`
- `no_action`

Le moteur produit une seule recommandation principale pour éviter des actions contradictoires.

## Principales règles V1

### Critical

Une priorité `critical` peut notamment être déclenchée par :

- RUL <= 24 heures ;
- failure probability >= 0.75 ;
- Health Score < 30.

Action principale : `urgent_maintenance`.

### High

Peut notamment être déclenchée par :

- RUL <= 72 heures ;
- Health Score entre 30 inclus et 50 exclus.

Actions possibles :

- `planned_maintenance`
- `inspection`

### Medium

Peut notamment être déclenchée par :

- RUL <= 168 heures ;
- anomaly score >= 0.50.

Actions possibles :

- `planned_maintenance`
- `monitoring`

### Low

Lorsqu'aucun signal significatif de risque ou de dégradation n'est détecté : `no_action`.

## Explicabilité

Les prédictions et recommandations doivent rester interprétables.

Une recommandation contient notamment :

- la priorité ;
- le type ;
- le titre ;
- la raison ;
- l'action recommandée ;
- les signaux ayant participé à la décision.

L'objectif est de permettre à un opérateur ou responsable maintenance de comprendre pourquoi une action est recommandée.

## API prédictive

Les principales API prédictives incluent notamment :

```text
POST /api/v1/equipments/{equipment_id}/health-score
POST /api/v1/equipments/{equipment_id}/rul
GET  /api/v1/equipments/{equipment_id}/predictions
```

## API recommandations

Génération d'une recommandation :

```text
POST /api/v1/equipments/{equipment_id}/recommendations
```

Cette opération :

- récupère les dernières prédictions disponibles ;
- génère une recommandation ;
- persiste la recommandation ;
- retourne la recommandation générée.

Historique :

```text
GET /api/v1/equipments/{equipment_id}/recommendations
```

Filtres supportés :

- `priority`
- `recommendation_type`
- `start_time`
- `end_time`

L'historique utilise la même convention de pagination que l'historique des prédictions.

## Principe REST

Une opération `GET` ne doit pas modifier l'état du système.

Par conséquent, `POST /recommendations` est utilisé pour générer et persister une nouvelle recommandation, tandis que `GET /recommendations` sert uniquement à consulter l'historique.

## Séparation ML / API

La logique ML ne doit jamais être directement implémentée dans les routes HTTP.

Flux recommandé :

```text
Route
→ Service
→ ML / Recommendation Engine
→ Repository
→ Database
```

Les composants ML doivent rester :

- testables indépendamment ;
- réutilisables ;
- découplés de FastAPI ;
- indépendants de la présentation frontend.

## Base de données

PostgreSQL est utilisé comme base principale.

Les migrations sont gérées par Alembic.

Principales entités persistées :

```text
companies
sites
equipments
sensors
measurements
maintenance_records
prediction_records
maintenance_recommendations
```

## Tests

Le backend utilise `pytest`.

Les tests couvrent notamment :

- repositories ;
- services ;
- API ;
- pipeline de données ;
- composants ML ;
- persistance des prédictions ;
- RUL ;
- moteur de recommandations ;
- historique et pagination.

Les tests nécessitant une base PostgreSQL réelle peuvent être marqués comme tests d'intégration et ignorés lorsqu'un environnement PostgreSQL n'est pas disponible.

## Principes d'évolution

Toute nouvelle fonctionnalité doit respecter :

```text
Route
→ Service
→ Repository
```

ou, pour les fonctionnalités prédictives :

```text
Route
→ Service
→ ML / Analytics
→ Repository
```

Les règles suivantes doivent être conservées :

- aucune logique métier dans les routes ;
- aucune logique HTTP dans les composants ML ;
- aucune duplication de logique métier ;
- tests obligatoires pour les nouvelles fonctionnalités ;
- migrations Alembic pour toute évolution de schéma ;
- contrats API stables sauf décision explicite ;
- séparation claire entre prédiction et recommandation ;
- persistance des résultats importants nécessaires à l'historisation.

## Responsabilité opérationnelle

Industrial Predict AI fournit une aide à la décision.

Les prédictions et recommandations ne provoquent pas automatiquement :

- l'arrêt d'un équipement ;
- la création d'un ordre de travail ;
- l'affectation d'un technicien ;
- l'exécution d'une maintenance.

La décision opérationnelle finale reste sous la responsabilité des utilisateurs autorisés.
