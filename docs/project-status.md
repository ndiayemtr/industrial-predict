# Industrial Predict AI - Project Status

## État général

Projet en développement actif.

## Branche actuelle

main

À mettre à jour à chaque changement de branche.

## Backend

FastAPI + PostgreSQL opérationnels.

CRUD terminés pour :

- Company
- Site
- Equipment
- Sensor
- Measurement
- MaintenanceRecord

## Dashboard

Étape 1.4.16 terminée.

Fonctionnalités principales :

- inventaire des actifs
- statut des équipements
- criticité
- couverture capteurs
- qualité des mesures
- activité des mesures
- maintenance
- downtime
- coûts
- filtres company/site/equipment/date

Tests Dashboard :

- 50 tests passés
- 0 échec
- 1 test PostgreSQL ignoré selon l'environnement

## Machine Learning

### 2.4 - Anomaly Detection

Statut : terminée et testée.

Fonctionnalités principales :

- détection statistique des anomalies
- Z-score classique et robuste
- Isolation Forest
- score d'anomalie unifié
- orchestration par capteur et équipement
- explication des anomalies

### 2.5 - Failure Risk Model

Statut : terminée et testée.

Fonctionnalités principales :

- génération des labels de panne
- préparation du dataset supervisé
- baseline classifier
- Random Forest
- évaluation du modèle
- score de risque
- niveaux de risque
- explication des prédictions

### 2.6 - Health Score

Statut : terminée et testée.

Fonctionnalités principales :

- Failure Health
- Anomaly Health
- Data Quality Health
- Maintenance Health
- agrégation pondérée
- classification du niveau de santé
- API Health Score par équipement

### 2.7 - Predictions Persistence

Statut : terminée et testée.

Fonctionnalités principales :

- enum PredictionType
- modèle SQLAlchemy PredictionRecord
- migration Alembic prediction_records
- schémas Pydantic
- PredictionRepository
- PredictionService
- persistance des anomalies
- persistance du Failure Risk
- persistance du Health Score
- historique des prédictions par équipement
- filtres par type, niveau, alerte et période
- pagination des prédictions

API :

- GET /api/v1/equipments/{equipment_id}/predictions

Tests Predictions Persistence :

- 44 tests passés
- 0 échec
- 1 test PostgreSQL ignoré selon l'environnement

Suite backend complète :

- 538 tests passés
- 0 échec
- 4 tests ignorés
- compileall app : OK

## Travail actuel

Étape 2.7 terminée.

## Prochaine action

Démarrer l'étape 2.8 - Remaining Useful Life.
