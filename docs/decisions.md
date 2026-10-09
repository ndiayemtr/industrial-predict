# Décisions techniques

## D001 - API

FastAPI est utilisé pour le backend.

## D002 - Base de données

PostgreSQL est la base principale.

## D003 - ORM

SQLAlchemy est utilisé avec Alembic pour les migrations.

## D004 - Architecture

Séparation :

Route
→ Service
→ Repository

## D005 - Multi-tenant

Les données doivent être isolées par `company_id`.

## D006 - Dashboard

Les agrégations complexes sont effectuées au niveau Repository.

## D007 - Machine Learning

Les composants ML doivent rester découplés des routes API.

## D008 - Tests

Toute nouvelle fonctionnalité importante doit être accompagnée de tests automatisés.
