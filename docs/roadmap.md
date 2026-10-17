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

- [x] UI 1.1 - Audit et architecture frontend
- [x] UI 1.2 - Initialisation Angular standalone
- [x] UI 1.3 - Thème global et Shell
- [x] UI 1.4 - Sidebar et navigation centralisée
- [x] UI 1.5 - Header global et finitions visuelles
- [x] UI 1.6 - Routing, 404, accessibilité et consolidation des tests

### UI 1.7 - Composants partagés terminés et commités

- [x] UI 1.7.0 - Synchronisation documentaire validée
- [x] UI 1.7.1 - Conception et contrats validés
- [x] UI 1.7.2 - PageHeader
- [x] UI 1.7.3 - LoadingState
- [x] UI 1.7.4 - EmptyState
- [x] UI 1.7.5 - ErrorState
- [x] UI 1.7.6 - Validation globale et visuelle ; démonstration retirée

Les quatre composants sont implémentés sous `shared/components/` et commités
dans `e3a2a2c`. Ils restent autonomes et sont désormais intégrés au Dashboard V1 ;
Companies les réutilise également ; les autres pages métier restent des placeholders.

### UI 1.8 - Responsive et accessibilité terminés et fusionnés

- [x] UI 1.8.1 - Audit responsive global
- [x] UI 1.8.2 - Corrections responsive ciblées, validées et livrées dans `12a18c3`
- [x] UI 1.8.3 - Validation approfondie, avec zoom réel 100/200/400 % confirmé par l'utilisateur
- [x] UI 1.8.4 - Documentation et validation finale terminées ; commit `12a18c3`, fusion `acd872b`

La validation historique du socle comprend 116 tests Angular, 5 tests du correctif Sass
et un build production réussi. Le lecteur d'écran réel reste non testé.
L'avertissement de bundle (504,68 ko pour un budget de 500 ko) reste explicite,
sans relèvement de seuil.

### UI 2 - Dashboard frontend V1 et intégration API clôturés

- [x] UI 2.1 - Audit du contrat réel et conception frontend validés
- [x] UI 2.1.1 - Synchronisation documentaire Dashboard V1 validée et commitée
- [x] UI 2.2 - DTO TypeScript, accès HTTP Dashboard et proxy développement
- [x] UI 2.3 - Références paginées et filtres accessibles
- [x] UI 2.4 - Façade locale, page lazy et états UI
- [x] UI 2.4.1 - Diagnostic de croissance du bundle ; lazy loading confirmé
- [x] UI 2.5 - Synthèse, équipements et capteurs (`b666d7d`)
- [x] UI 2.6 - Mesures et maintenance (`2a6116d`)
- [x] UI 2.7 - Validation intégrée terminée, avec limites réelles/simulées explicites
- [x] UI 2.7.1 - Formulation neutre de couverture (`956a0b4`), 220 tests Angular
- [x] UI 2.8 - Documentation et validation finale terminées (`9ce0cac`)
- [x] Fusion de `feature/frontend-dashboard` dans `main` (`f3f6f2c`)
- [x] Publication sur GitHub du code sur `main`, référence `23e28e5`
- [x] Nettoyage typographique : 90 tirets cadratins remplacés dans 24 fichiers (`23e28e5`)

La conception D014/DASH-01 à DASH-06 est implémentée. Les cinq sections livrées
sont synthèse, équipements, capteurs, mesures et maintenance ; les prédictions
ML et l'affichage monétaire sont exclus de V1. Le backend local sur le port
8000 est consommé via le proxy Angular de développement ; le reverse proxy
de production reste à configurer. UI 2.8 a uniquement modifié la documentation ;
la publication sur GitHub ne constitue pas un déploiement de production.

#### Découpage validé et critères de livraison

Les chemins ci-dessous sont relatifs à `frontend/`. UI 2.2 à UI 2.6 sont
implémentées ; UI 2.7 a validé ces critères avec la distinction réel/simulé
décrite dans project-status.md. UI 2.8 a finalisé les documents et relancé les contrôles.

| Étape | Fichiers / périmètre | Critères validés ou contrôle final |
| --- | --- | --- |
| UI 2.2 | `src/app/features/dashboard/models/`, `data-access/dashboard-api.service.ts`, `src/app/core/http/api-config.ts`, `src/app/app.config.ts`, `proxy.conf.json` et angular.json | DTO conformes aux schémas et nullabilité ; GET sur `/api/v1/dashboard` ; paramètres obligatoires exacts, facultatifs omis ; `equipment_id` seul conservé ; dates avec fuseau ; erreurs HTTP 400/404/422/500 testées avec le contrôleur HTTP Angular ; proxy développement vers `127.0.0.1:8000` sans modification backend. Aucun KPI recalculé. |
| UI 2.3 | `src/app/core/api/reference-data-api.service.ts`, modèles de pagination/références, `features/dashboard/components/dashboard-filters/` | Pagination multipage simulée et paramètre search du service testé (aucun champ de recherche UI) ; cascade des sélecteurs, changement d'entreprise efface site/équipement, changement de site efface équipement ; sept jours glissants UTC à horloge contrôlée, bornes fixes après application ; dates invalides, fin exclusive et requête interdite tant que les filtres obligatoires manquent ; labels et clavier. |
| UI 2.4 | `features/dashboard/dashboard.facade.ts`, `pages/dashboard/`, adaptation de `src/app/app.routes.ts` | Une requête par application/actualisation, annulation des réponses obsolètes, invitation initiale, loading/empty/error/success, relance manuelle ; page lazy, titre Router conservé, un seul h1 et PageHeader ; skip link/focus du Shell préservés. |
| UI 2.5 | `features/dashboard/components/dashboard-kpi-card/`, `equipment-summary/`, `sensor-summary/` | Rendu des effectifs et ratios renvoyés, zéro distinct de null, catégories inconnues conservées ; libellés « État actuel » et « Sur la période » justes ; aucune santé ou prédiction inventée ; rendu responsive. |
| UI 2.6 | `features/dashboard/components/measurement-summary/`, `maintenance-summary/` | Bornes UTC, jours partiels et zéros quotidiens ; dernières mesures hors période ou absentes ; maintenance ouverte/current et terminée/période distinctes ; couvertures partielles, zéro/null, dates manquantes ; aucun coût monétaire affiché faute de devise. |
| UI 2.7 | Audit et suites existantes, validation navigateur ; UI 2.7.1 a corrigé uniquement la formulation de couverture | PETROSEN et GET backend réels ; erreurs UI/réseau/serveur et absence de doublons HTTP simulées ; six largeurs CSS, clavier, menu mobile, focus, console et bundle contrôlés. Zoom réel Dashboard 100/200/400 % validé manuellement par l'utilisateur, confirmé en UI 2.8. Aucune mesure de charge à grande échelle ; lecteur d'écran réel non testé. |
| UI 2.8 | Documents de statut, architecture, UI et décisions si nécessaire | Documentation conforme au code livré et au contrat inchangé ; bilan des tests, tailles, avertissements et limites validé et commité dans `9ce0cac`, puis fusionné dans `main`. |

À chaque étape d'implémentation : `npm run build`, `npm test -- --watch=false`,
`npm ls --all`, `npm audit` et contrôles Sass pertinents. Préserver les tests
existants sans duplication, les budgets, les dépendances et le backend.
Le bundle historique du socle est 504,68 ko. À la clôture UI 2.8, Dashboard était à
565,38 ko initial pour un budget warning de 500 ko ; référence différée UI 2.6
52,00 ko, 51,98 ko après UI 2.7.1. Angular Forms partagé avec Nebular explique
l'essentiel de la hausse UI 2.4 ; aucun seuil relevé. Mesurer initial et différé
séparément, sans dépendre des noms hashés. 220 tests Angular et 5 tests du
correctif Sass réussis ; bilan final UI 2.8 dans project-status.md.

UI 2.7 a confronté PETROSEN réel à FastAPI et vérifié la fin exclusive,
les relevés hors période, le clavier et six largeurs CSS. Les états UI error/retry,
empty, courses de requêtes, pagination multipage et couvertures partielles sont
simulés. Zoom réel du socle 100/200/400 % confirmé historiquement par l'utilisateur ;
zoom réel Dashboard **100/200/400 % validé manuellement par l'utilisateur**,
confirmation reçue en UI 2.8, distincte des essais du navigateur intégré.
Lecteur d'écran réel non testé. Autorisation multi-entreprises non démontrée :
pas de déclaration de préparation à la production SaaS multi-tenant.

### UI 3 - Companies MVP terminé, fusionné et publié

- [x] UI 3.1 - Conception fonctionnelle et technique validée (`d6d31ec`)
- [x] UI 3.2 - DTO et service HTTP Companies (`07d2bc3`)
- [x] UI 3.3 - Liste, recherche serveur et pagination (`84f7f18`)
- [x] UI 3.4 - Détail entreprise (`a1e332e`)
- [x] UI 3.5 - Création avec formulaire partagé (`d8e6c48`)
- [x] UI 3.6 - Modification par PATCH différentiel (`ab99551`)
- [x] UI 3.6.1 - Notifications Nebular après création/modification (incluses dans `ab99551`)
- [x] UI 3.7 - Validation intégrée, lectures FastAPI réelles et écritures simulées
- [x] UI 3.7.1 - Diagnostic de stabilité validé, rapport commité (`ac2dc3a`)
- [x] UI 3.8 - Documentation finale terminée (`a495f90`)
- [x] Fusion de `feature/frontend-companies` dans `main` (`537822c`), code publié
- [x] Formatage des dates Dashboard et Companies, filtres simples et précision avancée (`9c183e0`)
- [x] Publication de la finition des dates dans `main`, référence `2c49c4f`

État contrôlé le 16 octobre 2026 : branche `main`, HEAD publié `2c49c4f`,
synchronisé avec `origin/main`, dépôt propre avant synchronisation documentaire.
La conception d'origine est conservée
dans [etape-ui-3.1-companies.md](etape-ui-3.1-companies.md), avec renvoi vers
l'implémentation actuelle. Le [bilan Companies](project-status.md#companies-mvp---validation-historique-ui-37)
distingue les observations réelles des simulations : liste/détail/recherche
FastAPI réels ; POST/PATCH, erreurs d'écriture et pagination multipage simulés.
Le responsive des quatre parcours a été contrôlé aux six largeurs CSS prévues ;
zoom Companies 200/400 % non validé, lecteur d'écran réel non testé.

[UI 3.7.1](ui-3.7.1-test-stability.md) : trois suites complètes séquentielles
à 348/348, 31 fichiers, et six tests 404 réussis dans neuf lancements. Le défaut
initial « neuf liens attendus, zéro reçu » reste non reproduit. Des timeouts
Sidebar/Shell sous concurrence sont observés ; aucun correctif de synchronisation
spéculatif n'est appliqué. Exécuter les validations de livraison séquentiellement.
Build production, cinq tests Sass et contrôles des breakpoints/thème réussis
historiquement ; aucune suite applicative relancée dans UI 3.8 documentaire.

Validation finale après finition des dates : **386 tests Angular réussis**,
build production réussi et `npm audit` sans vulnérabilité signalée. Ces résultats
de livraison ne sont pas de nouvelles exécutions documentaires. Voir les rapports
[dates Dashboard et Companies](frontend-datetime-display.md) et
[précision des filtres](dashboard-date-precision.md). Le mode simple saisit les
minutes ; le mode avancé conserve secondes et millisecondes, avec confirmation
explicite en cas de conversion vers la minute. Les bornes UTC sont préservées.

Dette actuelle : 601,51 ko initial pour un budget de 500 ko, dont +32,48 ko après
intégration de NbToastrService ; dépassement 101,51 ko, seuils inchangés.
Liste/détail/formulaire Companies restent différés. DELETE est exclu du MVP à
cause de la cascade. L'autorisation multi-entreprises reste non démontrée ;
le module n'est pas prêt pour une production SaaS multi-tenant. Les écritures
réelles POST/PATCH restent non testées de bout en bout.

### UI 4 - Sites industriels, conception fonctionnelle validée

- [x] UI 4.1 - Analyse et conception fonctionnelle validées, [rapport](etape-ui-4.1-sites.md), commit `1630ebc`
- [x] UI 4.2 - DTO et intégration HTTP validés, [bilan](ui-4.2-sites-data-access.md), commit `cd2389d`
- [x] UI 4.3 / UI 4.3.1 - Liste, recherche, pagination et finitions UX livrées, [bilan](ui-4.3-sites-list.md), commit `43f72f8`
- [x] UI 4.4 et finitions UI 4.4.1 à UI 4.4.3 - Détail et libellés métier, [bilan](ui-4.4-site-detail.md), commit `491cb24`
- [x] UI 4.5 et finitions - Création Site commitée dans `e8702b0`, [bilan](ui-4.5-site-create.md), écritures simulées uniquement
- [x] UI 4.6 - Modification Site validée, [bilan](ui-4.6-site-edit.md), sans transfert d'entreprise
- [ ] Étapes suivantes - Suivre le découpage de la conception et les validations correspondantes

### Écrans métier restant à implémenter

La présence de routes et de placeholders ne signifie pas que les fonctionnalités
ci-dessous sont livrées ou connectées aux APIs.

[x] Dashboard V1 livré, fusionné dans `main` et publié sur GitHub
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
