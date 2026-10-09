# Industrial Predict AI - AI Context

## Projet

Industrial Predict AI est une plateforme SaaS de maintenance prédictive
et de gestion d'actifs industriels.

Secteurs visés :

- énergie
- pétrole et gaz
- ports
- transport
- industrie

## Objectif

Construire une plateforme professionnelle permettant notamment :

- gestion des entreprises, sites et équipements
- gestion des capteurs
- collecte de mesures
- suivi de maintenance
- tableaux de bord industriels
- détection d'anomalies
- prédiction du risque de panne
- Health Score des équipements
- maintenance prédictive

## Stack principale

### Backend

- Python 3.12
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pydantic

### Frontend

- Angular
- Nebular

### Machine Learning

- Python
- scikit-learn
- pipeline ML interne

## Règles de développement

1. Lire `docs/project-status.md` avant toute modification.
2. Lire `docs/architecture.md` avant toute modification structurelle.
3. Respecter l'architecture existante.
4. Ne pas dupliquer la logique métier.
5. Ne modifier que le périmètre demandé.
6. Ajouter ou mettre à jour les tests.
7. Lancer les tests après chaque implémentation.
8. Ne pas supprimer du code existant sans justification.
9. Ne pas modifier les contrats API existants sans demande explicite.
10. Ne pas effectuer de commit automatiquement sauf demande explicite.

## Méthode de travail

Analyse
→ Plan
→ Implémentation
→ Tests
→ Validation
→ Commit

Chaque fonctionnalité est développée étape par étape.
