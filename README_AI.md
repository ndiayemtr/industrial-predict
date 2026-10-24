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
Sites et Équipements sont intégrés dans `main` (référence locale `a76e49c`).
Sensors et Measurements MVP sont intégrés dans main local. Maintenance MVP de
consultation est implémenté sur feature/frontend-maintenance à d71774c et sa
livraison documentaire UI 8.7 est préparée. main local est à 74a24e4, origin/main
local à 15c956b, sans fetch. Prédictions et Recommandations restent des placeholders.
Aucun identifiant d'entreprise par défaut, polling ou donnée fictive n'est introduit.

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
Bundle initial historique Sites : 601,51 ko pour un budget de 500 ko, dont +32,48 ko après
intégration de NbToastrService ; aucun budget relevé. Zoom Companies 200/400 %
non validé, lecteur d'écran réel non testé et autorisation multi-entreprises non
démontrée. Companies n'est pas prêt pour une production SaaS multi-tenant.
Validation finale de livraison Companies : 386 tests Angular réussis, build production
réussi et `npm audit` sans vulnérabilité signalée. Ces résultats historiques
ne sont pas de nouvelles exécutions lors de la synchronisation documentaire.
Voir `docs/frontend-datetime-display.md` et `docs/dashboard-date-precision.md`.
UI 4 - Sites MVP est intégré dans `main` à `667fe5b` ; validation de référence `b3d0352`.
La [conception UI 4.1](docs/etape-ui-4.1-sites.md) reste la référence métier :
entreprise explicite, code unique globalement, PATCH différentiel sans company_id,
entreprise non transférable et aucun DELETE frontend. Liste/recherche/pagination,
détail, création, édition, navigation et notifications sont livrés dans `main`.
Les [preuves UI 4.7.4](docs/ui-4.7.4-real-sites-crud.md) complètent les simulations
par POST 201/PATCH 200 réels via Angular 4201 et FastAPI 8001 vers DEV :
persistance SQL, deux entreprises et quatre sites, seed de 36 lignes préservé.
La [clôture UI 4.7.5](docs/ui-4.7.5-sites-closure.md) fixe la référence à
583 tests Angular réussis avec deux workers et un build réussi, sans lever
la réserve sur le dialogue natif d'abandon. Le [statut Sites](docs/project-status.md#sites-mvp---livraison-préparée-ui-48)
centralise les limites et dettes, dont les secrets historiques suivis à externaliser
et à renouveler et l'absence actuelle d'authentification/autorisation multi-tenant.
UI 4.8 et sa [documentation de livraison](docs/ui-4.8-sites-delivery.md) sont enregistrées dans `667fe5b`.

UI 5 - Équipements MVP est intégré dans `main` à `a76e49c`. Sa validation
historique reste référencée par `39e2f0d`. Les décisions EQ-01 à EQ-07 de la [conception](docs/etape-ui-5.1-equipments.md)
sont approuvées : sélection entreprise/site, liste/recherche/filtres/pagination,
détail avec parents réels, liens Site/Équipements, création et édition différentielle.
Type libre, défauts operational/medium, aucun transfert ni DELETE frontend.
Boutons harmonisés et protections des formulaires livrés. Capteurs, maintenance,
prédictions, Health Score et RUL ne sont pas des écrans Équipements livrés.
Références historiques : 864 tests Angular / 49 fichiers, build réussi,
bundle initial 604,81 ko. [UI 5.7](docs/ui-5.7-equipments-integration.md) prouve
POST 201/PATCH 200 et persistance DEV, seed et données préexistantes préservés.
409/422 d'écriture et double soumission restent simulés ; dialogue natif réservé.
Le [statut Équipements](docs/project-status.md#équipements-mvp---livraison-préparée-ui-58)
centralise les limites : budget dépassé, secrets historiques à externaliser et
renouveler, absence d'authentification et d'autorisation multi-tenant.
[UI 5.8](docs/ui-5.8-equipments-delivery.md) a finalisé la documentation,
enregistrée dans `a76e49c`. Ses résultats restent historiques.

UI 6 - Sensors MVP est intégré dans `main` à `20293a4`.
SEN-01 à SEN-10 approuvées : sélection explicite entreprise/site/équipement,
liste avec recherche/statut/pagination serveur, détail et rattachement réel,
création, édition différentielle et navigation Equipment <-> Sensors. Code
unique globalement ; parent, type et unité immuables en édition, aucun DELETE
frontend ni mesure ou prédiction fictive. B-SEN-01 est corrigé dans `4defbe9`.
Le [statut Sensors](docs/project-status.md#sensors-mvp---livraison-préparée-ui-68)
centralise les références 1 179 tests/build/605,24 kB, les preuves réelles et
les réserves ouvertes. [UI 6.8](docs/ui-6.8-sensors-delivery.md) conserve
la préparation historique de livraison, enregistrée dans `20293a4`.

UI 7 - Measurements MVP, MES-01 à MES-12 approuvées, couvre liste/historique
paginés par capteur, quatre choix explicites et rattachements réels, cinq qualités
déclarées, périodes UTC [début, fin) avec calendrier/heure/fraction et détail
strictement en lecture seule. Microsecondes et offsets ISO préservés ; unité
actuelle issue du capteur, sans garantie historique. Navigation Sensor ->
Measurements et retours contextuels, actions harmonisées Equipment/Sensor/Measurement.
Le service Angular expose uniquement GET paginé et GET détail, aucun POST,
PATCH ou DELETE, polling, graphique ou prédiction fictive.
Le [statut Measurements](docs/project-status.md#measurements-mvp---livraison-préparée-ui-76)
centralise les références historiques : 1 482 tests, build production réussi,
bundle initial 605,65 kB, GET réels et SQL concordants, 40 lignes conservées et
empreintes des huit tables inchangées. Les réserves backend, seed, sécurité,
budget et couverture PostgreSQL demeurent. [UI 7.6](docs/ui-7.6-measurements-delivery.md)
conserve la préparation historique de livraison. Measurements et sa documentation
sont intégrés dans main local (15c956b), avant la conception Maintenance (74a24e4).

## UI 8 - Maintenance MVP de consultation, livraison préparée

MAIN-01 à MAIN-16 validées, lecture seule. Liste lazy, sélection explicite
Entreprise -> Site -> Équipement et rattachements vérifiés ; recherche, filtres,
période created_at [début, fin), microsecondes/offsets et pagination serveur.
Détail de 18 champs, coût sans devise supposée, indisponibilité déclarée et dates
administratives naïves sans Z ajouté. Navigation Equipment <-> Maintenance,
actions harmonisées et retour contextuel. Aucun POST/PATCH/DELETE ni transition ;
predictive n'est pas une preuve de prédiction IA.
Le [statut Maintenance](docs/project-status.md#maintenance-mvp---livraison-préparée-ui-87)
centralise 741 tests ciblés/1 899 tests Angular/build/606,00 kB historiques,
validation utilisateur 9/9 et recette UI 8.6 : 36 GET indépendants, 27 listes SQL,
30 états Angular, trois dossiers et 40 lignes préservées. B-MAIN-01 à 09, sécurité,
seed strict, budget et limites de preuve restent ouverts. Le
[dossier UI 8.7](docs/ui-8.7-maintenance-delivery.md) prépare la livraison en DEV,
sans aptitude déclarée à la production SaaS. Aucun test/build ou accès DEV relancé.
Commit et fusion attendent des autorisations distinctes ; UI 9 non commencée.

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
