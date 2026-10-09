# Industrial Predict AI - Project Status

## État général

Projet en développement actif.

## Branche actuelle

feature/2.6-health-score

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

### 2.4

Détection d'anomalies
Statut : terminée

### 2.5

Failure Risk Model
Statut : implémenté et testé

Commits principaux :

- modèle de risque de panne
- tests automatisés du modèle

## Travail actuel

### 2.6 - Health Score

Objectif :
Calculer un score de santé synthétique d'un équipement
à partir des données disponibles.

## Prochaine action

Définir précisément :

- formule du Health Score
- variables utilisées
- pondérations
- niveaux de santé
- API d'exposition du score
- tests
