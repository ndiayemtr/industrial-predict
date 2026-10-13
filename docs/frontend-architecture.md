# Frontend Architecture - Industrial Predict AI

## Objectif

Définir l'architecture frontend d'Industrial Predict AI et garantir une interface cohérente, maintenable et alignée avec les APIs backend.

## Stack

- Angular standalone
- TypeScript
- Nebular
- RxJS
- Angular Router
- HttpClient

## Structure générale

src/app/
├── core/
├── shared/
├── layout/
├── features/
│ ├── dashboard/
│ ├── companies/
│ ├── sites/
│ ├── equipments/
│ ├── sensors/
│ ├── measurements/
│ ├── maintenance/
│ ├── predictions/
│ └── recommendations/
└── app.routes.ts

## Navigation principale

- Dashboard
- Entreprises
- Sites
- Équipements
- Capteurs
- Mesures
- Maintenance
- Prédictions
- Recommandations
- Rapports
- Administration

## Pages prioritaires

### Dashboard

- KPI globaux
- état de santé des équipements
- risques de panne
- alertes critiques
- activité récente

### Équipements

- liste
- filtres
- Health Score
- Failure Risk
- RUL
- statut
- dernière maintenance

### Détail équipement

Onglets :

- Vue d'ensemble
- Capteurs
- Mesures
- Prédictions
- Recommandations
- Maintenance
- Documents

### Prédictions

- historique
- filtres
- pagination
- anomaly
- failure risk
- health score
- RUL

### Recommandations

- génération
- historique
- priorité
- type
- raison
- action recommandée
- signaux utilisés

## Architecture frontend

Page
→ Facade / Service
→ API Service
→ Backend FastAPI

Les composants visuels ne doivent pas contenir de logique métier complexe.

## Gestion API

Les appels HTTP sont centralisés dans des services dédiés.

Exemples :

- EquipmentApiService
- DashboardApiService
- PredictionApiService
- RecommendationApiService
- MaintenanceApiService

## États UI

Chaque écran doit gérer explicitement :

- loading
- success
- empty
- error

## Design System

### Couleurs fonctionnelles

- vert : normal / healthy
- jaune : vigilance
- orange : dégradation
- rouge : critique
- bleu : navigation / actions principales

### Principes

- interface professionnelle
- forte lisibilité
- informations critiques immédiatement visibles
- densité adaptée aux usages industriels
- cohérence entre tableaux, cartes et badges
- responsive desktop/tablette

## Composants partagés

Prévoir notamment :

- KPI Card
- Status Badge
- Priority Badge
- Health Score Gauge
- Risk Gauge
- RUL Indicator
- Empty State
- Loading State
- Error State
- Pagination
- Filter Bar

## Règles

1. Réutiliser les composants communs.
2. Ne pas dupliquer les appels API.
3. Ne pas mettre de logique métier complexe dans les composants.
4. Utiliser les types TypeScript correspondant aux schémas backend.
5. Respecter les contrats API existants.
6. Gérer loading, error et empty state.
7. Garder une navigation cohérente.
8. Concevoir les pages avant leur implémentation.

## Ordre d'implémentation

1. Layout global
2. Dashboard
3. Liste des équipements
4. Détail équipement
5. Prédictions
6. Recommandations
7. Maintenance
8. Autres modules
