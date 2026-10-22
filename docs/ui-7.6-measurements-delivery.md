# UI 7.6 - Documentation et préparation de livraison Measurements

22 octobre 2026. Branche feature/frontend-measurements, HEAD attendu et vérifié
43d12fa. Dépôt propre au démarrage. Les étapes UI 7.5, UI 7.5.1 et UI 7.5.2 sont
validées et enregistrées dans ce commit. Le présent dossier prépare la livraison
vers main ; il ne constitue ni une fusion ni une autorisation de production.

## 1. Intervention documentaire

Seuls six documents de suivi sont actualisés et ce rapport est créé :

| Document | Actualisation utile |
| --- | --- |
| [README_AI.md](../README_AI.md) | Contexte actuel : Sensors intégré dans main, Measurements implémenté, lecture seule et prochaine validation |
| [frontend/README.md](../frontend/README.md) | Routes, usage, transport GET, temps précis, navigation, références historiques et liens de livraison |
| [project-status.md](project-status.md#measurements-mvp---livraison-préparée-ui-76) | Statut central, références, preuves et réserves Measurements ; branche/main actualisés |
| [roadmap.md](roadmap.md) | UI 7.1 à UI 7.5 validées, UI 7.6 préparée, fusion en attente, UI 8 non commencée |
| [architecture.md](architecture.md) | Flux de lecture et frontière avec les contrats backend, sécurité et fonctions IA |
| [frontend-architecture.md](frontend-architecture.md#measurements-mvp---architecture-implémentée-ui-7) | Structure, routes, modèles, façade, contrôles temporels, contexte et styles réellement livrés |
| Ce rapport | Périmètre, audit Git, inventaire et checklist de fusion |

Les rapports historiques [UI 7.1](etape-ui-7.1-measurements.md),
[UI 7.2](ui-7.2-measurements-data-access.md),
[UI 7.3 et UI 7.3.1](ui-7.3-measurements-list.md),
[UI 7.4](ui-7.4-measurement-detail.md) et
[UI 7.5, UI 7.5.1 et UI 7.5.2](ui-7.5-measurements-integration.md) sont relus et
préservés sans changement. Les rapports Sensors et étapes antérieures restent
intacts. Les statuts anciens de ces rapports décrivent leur date d'intervention ;
ils ne remplacent pas le statut courant centralisé dans project-status.md.

Aucune modification de source exécutable, de backend, schéma SQL, migration,
Docker, package ou budget Angular. Aucun test, build, serveur, requête API,
navigateur ou accès PostgreSQL exécuté pendant UI 7.6. Les contrôles de cette
étape sont exclusivement documentaires et Git.

## 2. Périmètre fonctionnel livré sur la branche

### Historique par capteur

- /measurements charge la liste lazy dans le Shell, avec sélection explicite
  Entreprise -> Site -> Équipement -> Capteur, sans premier choix automatique.
- Catalogues paginés de 50 et Charger la suite ; vérification de chaque id/FK
  de Sensor -> Equipment -> Site -> Company. Aucun GET liste Measurements avant
  résolution complète, aucun fallback global si le contexte est incohérent.
- Historique paginé serveur, page 1/taille 20 par défaut, choix 20/50/100 et
  tailles d'URL valides 1..100. Tri réel timestamp DESC puis id DESC ; pas de
  recherche, tri local, agrégat ou chargement de tout l'historique inventé.
- Cinq qualités déclarées : good Bonne, suspect Suspecte, bad Mauvaise,
  missing Manquante et estimated Estimée. Toutes omet le filtre ; aucune valeur
  suspecte, manquante ou invalide n'est remplacée silencieusement par zéro.
- Périodes UTC [début, fin), début inclus et fin exclue. Calendrier natif, heure
  avec secondes et fraction facultative jusqu'à six chiffres. Application explicite,
  bornes facultatives séparément, intervalle incohérent bloqué sans lecture élargie.
- ISO source, offsets et microsecondes conservés à l'API et dans l'URL. Affichage
  UTC explicite sans Date/toISOString ni troncature à la milliseconde. Brouillon
  indépendant des filtres appliqués et valeur restaurée conservant sa chaîne initiale.
- États sélection attendue, chargement, historique vide, aucun résultat filtré,
  page hors plage et erreurs séparés. Reprise de page manuelle et annulation des
  requêtes obsolètes lors des changements rapides de périmètre.

### Détail et navigation

- /measurements/:measurementId affiche les cinq champs réels id, sensor_id,
  timestamp, value et quality, avec ISO source et valeur sans arrondi arbitraire.
- Références Measurement -> Sensor -> Equipment -> Site -> Company réellement
  chargées. Erreur de référence distincte ; données Measurement préservées si un
  parent est inaccessible. Unité actuelle du capteur, sans garantie historique.
- Sensor -> Voir les mesures seulement après résolution des quatre références.
  URL avec les quatre ids réels, page=1 et page_size=20, sans filtre search/status
  Sensors ni qualité/période implicite. Retour et Modifier Sensor préservés.
- Liste -> détail -> retour conserve les filtres appliqués, bornes précises,
  parents, page/taille et fragment. Le retour Sensor utilise un contexte distinct
  valide ou les parents réels, sans returnUrl externe ni rattachement supposé.
- Actions Equipment/Sensor/Measurement fondées sur la mixin existante
  navigation-action et les interactions _buttons.scss : secondaires, Modifier
  Sensor primaire bleu, focus, transitions, actif et mouvement réduit. Le retour
  Equipment historique garde son interligne local, comme documenté en UI 7.5.2.

### Limites intentionnelles du MVP

MeasurementsApiService expose uniquement GET /api/v1/measurements paginé avec
sensor_id obligatoire côté Angular et GET /api/v1/measurements/{id}. Query limitée
à sensor_id/page/page_size/quality/start_time/end_time. Aucun parent company/site/
equipment, unité, search ou sort vers cette API. Les deux lectures spécialisées
backend par capteur ne sont pas interchangeables et ne sont jamais substituées
au paginé. Pas de DTO ou méthode d'écriture frontend Measurements.

Aucun POST, PATCH ou DELETE Measurements, création manuelle, modification,
transfert ou nettoyage de doublons. Aucune mesure temps réel, polling, graphique,
anomalie calculée, prédiction, Health Score ou RUL fictifs. Le ML backend et les
agrégats Dashboard ne deviennent pas des écrans Measurements livrés par cette
étape. Maintenance, Prédictions et Recommandations restent des placeholders.

## 3. Références de validation historiques, non relancées

| Preuve antérieure | Résultat de référence | Source |
| --- | --- | --- |
| Suite finale UI 7.5.2 | 1 482 tests Angular réussis, 66 fichiers ; 256 ciblés dans six fichiers | [UI 7.5, section 11](ui-7.5-measurements-integration.md#11-ui-752---harmonisation-des-actions-de-détail) |
| Build production final | Réussi, bundle initial 605 652 octets, soit 605,65 kB | Même section ; budgets inchangés |
| Dépassement initial | 105,65 kB au-dessus du warning de 500 kB | Même section ; aucune correction artificielle de budget |
| Recette DEV UI 7.5 | GET réels Angular 4201 -> FastAPI 8001 -> industrial_predict_dev sur 5434, rôle ui47_app, HTTP 200 corroboré et SQL/DOM concordants | [UI 7.5, sections 1 à 7](ui-7.5-measurements-integration.md) |
| Temps et filtres réels | Fenêtre d'une microseconde, début inclus/fin exclue, qualités présentes, détail et retour avec page/qualité/période conservés | Même rapport, sections 4 à 6 |
| Intégrité réelle | 40 lignes préservées ; compteurs et empreintes SHA-256 des huit tables, plus empreintes individuelles, inchangés avant/après | Même rapport, sections 7 et 10 |
| Navigation ajoutée | Sensor -> Measurements, quatre ids réels et page 1/taille 20, sans filtres Sensors ; focus et navigation DEV | Même rapport, sections 10 et 11 |

Les 40 lignes comprennent companies 2, sites 4, equipments 6, sensors 7,
measurements 18, maintenance_records 3, prediction_records 0 et
maintenance_recommendations 0. Les 39 lignes initiales et le capteur fictif UI 6.7
sont conservés. Ces compteurs proviennent des instantanés historiques, pas d'une
lecture effectuée aujourd'hui pour UI 7.6. Aucune nouvelle vérification du seed.

L'inventaire UI 7.5 relève 16 URL XHR distinctes, dédupliquées. Les statuts/corps
sont corroborés par GET indépendants sur les URL effectivement observées et
comparés aux SELECT SQL ; ne pas présenter cela comme une interception HAR
exhaustive. UI 7.5.1 ajoute sa propre preuve de navigation et de conservation.

Erreurs réseau/400/404/422, parents absents ou incohérents, réponses obsolètes,
valeurs hors contrat et doubles navigations sont notamment couverts par HTTP
simulé Angular. Les réponses DEV consultées reviennent en Z ; offsets non nuls
et affichage d'une ligne missing sont validés par simulation. Les qualités good,
suspect, bad et estimated existent réellement, missing seulement en filtre vide.
La précision float déjà perdue côté serveur ou JSON ne peut pas être reconstruite.

Responsive historique : 1440, 1024, 1023, 768, 320 px et encadrement 389/391 pour
390, sans débordement global. Pas de validation exacte à 390 revendiquée.
Captures desktop/mobile et styles calculés examinés en UI 7.5.2 ; échecs ou
retards de capture sous viewport imposé documentés. Hover/active maintenus et
reduced-motion ne sont pas présentés comme des captures de pseudo-états réels.
Ces captures et traces sont locales et ignorées, elles ne sont pas embarquées
par ce dossier Git ; leurs liens de preuve restent dans les rapports historiques.

## 4. Limites et dettes techniques ouvertes

Le [statut central](project-status.md#réserves-et-dettes-measurements-ouvertes)
détaille les risques sans dupliquer l'audit backend :

| Réserve | Limite à conserver avant fusion et exploitation |
| --- | --- |
| B-MES-01 | Bornes inclusives/exclusives, fuseaux, tris et erreurs divergent entre endpoints ; seuls paginé et détail retenus sont exposés |
| B-MES-02 | Valeurs non finies et coercitions backend ; garde Angular sans correction du contrat serveur ni garantie de validité physique |
| B-MES-03 | Écarts Pydantic/SQL, null et omission, ids positifs ; pas de correction de schéma ou d'écriture |
| B-MES-04 | IntegrityError/concurrence, doublons, idempotence et correction auditée à traiter séparément |
| B-MES-05 | Authentification et isolation multi-tenant absentes ; rattachement correct ne vaut pas autorisation de ressource |
| B-MES-06 | COUNT/offset, grandes périodes et pages mouvantes ; charge/concurrence non mesurées en réel |
| B-MES-07 | Unité actuelle, aucune garantie de snapshot historique ; mutations Sensor hors UI possibles |
| B-SEN-02/03 | Validations, intégrité et concurrence Sensors non corrigées par Measurements |
| Seed strict | Capteur 1 conserve description Capteur fictif et updated_at 2026-10-20 22:11:55.315993, contre Capteur fictif. et 2026-10-16T12:00:00 attendus ; check strict non conforme, non déclaré réussi |
| Dialogue natif | beforeunload/abandon des modules d'écriture concernés non vérifié manuellement ; pas de formulaire métier Measurements |
| Bundle | Initial 605,65 kB, budgets inchangés, optimisation séparément autorisée |
| PostgreSQL | Couverture spécifique incomplète ; recette DEV ne remplace pas des tests isolés exhaustifs des contraintes, non-finis et concurrence |
| Accessibilité | Réserve 390 exact, captures de certains états et audit lecteur d'écran non exhaustifs |
| Secrets historiques | Dette projet déjà signalée : externalisation/renouvellement séparés ; aucun secret nouveau dans le diff Measurements |

F-MES-01 (temps précis frontend) est traité pour Measurements en UI 7.2/7.3.1/7.4.
Cela ne corrige ni B-MES-01 ni les dates des autres modules. Aucun risque backend
n'est masqué par l'absence d'écriture frontend. Cette livraison n'est pas une
validation de production SaaS multi-tenant.

## 5. Comparaison Git locale avant livraison

Contrôle au HEAD 43d12fa, sans fetch : main et la référence locale origin/main
valent 20293a4, également merge-base. main est ancêtre de la branche : zéro
commit de retard, cinq commits en avance. Aucun historique divergent constaté
localement ; aucun rebase, merge, mise à jour distante ou opération de publication.
L'état distant courant n'est pas établi par cette comparaison locale.

| Commit à intégrer, ordre chronologique | Périmètre |
| --- | --- |
| 19b64e2 | docs(frontend): design Measurements read-only MVP |
| 4b34f67 | feat(frontend): add Measurements data models and API integration |
| bbd18d6 | feat(frontend): implement Measurements list and UTC filters ; comprend UI 7.3.1 |
| 7b1265a | feat(frontend): implement Measurement detail and navigation |
| 43d12fa | feat(frontend): complete Measurements integration and detail actions ; comprend UI 7.5.1/7.5.2 |

Diff main...HEAD avant UI 7.6 : **36 fichiers**, dont **28 ajouts et 8 modifications**,
3 733 insertions et 13 suppressions. Répartition : cinq rapports, 22 fichiers de
feature Measurements, cinq fichiers Sensor Detail et quatre fichiers transversaux
routage/tests/styles. Le futur commit documentaire ajouterait les six documents
actualisés et ce rapport, soit un périmètre cumulé attendu de **43 fichiers**.
Ce commit n'est ni créé ni inclus dans les cinq commits ci-dessus.

### Revue des éléments transversaux

- app.routes.ts ajoute le loadChildren de MEASUREMENT_ROUTES à la place du
  placeholder ; Shell, autres routes et titres existants sont conservés.
- app.routes.spec.ts et sidebar.component.spec.ts retirent l'attente de placeholder
  Measurements, complétée par les tests de routes de la feature. Les trois autres
  placeholders restent couverts ; aucune fonctionnalité n'est retirée.
- Les quatre composants PageHeader/LoadingState/EmptyState/ErrorState sont
  réutilisés sans changement de contrat ni modification de leurs sources.
- _buttons.scss ajoute seulement sensor-back, measurement-back et
  sensor-measurements aux sélecteurs secondaires/communs et mouvement réduit.
  Aucune modification de tokens, thème, budgets ou mixin _actions.scss.
- Sensor Detail ajoute la navigation fondée sur ses références déjà résolues,
  sans changer le calcul du contexte de retour ou les lectures des parents.
  Le SCSS remplace le bloc local de retour par la mixin partagée, conservant
  Voir les mesures secondaire et Modifier primaire ; pas de changement Equipment.

### Inventaire exact des 36 fichiers déjà commités

A = ajouté, M = modifié, comparaison main...43d12fa. Les liens désignent les
sources courantes ; ils n'impliquent pas de modification dans UI 7.6.

| État | Fichier |
| --- | --- |
| A | [docs/etape-ui-7.1-measurements.md](../docs/etape-ui-7.1-measurements.md) |
| A | [docs/ui-7.2-measurements-data-access.md](../docs/ui-7.2-measurements-data-access.md) |
| A | [docs/ui-7.3-measurements-list.md](../docs/ui-7.3-measurements-list.md) |
| A | [docs/ui-7.4-measurement-detail.md](../docs/ui-7.4-measurement-detail.md) |
| A | [docs/ui-7.5-measurements-integration.md](../docs/ui-7.5-measurements-integration.md) |
| M | [frontend/src/app/app.routes.spec.ts](../frontend/src/app/app.routes.spec.ts) |
| M | [frontend/src/app/app.routes.ts](../frontend/src/app/app.routes.ts) |
| A | [frontend/src/app/features/measurements/data-access/measurements-api.service.spec.ts](../frontend/src/app/features/measurements/data-access/measurements-api.service.spec.ts) |
| A | [frontend/src/app/features/measurements/data-access/measurements-api.service.ts](../frontend/src/app/features/measurements/data-access/measurements-api.service.ts) |
| A | [frontend/src/app/features/measurements/measurements-list.facade.spec.ts](../frontend/src/app/features/measurements/measurements-list.facade.spec.ts) |
| A | [frontend/src/app/features/measurements/measurements-list.facade.ts](../frontend/src/app/features/measurements/measurements-list.facade.ts) |
| A | [frontend/src/app/features/measurements/measurements.routes.spec.ts](../frontend/src/app/features/measurements/measurements.routes.spec.ts) |
| A | [frontend/src/app/features/measurements/measurements.routes.ts](../frontend/src/app/features/measurements/measurements.routes.ts) |
| A | [frontend/src/app/features/measurements/models/measurement-page-query.model.ts](../frontend/src/app/features/measurements/models/measurement-page-query.model.ts) |
| A | [frontend/src/app/features/measurements/models/measurement.model.ts](../frontend/src/app/features/measurements/models/measurement.model.ts) |
| A | [frontend/src/app/features/measurements/models/measurements-state.model.ts](../frontend/src/app/features/measurements/models/measurements-state.model.ts) |
| A | [frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.html](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.html) |
| A | [frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.scss](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.scss) |
| A | [frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.spec.ts](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.spec.ts) |
| A | [frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.ts](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.ts) |
| A | [frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.html](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.html) |
| A | [frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.scss](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.scss) |
| A | [frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts) |
| A | [frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.ts](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.ts) |
| A | [frontend/src/app/features/measurements/utils/measurement-display.ts](../frontend/src/app/features/measurements/utils/measurement-display.ts) |
| A | [frontend/src/app/features/measurements/utils/measurement-period-draft.spec.ts](../frontend/src/app/features/measurements/utils/measurement-period-draft.spec.ts) |
| A | [frontend/src/app/features/measurements/utils/measurement-period-draft.ts](../frontend/src/app/features/measurements/utils/measurement-period-draft.ts) |
| A | [frontend/src/app/features/measurements/utils/measurement-time.spec.ts](../frontend/src/app/features/measurements/utils/measurement-time.spec.ts) |
| A | [frontend/src/app/features/measurements/utils/measurement-time.ts](../frontend/src/app/features/measurements/utils/measurement-time.ts) |
| M | [frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.html](../frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.html) |
| M | [frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.scss](../frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.scss) |
| M | [frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.spec.ts](../frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.spec.ts) |
| M | [frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.ts](../frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.ts) |
| A | [frontend/src/app/features/sensors/pages/sensor-detail/sensor-measurements-navigation.spec.ts](../frontend/src/app/features/sensors/pages/sensor-detail/sensor-measurements-navigation.spec.ts) |
| M | [frontend/src/app/layout/sidebar/sidebar.component.spec.ts](../frontend/src/app/layout/sidebar/sidebar.component.spec.ts) |
| M | [frontend/src/styles/_buttons.scss](../frontend/src/styles/_buttons.scss) |

## 6. Checklist de fusion préparée, sans exécution

Contrôles déjà faits pendant UI 7.6 :

- [x] Branche feature/frontend-measurements, HEAD 43d12fa et dépôt initial propre.
- [x] Rapports UI 7.1 à UI 7.5 et finitions relus, préservés et reliés aux suivis.
- [x] Périmètre lecture seule, temps précis, unité actuelle et navigation documentés.
- [x] Références historiques exactes et réserves visibles, sans nouvelle validation revendiquée.
- [x] Comparaison locale main/origin/main, cinq commits et 36 fichiers identifiés.
- [x] Routage, styles globaux et réutilisation des composants partagés examinés.
- [x] Diff de branche et modifications documentaires contrôlés : aucun secret nouveau,
  dump SQL, capture, trace HTTP, runner, fixture temporaire, dépendance ou artefact.
- [x] Liens locaux et ancres des sept documents contrôlés ; URLs externes non sollicitées.
- [x] git diff --check du diff de branche et du travail documentaire réussi.
- [x] Aucun code exécutable modifié en UI 7.6 ; tests et build non relancés.

Actions restant à autoriser ou à effectuer après validation de ce dossier :

- [ ] Valider les sept documents UI 7.6 et accepter explicitement les réserves restantes.
- [ ] Autoriser séparément le commit documentaire ; ajouter uniquement ces sept fichiers,
  examiner l'index/stat/check et créer le commit autorisé.
- [ ] Avant fusion autorisée, revérifier les références locales et distantes selon le
  workflow approuvé ; s'assurer de l'absence de divergence et d'autres modifications.
- [ ] Examiner le diff final incluant la documentation, les commits et le périmètre
  attendu de 43 fichiers ; ne pas inclure de preuves ignorées ou secrets historiques.
- [ ] Si les sources restent identiques, conserver les 1 482 tests et le build comme
  références historiques ; si une résolution modifie du code, faire valider à nouveau
  les tests/build pertinents, sans relever artificiellement les budgets.
- [ ] Confirmer l'acceptation des dettes B-MES/B-SEN, sécurité, seed, unité et couverture
  PostgreSQL ; aucune remise en conformité implicite ni écriture de nettoyage.
- [ ] Vérifier la disponibilité des preuves locales référencées si nécessaire au suivi ;
  leur caractère ignoré signifie qu'un clone Git seul ne les fournit pas.
- [ ] Autoriser et effectuer la fusion vers main selon le workflow retenu, puis contrôler
  statut/historique ; publication et éventuel déploiement sont des opérations distinctes.

Aucune de ces cases en attente ne constitue une opération déjà réalisée.

## 7. État Git de cette intervention

HEAD 43d12fa inchangé, branche feature/frontend-measurements. Index vide.
Six documents suivis modifiés et docs/ui-7.6-measurements-delivery.md ajouté non suivi,
soit sept fichiers documentaires uniquement. Rapports historiques inchangés.
Aucun secret nouveau, dump SQL, capture ou artefact dans le périmètre à livrer.
Aucun commit, push, rebase ou merge ; aucune opération PostgreSQL/Docker, package,
test ou build. UI 8 non commencée. Attendre validation avant commit et fusion.
