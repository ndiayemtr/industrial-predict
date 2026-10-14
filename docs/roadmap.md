# Industrial Predict AI - Roadmap

## Phase 1 - Core Platform

[x] Database
[x] Company
[x] Site
[x] Equipment
[x] Sensor
[x] Measurement
[x] MaintenanceRecord
[x] Dashboard

## Phase 2 - Predictive Intelligence

[x] Anomaly Detection
[x] Failure Risk Model
[x] Health Score
[x] Predictions Persistence
[x] Remaining Useful Life
[x] Predictive Maintenance Recommendations

## Phase 3 - Frontend

### Fondation terminée et fusionnée dans main

- [x] UI 1.1 — Audit et architecture frontend
- [x] UI 1.2 — Initialisation Angular standalone
- [x] UI 1.3 — Thème global et Shell
- [x] UI 1.4 — Sidebar et navigation centralisée
- [x] UI 1.5 — Header global et finitions visuelles
- [x] UI 1.6 — Routing, 404, accessibilité et consolidation des tests

### UI 1.7 — Composants partagés terminés et commités

- [x] UI 1.7.0 — Synchronisation documentaire validée
- [x] UI 1.7.1 — Conception et contrats validés
- [x] UI 1.7.2 — PageHeader
- [x] UI 1.7.3 — LoadingState
- [x] UI 1.7.4 — EmptyState
- [x] UI 1.7.5 — ErrorState
- [x] UI 1.7.6 — Validation globale et visuelle ; démonstration retirée

Les quatre composants sont implémentés sous `shared/components/` et commités
dans `e3a2a2c`. Ils restent autonomes ; les pages métier sont des placeholders.

### UI 1.8 — Responsive et accessibilité terminés et fusionnés

- [x] UI 1.8.1 — Audit responsive global
- [x] UI 1.8.2 — Corrections responsive ciblées, validées et livrées dans `12a18c3`
- [x] UI 1.8.3 — Validation approfondie, avec zoom réel 100/200/400 % confirmé par l'utilisateur
- [x] UI 1.8.4 — Documentation et validation finale terminées ; commit `12a18c3`, fusion `acd872b`

La validation historique du socle comprend 116 tests Angular, 5 tests du correctif Sass
et un build production réussi. Le lecteur d'écran réel reste non testé.
L'avertissement de bundle (504,68 ko pour un budget de 500 ko) reste explicite,
sans relèvement de seuil.

### UI 2 — Dashboard frontend V1 et intégration API

- [x] UI 2.1 — Audit du contrat réel et conception frontend validés
- [ ] UI 2.1.1 — Synchronisation documentaire Dashboard V1 ; livrable en attente de validation
- [ ] UI 2.2 — DTO TypeScript et accès HTTP Dashboard
- [ ] UI 2.3 — Références et filtres accessibles
- [ ] UI 2.4 — Façade locale, page lazy et états UI
- [ ] UI 2.5 — Synthèse, équipements et capteurs
- [ ] UI 2.6 — Mesures et maintenance
- [ ] UI 2.7 — Validation intégrée, responsive et accessibilité
- [ ] UI 2.8 — Documentation finale et préparation de livraison

La conception est validée (D014, DASH-01 à DASH-06) ; **UI 2.2 n'est pas commencée**.
UI 2.1.1 ne crée aucun code, service, DTO, composant ou proxy. Les cinq sections
sont synthèse, équipements, capteurs, mesures et maintenance ; les prédictions
ML et l'affichage monétaire sont exclus de V1. Le backend local sur le port
8000 est confirmé par l'utilisateur ; le proxy sera implémenté ultérieurement.

#### Plan d'implémentation et critères de validation prévus

Les chemins ci-dessous sont relatifs à `frontend/` et désignent des fichiers
à créer ou adapter dans les missions futures, jamais des éléments déjà livrés.

| Étape | Fichiers / périmètre prévu | Tests attendus et critères d'acceptation |
| --- | --- | --- |
| UI 2.2 | `src/app/features/dashboard/models/`, `data-access/dashboard-api.service.ts`, `src/app/core/http/api-config.ts`, `src/app/app.config.ts` ; future configuration du proxy de développement | DTO conformes aux schémas et nullabilité ; GET sur `/api/v1/dashboard` ; paramètres obligatoires exacts, facultatifs omis ; `equipment_id` seul conservé ; dates avec fuseau ; erreurs HTTP 400/404/422/500 testées avec le contrôleur HTTP Angular ; proxy vers `127.0.0.1:8000` sans modification backend. Aucun KPI recalculé. |
| UI 2.3 | `src/app/core/api/reference-data-api.service.ts`, modèles de pagination/références, `features/dashboard/components/dashboard-filters/` | Pagination au-delà de la première page, recherche et dépendances des sélecteurs ; changement d'entreprise efface site/équipement, changement de site efface équipement ; sept jours glissants UTC à horloge contrôlée, bornes fixes après application ; dates invalides, fin exclusive et requête interdite tant que les filtres obligatoires manquent ; labels et clavier. |
| UI 2.4 | `features/dashboard/dashboard.facade.ts`, `pages/dashboard/`, adaptation de `src/app/app.routes.ts` | Une requête par application/actualisation, annulation des réponses obsolètes, invitation initiale, loading/empty/error/success, relance manuelle ; page lazy, titre Router conservé, un seul h1 et PageHeader ; skip link/focus du Shell préservés. |
| UI 2.5 | `features/dashboard/components/dashboard-kpi-card/`, `equipment-summary/`, `sensor-summary/` | Rendu des effectifs et ratios renvoyés, zéro distinct de null, catégories inconnues conservées ; libellés « État actuel » et « Sur la période » justes ; aucune santé ou prédiction inventée ; rendu responsive. |
| UI 2.6 | `features/dashboard/components/measurement-summary/`, `maintenance-summary/` | Bornes UTC, jours partiels et zéros quotidiens ; dernières mesures hors période ou absentes ; maintenance ouverte/current et terminée/période distinctes ; couvertures partielles, zéro/null, dates manquantes ; aucun coût monétaire affiché faute de devise. |
| UI 2.7 | Tests d'intégration Dashboard et validation navigateur ; ajustements ciblés seulement si défaut confirmé | Données réelles et erreurs réseau/serveur ; absence de doublons HTTP ; 1440/1024/1023/768/390/320 px, clavier, menu mobile, zoom, focus, console ; mesurer latence, poids initial et différé. Lecteur d'écran réel à tester si disponible, sinon limite explicite. |
| UI 2.8 | Documents de statut, architecture, UI et décisions si nécessaire | Documentation conforme au code livré et au contrat inchangé ; bilan des tests, tailles, avertissements et limites ; validation avant commit, aucune publication automatique. |

À chaque étape d'implémentation : `npm run build`, `npm test -- --watch=false`,
`npm ls --all`, `npm audit` et contrôles Sass pertinents. Préserver les tests
existants sans duplication, les budgets, les dépendances et le backend.
Le bundle de référence historique est 504,68 ko contre 500 ko d'avertissement ;
mesurer séparément le coût initial (dont la configuration HTTP) et celui du
Dashboard lazy, sans dépendre de noms de chunks hashés.

### Écrans métier restant à implémenter

La présence de routes et de placeholders ne signifie pas que les fonctionnalités
ci-dessous sont livrées ou connectées aux APIs.

[ ] Dashboard
[ ] Equipment monitoring
[ ] Alerts
[ ] Analytics
[ ] Predictive insights

## Phase 4 - Industrialisation

[ ] Authentication
[ ] RBAC
[ ] Multi-tenant security
[ ] Monitoring
[ ] Docker
[ ] CI/CD
[ ] Production deployment
