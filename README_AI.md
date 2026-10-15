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

Le socle UI 1.1 à UI 1.8 est terminé et fusionné dans `main`.
Les quatre composants partagés et le Shell responsive accessible sont disponibles.
UI 2.1 à UI 2.8 sont terminées. Dashboard V1 est fusionné dans `main`
(commit de fusion `f3f6f2c`) et publié sur GitHub ; référence de livraison
`23e28e5`, identique à `origin/main` au contrôle du 15 octobre 2026.
Dashboard V1 consomme FastAPI via `/api/v1/dashboard` :
filtres UTC, références paginées, façade locale et cinq sections de présentation.
UI 2.8 est enregistrée dans `9ce0cac` ; la publication du code ne constitue
pas un déploiement de production. La phase UI 3 - Gestion des entreprises
(Companies) est au stade de l’analyse fonctionnelle et technique UI 3.1,
sur `feature/frontend-companies`, HEAD de départ `b7aac19`.
Le contrat vérifié, le MVP et le plan proposés figurent dans
`docs/etape-ui-3.1-companies.md` ; validation attendue avant UI 3.2.
Aucun code Companies n’est encore implémenté. La suppression en cascade est
proposée hors MVP et l’autorisation backend reste à renforcer.
Les autres pages métier restent des placeholders. Aucun identifiant d'entreprise
par défaut, polling ou donnée fictive n'est introduit dans le Dashboard.
Les décisions Dashboard V1 DASH-01 à DASH-06 figurent dans D014 de
`docs/decisions.md` ; le contrat consommé et l'architecture livrée sont décrits
dans `docs/frontend-architecture.md`. Ne pas étendre le Dashboard V1 aux
indicateurs ML : les fonctions backend correspondantes ne sont pas intégrées
à cette page. L'autorisation multi-entreprises n'est pas démontrée sur la route
Dashboard ; ne pas déclarer une préparation à la production SaaS multi-tenant.
La validation finale comprend 220 tests Angular et un build production réussis ;
zoom réel Dashboard 100 %, 200 % et 400 % validé manuellement par l’utilisateur.
Lecteur d’écran réel non testé. Le nettoyage typographique `23e28e5` remplace
90 tirets cadratins par des tirets simples dans 24 fichiers ; conserver cette convention.
Le bundle initial de 565,38 ko dépasse le warning de 500 ko, sans relèvement.

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
