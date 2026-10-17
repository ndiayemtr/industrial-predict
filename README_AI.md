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

L'environnement permanent de développement utilise `industrial_predict_dev` sur
`127.0.0.1:5434`, FastAPI sur `8001` et Angular sur `4201`.
Utiliser les [lanceurs dédiés et leurs contrôles de cible](infra/development/README.md).
Les services historiques et leurs données sont conservés ; aucun repli vers
l'API historique sur `8000` n'est permis par ce lancement.

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
pas un déploiement de production. UI 3 Companies MVP est terminée, fusionnée
dans `main` via `537822c` et publiée : liste, recherche serveur nom/code, pagination,
détail, création, modification et notifications `NbToastrService`.
UI 3.1 à UI 3.8 sont terminées. La finition transversale des dates Dashboard et
Companies est également livrée, avec les filtres Dashboard en mode simple à la
minute ou en précision avancée (secondes et millisecondes), sans conversion
silencieuse. Référence publiée : `2c49c4f`, fusion de
`fix/frontend-datetime-display`, identique à `origin/main` au contrôle du
16 octobre 2026. Publication du code et déploiement de production restent distincts.
Le contrat initial reste dans `docs/etape-ui-3.1-companies.md` ; l'architecture
réellement livrée et le bilan sont dans `docs/frontend-architecture.md` et
`docs/project-status.md`. DELETE est exclu du MVP en raison de la cascade.
Les lectures FastAPI ont été contrôlées en UI 3.7 ; POST/PATCH sont implémentés
mais validés par simulation, sans écriture réelle dans PostgreSQL.
Les autres pages métier restent des placeholders. Aucun identifiant d'entreprise
par défaut, polling ou donnée fictive n'est introduit dans le Dashboard.
Les décisions Dashboard V1 DASH-01 à DASH-06 figurent dans D014 de
`docs/decisions.md` ; le contrat consommé et l'architecture livrée sont décrits
dans `docs/frontend-architecture.md`. Ne pas étendre le Dashboard V1 aux
indicateurs ML : les fonctions backend correspondantes ne sont pas intégrées
à cette page. L'autorisation multi-entreprises n'est pas démontrée sur la route
Dashboard ; ne pas déclarer une préparation à la production SaaS multi-tenant.
La validation historique Dashboard comprend 220 tests Angular et un build production réussis ;
zoom réel Dashboard 100 %, 200 % et 400 % validé manuellement par l’utilisateur.
Lecteur d’écran réel non testé. Le nettoyage typographique `23e28e5` remplace
90 tirets cadratins par des tirets simples dans 24 fichiers ; conserver cette convention.
La référence Companies UI 3.7.1 comprend trois suites complètes à 348/348 tests
(31 fichiers), build production et contrôles Sass réussis. Le défaut 404
« neuf liens attendus, zéro reçu » n'est pas reproduit ; les timeouts sous
concurrence justifient des validations séquentielles, sans correctif spéculatif.
Voir `docs/ui-3.7.1-test-stability.md`. Ces tests ne sont pas relancés en UI 3.8.
Bundle initial actuel : 601,51 ko pour un budget de 500 ko, dont +32,48 ko après
intégration de NbToastrService ; aucun budget relevé. Zoom Companies 200/400 %
non validé, lecteur d'écran réel non testé et autorisation multi-entreprises non
démontrée. Companies n'est pas prêt pour une production SaaS multi-tenant.
Validation finale de livraison : 386 tests Angular réussis, build production
réussi et `npm audit` sans vulnérabilité signalée. Ces résultats historiques
ne sont pas de nouvelles exécutions lors de la synchronisation documentaire.
Voir `docs/frontend-datetime-display.md` et `docs/dashboard-date-precision.md`.
UI 4 - Sites industriels : [conception UI 4.1](docs/etape-ui-4.1-sites.md)
validée fonctionnellement et commitée dans `1630ebc` sur `feature/frontend-sites`.
La couche de données UI 4.2 est validée et commitée dans `cd2389d` ;
[bilan UI 4.2](docs/ui-4.2-sites-data-access.md). La liste `/sites` UI 4.3 et ses
finitions UI 4.3.1 sont livrées dans `43f72f8` ; [bilan UI 4.3](docs/ui-4.3-sites-list.md).
La [fiche détail Sites UI 4.4 et ses finitions](docs/ui-4.4-site-detail.md) sont
commitées dans `491cb24`, avec retour au contexte de liste et libellés métier.
La [création Sites UI 4.5 et ses finitions](docs/ui-4.5-site-create.md) sont
commitées dans `e8702b0` : entreprise vérifiée explicitement, formulaire accessible,
POST simulé en validation et confirmation après navigation.
La [modification Sites UI 4.6](docs/ui-4.6-site-edit.md) est validée :
entreprise en lecture seule, PATCH différentiel sans company_id, dates de suivi
hors FormGroup et confirmation après navigation. Suppression et transfert exclus.
Les parcours HTTP de création/modification sont validés par simulation.

La [sécurisation UI 4.6.2](docs/ui-4.6.2-site-code-simulation.md) est validée :
non-régression du code métier et simulateur HTTP isolé en mémoire, sans upstream.
UI 4.7.2 et UI 4.7.2.1 sont validées : environnement permanent local
[DEV](infra/development/README.md), distinct de la base historique, sans repli sur 8000.

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
