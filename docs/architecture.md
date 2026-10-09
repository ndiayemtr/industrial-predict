# Architecture - Industrial Predict AI

## Vue générale

Frontend Angular
|
v
REST API FastAPI
|
+---- Services
|
+---- Repositories
|
v
PostgreSQL

        +
        |
        v

ML / Predictive Analytics

## Backend

app/
├── api/
│ └── routes/
├── models/
├── schemas/
├── repositories/
├── services/
├── core/
└── ml/

## Modèle métier

Company
└── Site
└── Equipment
├── Sensor
│ └── Measurement
└── MaintenanceRecord

## Principe

Les routes HTTP ne doivent pas contenir la logique métier.

Route
→ Service
→ Repository
→ Database

La logique ML doit également rester isolée de la couche API.
