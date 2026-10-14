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

### UI 1.8 — Responsive et accessibilité en finalisation

- [x] UI 1.8.1 — Audit responsive global
- [x] UI 1.8.2 — Corrections responsive ciblées, validées et non commitées
- [x] UI 1.8.3 — Validation approfondie, avec zoom réel 100/200/400 % confirmé par l'utilisateur
- [ ] UI 1.8.4 — Documentation et validation finale ; livrable et commit en attente de validation

La validation actuelle comprend 116 tests Angular, 5 tests du correctif Sass
et un build production réussi. Le lecteur d'écran réel reste non testé.
L'avertissement de bundle (504,68 ko pour un budget de 500 ko) reste explicite,
sans relèvement de seuil.

### Prochaine phase — Dashboard frontend et intégration API

- [ ] Concevoir les écrans et contrats de consommation du Dashboard
- [ ] Implémenter les services HTTP/façades et intégrer les APIs existantes
- [ ] Réutiliser les composants partagés pour loading, empty et error
- [ ] Vérifier les données réelles, les erreurs, l'accessibilité et les tests

Cette phase n'est pas commencée ; aucun appel API n'est ajouté dans UI 1.8.4.

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
