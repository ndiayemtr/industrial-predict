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
- estimation du Remaining Useful Life (RUL)
- persistance et historique des prédictions
- recommandations de maintenance prédictive
- historique des recommandations

## Stack principale

### Backend

- Python 3.12
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pydantic

### Frontend

- Angular 21.2.25 standalone, TypeScript strict et Angular Router
- Nebular 17.0.0, Angular CDK 21.0.6, SCSS et Zone.js

Les contraintes de compatibilité et la correction Sass reproductible par
`postinstall` sont documentées dans `docs/decisions.md`.
Avant une modification frontend, lire également `docs/frontend-architecture.md`
et `docs/ui-design.md`.

La fondation UI 1.1 à UI 1.6 est terminée et fusionnée dans `main`.
UI 1.7 est terminée et commitée : les quatre composants partagés sont disponibles.
UI 1.8.1 à UI 1.8.3 sont validées ; UI 1.8.4 finalise la documentation et
la préparation du commit responsive, sans commit automatique. Les pages métier restent
des placeholders explicites, sans données fictives ni appels API.

### Machine Learning

- Python
- scikit-learn
- pipeline ML interne
- détection d'anomalies
- prédiction du risque de panne
- Health Score
- Remaining Useful Life (RUL)
- moteur de recommandations de maintenance

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
