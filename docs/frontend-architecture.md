# Frontend Architecture - Industrial Predict AI

## Objectif

Définir l'architecture frontend d'Industrial Predict AI et garantir une interface cohérente, maintenable et alignée avec les APIs backend.

## Stack

- Angular 21.2.25 standalone ; CLI/build 21.2.26
- TypeScript 5.9.3, mode strict
- Nebular 17.0.0 et Angular CDK 21.0.6
- RxJS 7.8.2 et Zone.js 0.16.3
- Angular Router
- SCSS ; Dart Sass installé : 1.97.3, minimum 1.95.0 pour la correction Nebular
- HttpClient configuré par `provideHttpClient()` ; base relative `/api/v1`

État documentaire synchronisé en UI 5.8 le 20 octobre 2026 sur
`feature/frontend-equipments`, HEAD de référence `39e2f0d`. Le socle, Dashboard,
Companies et Sites sont intégrés dans `main` à `667fe5b`. Équipements MVP est
implémenté sur sa branche, en attente de validation du commit documentaire puis
de la fusion. Les sections datées conservent leurs résultats historiques ;
le [statut courant](project-status.md#équipements-mvp---livraison-préparée-ui-58)
centralise les résultats et limites. Aucun test/build relancé en UI 5.8.
Voir `decisions.md` pour les limites de compatibilité.

## Structure réellement présente - socle, Dashboard V1, Companies, Sites et Équipements MVP

```text
frontend/
├── src/app/
│   ├── app.component.* / app.config.ts / app.routes.ts / app.routes.spec.ts
│   ├── layout/
│   │   ├── shell/
│   │   ├── sidebar/
│   │   ├── header/
│   │   └── navigation/ (modèle et configuration)
│   ├── core/ (http/, api/reference-data-api.service.*, models/)
│   ├── features/dashboard/ (models/, data-access/, dashboard.facade.*, pages/, components/)
│   ├── features/companies/ (models/, data-access/, companies-list.facade.*, pages/, components/, styles/)
│   └── shared/
│       ├── components/page-header/
│       ├── components/loading-state/
│       ├── components/empty-state/
│       ├── components/error-state/
│       ├── pages/feature-placeholder/
│       ├── pages/not-found/
│       └── ui/icon/ (SVG locaux)
├── src/styles.scss
├── src/styles/_tokens.scss / _nebular-theme.scss
└── scripts/ (correction Sass Nebular et vérifications)
```

`features/sites/` complète cet inventaire avec models/, data-access/,
sites-list.facade.*, sites.routes.*, pages/ et components/site-form/.
`features/equipments/` contient models/, data-access/, equipments-list.facade.*,
equipments.routes.*, pages/ et components/equipment-form/. Les détails figurent
dans les sections Sites et Équipements ci-dessous. Les styles d'actions et
interactions communs sont dans src/styles/_actions.scss et _buttons.scss.

`AppComponent` contient le Router Outlet racine. `ShellComponent` contient
un seul `nb-layout`, un `nb-sidebar`, un `nb-layout-header subheader`
avec `HeaderComponent` et un `nb-layout-column` avec `main#main-content`
et le Router Outlet enfant. `SidebarComponent` s'intègre dans le sidebar
existant, sans le recréer. En desktop, le header se situe à droite de la sidebar ;
en mobile/tablette, il occupe la largeur disponible et la Sidebar est superposée.

Le Header lit `data.pageTitle` sur la route primaire active la plus profonde,
avec le repli « Espace de travail ». Le titre du document provient de `title`
dans la configuration Router. Aucun fil d'Ariane n'est défini actuellement.
La commande Sidebar utilise le service Nebular et reflète l'état avec
`aria-expanded`. Notifications et profil sont des emplacements visuels
« À venir », sans interaction ni identité ou compteur fictif.

Le lien d'évitement déplace le focus vers le main (`tabindex="-1"`) sans
navigation ni changement du chemin, des paramètres ou du fragment.
Après NavigationEnd, le focus est déplacé après rendu lors d'un changement
de page ; la navigation initiale, les changements de query params seuls,
les fragments et les interactions ayant repris le focus sont préservés.
Les abonnements et callbacks restent liés au cycle de vie Angular.

## Politique responsive réelle - UI 1.8.2

Le `ShellComponent` centralise la détection du mode à partir de la largeur CSS
du viewport, via `DOCUMENT.defaultView.innerWidth` et un listener `resize`
créé par `Renderer2`. Le listener et les callbacks `afterNextRender` sont
nettoyés via `DestroyRef`.

| Mode | Seuil | État initial et comportement |
| --- | --- | --- |
| Desktop | **>= 1024 px**, y compris 1024 exactement | Sidebar latérale expanded, fermeture manuelle possible |
| Mobile/tablette | **< 1024 px** | Sidebar collapsed initialement ; ouverture superposée sans compression du contenu |

Nebular reste la source unique de l'état de Sidebar : l'entrée `state` définit
l'état initial, puis les API `expand()`, `collapse()`, `toggle(false, tag)` du
service utilisé par le Header et la sortie `stateChange` synchronisent l'UI.
Le mode natif `responsive` de Nebular n'est pas activé : son état `compacted`
et ses styles de menu ne correspondent pas aux liens personnalisés du projet.
La superposition repose sur des overrides SCSS limités à `.shell-layout.shell-mobile`.

En mobile, le panneau ouvert est un dialogue `aria-modal="true"` ;
`CdkTrapFocus`, issu du CDK déjà installé, confine Tab/Shift+Tab dans le panneau.
Le focus est placé sur le bouton « Fermer la navigation » après rendu.
Le Header et la colonne principale deviennent `inert` et `aria-hidden`.
Le fond extérieur cliquable, Échap et le bouton interne ferment le panneau
et restaurent le focus au toggle du Header. Le fond n'est pas dans l'ordre de
tabulation ; le bouton interne fournit l'action clavier équivalente.
Le scroll de l'arrière-plan est bloqué par le style conditionnel
`body:has(.shell-layout.drawer-open)` ; la navigation conserve son propre scroll.

Après `NavigationEnd`, le panneau mobile ouvert est fermé sans forcer un retour
au toggle lorsqu'un changement de page doit déplacer le focus vers le main.
Les règles existantes de focus restent applicables : fragments, changements
de query params seuls, interactions et focus revendiqué par une page sont
respectés. Si une navigation avec fragment ou sur la même page laisse le focus
dans le menu désormais masqué, le toggle sert de repli. Une navigation annulée
ne ferme pas le panneau.

Au franchissement desktop vers mobile, la Sidebar se ferme ; un focus dans
la navigation masquée revient au toggle. Au retour desktop, elle s'ouvre et
le fond, la modalité et l'inertie du contenu disparaissent ; le focus revient
au toggle si le bouton de fermeture mobile disparaît. Un redimensionnement
restant dans le même mode conserve l'état choisi par l'utilisateur.

Le Header reçoit l'état réel de la Sidebar pour `aria-expanded`, son identifiant
pour `aria-controls` et un libellé dynamique. Ses styles mobiles sont déclenchés
par la classe du Shell, sans seconde politique de breakpoint indépendante.
Sous 1024 px, l'identité secondaire et Notifications/Profil sont masqués ;
le bouton et le titre restent prioritaires avec des espacements réduits.

La couverture dédiée se trouve dans `layout/shell/shell-responsive.spec.ts` :
initialisation (dont 1023/1024), transitions, fermeture, navigation annulée ou
réussie, focus, attributs accessibles, skip link et nettoyage du listener.

## Routes réellement présentes

Toutes les routes ci-dessous sont enfants du Shell. Les labels et chemins
des neuf destinations accessibles sont issus de `NAVIGATION_ITEMS`, source
unique partagée par `app.routes.ts` et la Sidebar.

| Chemin | data.pageTitle | Composant / comportement | Sidebar |
| --- | --- | --- | --- |
| `/` | - | Redirection vers `/dashboard`, `pathMatch: 'full'` | Dashboard après redirection |
| `/dashboard` | Dashboard | DashboardComponent standalone, connecté à FastAPI | Dashboard, correspondance exacte |
| `/companies` | Entreprises | CompaniesListComponent | Entreprises |
| `/companies/new` | Nouvelle entreprise | CompanyFormPageComponent, création | Entreprises |
| `/companies/:companyId/edit` | Modifier l’entreprise | CompanyFormPageComponent, modification | Entreprises |
| `/companies/:companyId` | Détail entreprise | CompanyDetailComponent | Entreprises |
| `/sites` | Sites industriels | SitesListComponent | Sites |
| `/sites/new` | Nouveau site industriel | SiteCreateComponent, création | Sites |
| `/sites/:siteId/edit` | Modifier le site | SiteEditComponent, modification | Sites |
| `/sites/:siteId` | Détail du site | SiteDetailComponent | Sites |
| `/equipments` | Équipements | EquipmentsListComponent | Équipements |
| `/equipments/new` | Nouvel équipement industriel | EquipmentCreateComponent | Équipements |
| `/equipments/:equipmentId/edit` | Modifier l’équipement | EquipmentEditComponent | Équipements |
| `/equipments/:equipmentId` | Détail équipement | EquipmentDetailComponent | Équipements |
| `/sensors` | Capteurs | FeaturePlaceholderComponent | Capteurs |
| `/measurements` | Mesures | FeaturePlaceholderComponent | Mesures |
| `/maintenance` | Maintenance | FeaturePlaceholderComponent | Maintenance |
| `/predictions` | Prédictions | FeaturePlaceholderComponent | Prédictions |
| `/recommendations` | Recommandations | FeaturePlaceholderComponent | Recommandations |
| `**` (dernière route) | Page introuvable | NotFoundComponent, `data.isNotFound: true` | Aucune sélection trompeuse |

Chaque page a un titre de document `pageTitle | Industrial Predict AI`.
Le paramètre `equipmentId` est validé localement avant GET Equipment ; les
lectures obsolètes sont annulées lorsqu'il change. Les parents réels sont résolus
depuis Equipment.site_id puis Site.company_id, jamais depuis le contexte URL.

Rapports et Administration n'ont ni chemin dans la navigation ni route dédiée.
Ils sont désactivés et libellés « À venir ». `/reports`, `/administration` et
les autres URL inconnues affichent la 404 dans le Shell, sans changer l'URL.
Pour `/equipments/42/inconnu`, le marqueur 404 force une correspondance
exacte des liens et évite une sélection Équipements incorrecte ; le détail
valide `/equipments/42` conserve la sélection de section.

Le Shell, DashboardComponent, le placeholder commun et la 404 utilisent
`loadComponent` avec import dynamique. Companies, Sites et Équipements utilisent
`loadChildren` vers `COMPANY_ROUTES`, `SITE_ROUTES` et `EQUIPMENT_ROUTES`, puis
`loadComponent` pour leurs pages,
sans préchargement configuré. Dans chaque feature, `new` puis la route d'édition
précèdent l'identifiant dynamique. Les cinq autres destinations métier disponibles partagent le même placeholder.
Les tests contrôlent les chargeurs différés sans dépendre des noms de chunks.
Les placeholders n'affichent aucun faux KPI et ne déclenchent aucun appel API.
Les fichiers DashboardPlaceholderComponent restent présents mais ne sont plus
routés ; la route Dashboard charge uniquement DashboardComponent.

## Structure générale cible

Les dossiers métier autres que `dashboard`, `companies`, `sites` et `equipments`
constituent la cible. `core`, `layout`, `shared` et ces quatre features existent.

```text
src/app/
├── core/
├── shared/
├── layout/
├── features/
│ ├── dashboard/
│ ├── companies/
│ ├── sites/
│ ├── equipments/
│ ├── sensors/
│ ├── measurements/
│ ├── maintenance/
│ ├── predictions/
│ └── recommendations/
└── app.routes.ts
```

## Navigation principale

- Dashboard
- Entreprises
- Sites
- Équipements
- Capteurs
- Mesures
- Maintenance
- Prédictions
- Recommandations
- Rapports
- Administration

## Pages prioritaires à implémenter

Dashboard V1, Companies, Sites et Équipements MVP sont implémentés. Les listes
ci-dessous distinguent les fonctions livrées des intentions produit futures ;
les routes Capteurs, Mesures, Maintenance, Prédictions et Recommandations rendent
encore des placeholders.

### Dashboard V1 - livré en UI 2.2 à UI 2.7.1

- synthèse des agrégats existants
- équipements : statut et criticité actuels
- capteurs : statut, couverture et émission
- mesures : volume, qualité déclarée et derniers relevés
- maintenance : ouverte, en retard de démarrage et terminée sur la période

Les intentions antérieures de santé des équipements, risques de panne et alertes
critiques restent des objectifs ultérieurs ; elles ne sont pas fournies par le
contrat Dashboard et ne font pas partie de V1 (D014 / DASH-01).

### Équipements et détail - MVP livré en UI 5

Liste/recherche/pagination, filtres statut/criticité, sélection entreprise/site,
détail des données réelles, création et modification différentielle sont livrés.
Voir l'[architecture implémentée](#équipements-mvp---architecture-implémentée-ui-5).
Health Score, Failure Risk, RUL et dernière maintenance ne sont pas affichés.
Les onglets Capteurs, Mesures, Prédictions, Recommandations, Maintenance et
Documents restent des intentions futures, sans compteurs fictifs ni calcul ML.

### Prédictions

- historique
- filtres
- pagination
- anomaly
- failure risk
- health score
- RUL

### Recommandations

- génération
- historique
- priorité
- type
- raison
- action recommandée
- signaux utilisés

## Architecture frontend

Page
→ Facade / Service
→ API Service
→ Backend FastAPI

Les composants visuels ne doivent pas contenir de logique métier complexe.
Ce flux est implémenté pour Dashboard V1, avec façade locale à la page et
services HTTP ; Companies utilise également une façade locale pour sa liste
et un service dédié. Sites et Équipements suivent cette séparation ; les services
des autres écrans métier restent à développer.

## Gestion API

Les appels HTTP sont centralisés dans des services dédiés.

Exemples :

- EquipmentsApiService (implémenté)
- DashboardApiService
- CompaniesApiService (implémenté)
- SitesApiService (implémenté)
- PredictionApiService
- RecommendationApiService
- MaintenanceApiService

## États UI

Chaque écran doit gérer explicitement :

- loading
- success
- empty
- error

## Design System

### Couleurs fonctionnelles

- vert : normal / healthy
- jaune : vigilance
- orange : dégradation
- rouge : critique
- bleu : navigation / actions principales

### Principes

- interface professionnelle
- forte lisibilité
- informations critiques immédiatement visibles
- densité adaptée aux usages industriels
- cohérence entre tableaux, cartes et badges
- responsive desktop/tablette

## Architecture shared et contrats validés UI 1.7.1

`shared/ui/icon` existe déjà. `shared/pages` contient les pages transversales
de routing (placeholder et 404). Les quatre composants de présentation sont
implémentés dans `shared/components/`, distinctement de ces pages, et commités
dans `e3a2a2c`. UI 1.7 est terminée. Ils sont intégrés au Dashboard V1
et ne créent aucune route de démonstration persistante.

Les contrats suivants ont été validés dans la discussion de conception
Industrial Predict AI puis transmis pour cette synchronisation documentaire.

### PageHeaderComponent - implémenté en UI 1.7.2

- Emplacement : `shared/components/page-header/`.
- Entrée obligatoire : `title: string` ; entrée optionnelle : `description?: string`.
- Projection `ng-content` pour les actions spécifiques à la page.
- Titre sémantique `<h1>` ; description rendue uniquement si renseignée.
- Actions à droite sur grand écran, sous le titre sur petit écran.
- Aucun appel API ni logique métier. Il ne remplace pas le Header global du Shell.
- API : `input.required<string>()` pour title, `input<string>()` pour description.
- Une description vide ou composée uniquement d'espaces n'est pas rendue.

### LoadingStateComponent - implémenté en UI 1.7.3

- Emplacement : `shared/components/loading-state/`.
- Entrée optionnelle : `message: string`, valeur par défaut « Chargement des données… ».
- Indicateur visuel et `role="status"` pour annoncer le chargement.
- Animation respectant les préférences de réduction du mouvement.
- Aucun déclenchement de requête HTTP.
- Une entrée signal avec défaut et un message de repli si le texte est vide ;
  une seule région status, `aria-atomic="true"`, indicateur décoratif `aria-hidden`.

### EmptyStateComponent - implémenté en UI 1.7.4

- Emplacement : `shared/components/empty-state/`.
- Entrées : `title: string` et `message: string`.
- Illustration ou icône décorative optionnelle.
- Projection facultative d'une action fournie par la page métier.
- État distinct d'une erreur réseau ; aucun appel API ni création automatique de données.
- title et message utilisent `input.required<string>()` ; titre sémantique `<h2>`.
- Entrée optionnelle `icon: LocalIconName | undefined` : réutilisation de
  `IconComponent` et de son entrée existante `name`, sans enrichir le catalogue.

### ErrorStateComponent - implémenté en UI 1.7.5

- Emplacement : `shared/components/error-state/`.
- Entrées : `title: string`, `message: string`, `retryable: boolean`.
- Sortie : événement `retry`, uniquement lorsque l'utilisateur active « Réessayer ».
- Message accessible avec `role="alert"` ou mécanisme équivalent adapté, sans répétition excessive.
- Bouton « Réessayer » accessible au clavier, visible uniquement si `retryable` est vrai.
- Aucun appel HTTP dans le composant ; la page consommatrice gère la relance.
- title et message utilisent `input.required<string>()` ; `retryable = input(false)`
  et `retry = output<void>()`. Le titre est un `<h2>`.
- Une seule région `role="alert"`, `aria-atomic="true"`, contient le titre et
  le message ; le bouton reste hors de cette région pour éviter les réannonces
  liées à son apparition. Aucun timer ni relance interne.

### Principes communs et validation d'implémentation

Les quatre composants utilisent Angular 21 standalone, OnPush, TypeScript strict, SCSS avec les tokens existants,
HTML sémantique, contrastes et navigation clavier. Ces composants restent
légers, indépendants des modules métier et du backend FastAPI, sans nouvelle
dépendance. Les tests unitaires couvrent les étapes UI 1.7.2 à UI 1.7.5 : contrats
d'entrée, rendu conditionnel, projection, sémantique accessible et émission
de `retry` seulement sur action utilisateur.

Les états restent distincts : `loading`, `success`, `empty`, `error`.
`success` est le rendu normal des données par la page métier ; aucun composant
partagé spécifique n'est prévu pour cet état.

## Historique de validation UI 1.8 - socle terminé

UI 1.8.4 est clôturée : commit `12a18c3`, fusion dans `main` via `acd872b`.
Les résultats ci-dessous proviennent de la validation du socle ; aucun build
ou test applicatif n'est relancé pendant la synchronisation documentaire UI 2.1.1.

La suite frontend comprend **116 tests Angular réussis**, dont les tests des
quatre composants partagés et les 19 tests responsive ajoutés en UI 1.8.2.
Les **5 tests du correctif Sass** et le contrôle des breakpoints, expressions
et thème unique réussissent ; le build production réussit sans nouvelle
dépréciation Sass. Le bundle initial reste à **504,68 ko**, au-dessus du budget
d'avertissement de **500 ko** ; aucun budget n'est relevé.

UI 1.8.3 a vérifié les routes Dashboard, détail équipement et 404 à 1440,
1024, 1023, 768, 390 et 320 px, hauteur 900 px, ainsi que les transitions
répétées autour du seuil et les interactions clavier/souris, sans anomalie
reproductible dans ce périmètre. Les composants partagés ont été réexaminés
dans leur code et leurs tests ; aucune nouvelle démonstration n'a été ajoutée.

Le zoom navigateur réel à **100 %, 200 % et 400 %** est **validé manuellement
par l'utilisateur**, avec cinq vérifications déclarées OK dans la demande
UI 1.8.4. Les tests de reflow de l'assistant à 720 × 450 et 360 × 225 px ne
sont pas présentés comme une preuve de zoom réel ; la confirmation utilisateur
complète cette limite de l'outillage. **Aucun lecteur d'écran réel n'a été testé**.
La vérification du DOM/ARIA et du clavier ne certifie pas à elle seule la
compatibilité de toutes les technologies d'assistance.

## Dashboard V1 - contrat consommé et architecture livrée UI 2

Conception validée en UI 2.1, documentée en UI 2.1.1 puis implémentée en UI 2.2
à UI 2.7.1. UI 2.8 a finalisé la documentation et la validation (`9ce0cac`) ;
Dashboard V1 est fusionné dans `main` et publié sur GitHub. Les choix DASH-01 à DASH-06 sont
enregistrés dans D014 de [decisions.md](decisions.md).
Le plan de tests et les étapes UI 2.2 à UI 2.8 figurent dans [roadmap.md](roadmap.md).

### Contrat backend réellement présent

Source de vérité : `backend/app/api/routes/dashboard.py`,
`backend/app/schemas/dashboard.py`, `backend/app/services/dashboard_service.py`,
`backend/app/repositories/dashboard_repository.py` et
`tests/dashboard/test_route.py`, `test_service.py`, `test_repository.py`.
Ces fichiers sont examinés en lecture seule ; aucune API n'est créée ou modifiée.

`GET /api/v1/dashboard` retourne `DashboardRead` sans pagination.

| Query param | Type et présence | Validation backend |
| --- | --- | --- |
| `company_id` | Entier obligatoire | > 0 ; entreprise existante |
| `start_time` | Datetime obligatoire | Fuseau obligatoire ; normalisation UTC |
| `end_time` | Datetime obligatoire | Fuseau obligatoire ; `start_time < end_time <= calculated_at` |
| `site_id` | Entier facultatif, omis si absent | > 0 ; site existant appartenant à l'entreprise |
| `equipment_id` | Entier facultatif, omis si absent | > 0 ; équipement existant appartenant à l'entreprise et au site si celui-ci est fourni |

Un équipement sans `site_id` est accepté : le service vérifie son rattachement
via son site. La réponse `scope.site_id` reste `null` dans ce cas. Une combinaison
incohérente est rejetée, jamais élargie. Le frontend envoie des chaînes ISO 8601
avec fuseau, de préférence `Z` ; les datetime de réponse sont des chaînes JSON.
Le backend ne fixe ni période par défaut ni durée maximale.

| Bloc de réponse | Données disponibles |
| --- | --- |
| `scope` | `company_id`, `site_id`, `equipment_id` ; les deux derniers peuvent être null |
| `period` | `start_time`, `end_time`, `calculated_at` UTC |
| `assets` | Comptages `sites`, `equipments`, `sensors`, parents sans enfant inclus |
| `equipment_status` | `total`, `operational`, `maintenance`, `out_of_service`, `other`, `distribution`, `operational_ratio` |
| `equipment_criticality` | `total`, `low`, `medium`, `high`, `critical`, `other`, `distribution`, `high_or_critical`, `high_or_critical_unavailable` |
| `sensor_coverage` | `equipments_total`, `equipments_with_active_sensor`, `coverage` |
| `sensor_status` | `total`, `active`, `inactive`, `other`, `distribution`, `active_ratio` |
| `measurements.activity` | `measurements_total`, `active_sensors_total`, `active_sensors_with_measurement`, `active_sensors_reporting_ratio` |
| `measurements.quality` | `total`, `good`, `suspect`, `bad`, `missing`, `estimated`, `other`, `distribution`, `good_ratio` |
| `measurements.daily_volume` | Tableau `{ date: string, count: number }`, jours UTC `YYYY-MM-DD` |
| `measurements.last_measurements` | Un relevé par capteur du périmètre, y compris sans mesure |
| `maintenance.open` | `total`, `planned`, `in_progress`, `other`, `priorities` (total, low/medium/high/critical/other, distribution) |
| `maintenance.overdue` | `overdue`, `planned_without_planned_at` |
| `maintenance.completed` | `total`, `completed_without_completed_at`, `types` (total, preventive/corrective/predictive/other, distribution) |
| `maintenance.corrective` | `corrective_completed`, `completed_total`, `ratio` |
| `maintenance.downtime` | `total_minutes`, `total_hours`, `coverage` |
| `maintenance.cost` | `total_cost`, `currency`, `coverage` ; données conservées dans le DTO, affichage monétaire différé |

Les comptages sont des entiers JSON, les valeurs/sommes/pourcentages des nombres.
Un ratio contient `numerator`, `denominator` et `percentage: number | null` :
dénominateur nul → null, sinon pourcentage arrondi par le backend à deux décimales.
Une distribution contient des `{ value: string, count: number }` : catégories
brutes conservées, inconnues incluses dans `other`, catégorie SQL nulle représentée
par la chaîne `"null"`. Ne pas fermer ces chaînes par une union d'enum restrictive.
La couverture des sommes contient `valid_values`, `eligible_records` et `ratio`.

Chaque dernier relevé comprend `sensor_id`, `sensor_name`, `sensor_code`,
`equipment_id`, `timestamp`, `value`, `unit`, `quality`, `age_seconds`.
Les identifiants/noms/codes sont renseignés ; timestamp, valeur, unité, qualité
et âge sont nullables. Sans relevé, ne pas inventer une valeur nulle à zéro.
L'unité vient du capteur et peut rester renseignée sans mesure.

### Temps, qualité et limites de calcul

- **État actuel** : inventaire, statut/criticité des équipements, statut et
  couverture capteurs, maintenances ouvertes (`planned`/`in_progress`) ;
  indépendants du filtre temporel, sans reconstitution des états historiques.
- **Sur la période** : mesures avec `timestamp` dans `[start_time, end_time)` ;
  interventions `completed` avec `completed_at` dans le même intervalle ;
  leurs types, part corrective, coûts et arrêts déclarés.
- **Au calcul** : dernières mesures `timestamp <= calculated_at`, sans
  restriction à la période ; retard de démarrage des interventions `planned`
  avec `planned_at < calculated_at` et `started_at` absent.
- Les dates prévues manquantes (`planned_without_planned_at`) et dates de fin
  manquantes (`completed_without_completed_at`) sont des anomalies de saisie
  comptées sur le périmètre actuel, pas sur la période.
- Le volume quotidien est regroupé en UTC et complété avec zéro. Les jours
  partiels sont possibles ; une fin à minuit exclut ce nouveau jour.
- Les capteurs ayant émis sont actuellement actifs avec au moins une mesure
  sur la période, quelle que soit la qualité ; pas de fréquence attendue déduite.
- La part opérationnelle n'est pas une disponibilité historique ; la qualité
  `good` est déclarée et ne prouve pas la validité physique des valeurs.
- `high_or_critical_unavailable` compte uniquement high/critical en maintenance
  ou out_of_service ; aucune liste nominative ni probabilité de panne fournie.
- Dernier relevé choisi par timestamp décroissant puis id décroissant ; âge
  calculé à `calculated_at`, sans seuil de silence inventé ni compteur live.
- Coûts et arrêts : zéro intervention éligible → somme 0 et pourcentage de couverture null ;
  interventions présentes sans valeur valide → somme null ; couverture partielle
  → somme partielle explicite. Les valeurs négatives/absentes sont exclues ; les
  coûts non finis aussi. `currency` vaut actuellement null (DASH-03).
- L'arrêt est une somme de déclarations, pas une indisponibilité dédupliquée ;
  ne pas inventer MTBF, MTTR, moyenne globale des mesures ou économie réalisée.

| HTTP | Comportement backend / traitement frontend livré |
| --- | --- |
| 200 | Réponse structurée, y compris périmètre vide et valeurs nullables |
| 400 | Dates sans fuseau, période vide/inversée, fin future, site hors entreprise ou équipement hors entreprise/site ; corriger les filtres |
| 404 | `Company not found`, `Site not found`, `Equipment not found`, `Equipment site not found` ; vérifier la référence, sans élargissement silencieux |
| 422 | Paramètres obligatoires absents ou mal typés, identifiants non positifs, datetime invalide ; erreurs de saisie |
| 500 éventuel / réseau | Erreur non interceptée ou indisponibilité ; message accessible et relance manuelle |

Les 400/404 contiennent `{ detail: string }` ; la validation FastAPI 422 utilise
une liste dans `detail`. Aucun contrôle d'autorisation utilisateur/entreprise
n'apparaît dans la route actuelle : `company_id` filtre le périmètre, sans
sécuriser l'accès multi-entreprises. Ce risque ne sera pas corrigé par l'UI seule.

### Références et filtres livrés

Le Dashboard ne retourne pas les noms/listes de référence nécessaires aux filtres.
`ReferenceDataApiService` utilise les API existantes, sans nouvelle API :

| Référence | GET relatif à `/api/v1` |
| --- | --- |
| Entreprises | `/companies?page=…&page_size=…&search=…` |
| Sites | `/sites?company_id=…&page=…&page_size=…&search=…` |
| Équipements | `/equipments?site_id=…&page=…&page_size=…&search=…&status=…&criticality=…` |

Les filtres status/criticality sont facultatifs depuis UI 5.2 ; les appels
Dashboard existants sont conservés et omettent ces paramètres.

Les réponses `Page<T>` contiennent `items`, `total`, `page`, `page_size`, `pages`.
Page initiale 1, taille par défaut 20, maximum 100 : ne pas présenter la première
page comme une liste exhaustive. Les modèles de références transportent id,
nom/code et parent réel ; les sélecteurs affichent nom/code. Ne pas coder
d'entreprise ou de données d'exemple en dur.

Entreprise obligatoire ; « Tous les sites » et « Tous les équipements » omettent
les filtres facultatifs. Changer d'entreprise efface site et équipement ; changer
de site efface équipement. Le sélecteur d'équipement est proposé après choix du
site (DASH-04), sans imposer cette limitation au DashboardApiService.

Le préréglage initial est sept jours glissants UTC, soit 168 heures :
à l'application, fixer une fin unique T et un début T - 168 heures (DASH-05).
Les bornes envoyées restent fixes après application ; une saisie de période
explicite conserve ses valeurs validées. Les dates restent avec fuseau et la fin
exclusive est indiquée à l'utilisateur. Aucun GET Dashboard tant qu'entreprise
et période valides ne sont pas disponibles ; application explicite des filtres,
pas de requête à chaque frappe ni de polling.

`DashboardFiltersComponent` utilise Reactive Forms, des labels natifs et des
messages UTC. Le chargement commence à page 1, taille 50 ; les boutons « Charger
davantage » ajoutent les pages suivantes en dédupliquant les identifiants.
Les compteurs chargés/total restent visibles. Une erreur de page ultérieure
conserve les options déjà chargées et permet de réessayer cette page. Les flux
de références utilisent `switchMap` et `takeUntilDestroyed`, désactivent les
contrôles pendant le chargement et bloquent l'application en cas d'erreur ou de
sélection incohérente. Le service accepte `search`, mais aucun champ de recherche
de références n'est présent dans le formulaire Dashboard V1.

Le préréglage non édité est finalisé à la première application ; les périodes
personnalisées et les bornes déjà appliquées restent fixes. Les inputs
`datetime-local` sont explicitement interprétés en UTC, pas en heure locale.
Le composant émet `filtersApplied` et ne consomme jamais DashboardApiService.

### Architecture Angular livrée

```text
src/app/
├── core/
│   ├── http/api-config.ts
│   ├── api/reference-data-api.service.ts
│   └── models/ (page.model.ts, reference-data.model.ts)
└── features/dashboard/
    ├── models/ (dashboard.model.ts, dashboard-filters.model.ts, dashboard-state.model.ts)
    ├── data-access/dashboard-api.service.ts
    ├── dashboard.facade.ts
    ├── pages/dashboard/dashboard.component.*
    └── components/
        ├── dashboard-filters/
        ├── dashboard-kpi-card/
        ├── equipment-summary/
        ├── sensor-summary/
        ├── measurement-summary/
        └── maintenance-summary/
```

- DTO TypeScript stricts conformes aux schémas, noms JSON et nullabilité ;
  dates conservées en chaînes de transport, formatage explicite à l'affichage.
- DashboardApiService : GET et HttpParams, sans filtre absent envoyé sous forme
  `null`/chaîne vide ; aucun calcul de KPI. HttpClient est configuré dans app.config.ts.
- Service de références : centraliser les CRUD paginés, sans duplication HTTP.
- Façade locale à la page : filtres appliqués, états, actualisation/relance,
  traduction des erreurs ; `switchMap` pour écarter les réponses obsolètes,
  une réponse partagée entre les sections, cycle de vie nettoyé ; pas de store global.
- Page standalone lazy : DashboardComponent remplace le placeholder dans le
  chargeur Dashboard seulement, avec métadonnées Router et Header global conservés ; PageHeader fournit
  l'unique h1. Aucun import Dashboard dans le Shell.
- Présentation OnPush : entrées typées, sections et cartes sans HTTP ni logique
  métier ; tokens SCSS et styles Nebular ciblés, sans nouveaux modules volumineux.
- DASH-06 : base relative `/api/v1` centralisée dans `core/http/api-config.ts`,
  `provideHttpClient()` dans app.config.ts. `proxy.conf.json` relaie `/api/v1/**`
  vers `http://127.0.0.1:8000`, uniquement pour `serve:development` dans angular.json.
  Ce lancement historique ne constitue plus le démarrage DEV recommandé : le
  [lanceur permanent](../infra/development/README.md) impose Angular 4201,
  FastAPI 8001 et `industrial_predict_dev`, avec contrôle d'identité sans repli.
  La configuration de production n'utilise pas ce proxy et n'embarque pas son URL
  localhost. Le reverse proxy de production reste à configurer séparément.

DashboardFacade est fournie dans `providers` de DashboardComponent. Elle garde
un snapshot immuable des filtres appliqués et les états sous forme de signals ;
`switchMap` annule les requêtes obsolètes, `DestroyRef` nettoie les abonnements.
Actualiser et Réessayer relancent ce snapshot, sans lire les valeurs en édition.
Le bouton Actualiser reste focusable avec `aria-disabled`, et son handler ignore
les activations lorsqu'une relance n'est pas permise. Pas de polling ni de GET
Dashboard à l'initialisation ; seul le chargement de références est automatique.

Les cinq sections réutilisent une réponse unique : six DashboardKpiCard dans la
synthèse, EquipmentSummary, SensorSummary, MeasurementSummary et MaintenanceSummary.
Ces composants standalone OnPush n'ont pas de dépendance HTTP. Les ratios
proviennent de l'API ; numérateur/dénominateur servent uniquement à l'explication.
Les mixins SCSS locaux de `components/_summary.scss` réutilisent les tokens.
DashboardKpiCard est un composant de feature réutilisable, pas un nouveau module
Nebular. Les relevés conservent la précision de la valeur et l'âge API en secondes.
L'affichage monétaire est absent, même si `maintenance.cost` est transporté.

### États de la page implémentés

| État | Comportement livré |
| --- | --- |
| idle | PageHeader et filtres, « Sélectionnez une entreprise » ; aucune requête Dashboard ni entreprise supposée |
| loading | LoadingState unique et zone de résultats aria-busy ; conserver filtres et focus |
| empty | EmptyState si sites, équipements et capteurs sont tous à zéro ; périmètre/période visibles. En success, les sections sans lignes affichent un texte explicite, pas un état vide global |
| error | ErrorState ; retry pour réseau/serveur uniquement sur action utilisateur ; pour 400/422 corriger les filtres, pour 404 revoir la référence |
| success | Cinq sections avec données réelles ; aucun composant success partagé supplémentaire |

Une période sans mesures ne vide pas l'inventaire ni la maintenance. Ne pas
déduire l'état vide de la seule longueur de `daily_volume`, qui peut contenir
des jours à zéro, ni confondre des derniers relevés absents avec aucun capteur.
Les changements de filtres/chargements ne doivent pas forcer le focus ou une
navigation ; conserver skip link, focus du Shell et annonces accessibles uniques.

### Validation réelle, simulations et limites

UI 2.7 a validé PETROSEN sur PostgreSQL existant, sans injection de données.
KPI exacts confrontés à FastAPI ; période initiale 168 heures, cascade, options
facultatives, dates invalides et snapshot d'actualisation vérifiés en navigateur.
La fin exclusive est prouvée sur un relevé existant : 3 mesures avant
`2026-09-01T10:03:00Z`, 4 avant `10:03:00.001Z`, avec début à `10:00:00Z`.
Un relevé du 1er septembre reste visible dans une période d'octobre ; un capteur
sans mesure conserve son unité. Un équipement sans capteurs reste en success.

idle/success sont observés avec le backend ; loading Dashboard, empty et l'UI
error/retry sont contrôlés par les tests HTTP simulés. Les GET directs reproduisent
400/404/422, sans revendiquer leur affichage réel dans la page. Pagination sur
plusieurs pages, courses de réponses, catégories inconnues et couvertures
partielles sont simulées ; les références réelles tiennent sur une page.
Les tests HTTP vérifient l'absence de requêtes inattendues ; pas de capture réseau
navigateur exhaustive. Aucun test de charge à grand volume n'est revendiqué.
Après UI 2.7.1 : 220 tests Angular et 5 tests Sass réussis, build réussi,
`npm ls --all` valide, `npm audit` sans vulnérabilité. Le bilan UI 2.8 est consigné
dans [project-status.md](project-status.md).

Les six largeurs 1440/1024/1023/768/390/320 px CSS, hauteur 900 px, sont contrôlées
sans débordement global ; clavier, focus, huit tableaux, un seul h1 et console
contrôlés. Le zoom réel Dashboard **100/200/400 % est validé manuellement par
l'utilisateur**, confirmé en réponse à la clarification UI 2.8 ; ce contrôle
n'est pas attribué à l'assistant. Voir [ui-design.md](ui-design.md) pour la portée
des essais de zoom et la distinction avec l'historique du socle.
**Lecteur d'écran réel non testé** ; aucun résultat vocal ou certification déduit
des tests DOM/ARIA. Dashboard V1 est désormais fusionné dans `main` ;
la publication du code ne vaut pas validation de production SaaS multi-tenant.

### Risques et dette technique restant à traiter

- Autorisation multi-entreprises absente dans la route actuelle ; filtrage et
  sélection ne remplacent pas authentification/RBAC.
- Pagination des références et suppression/rattachement concurrent d'une
  référence ; gérer 404 et cohérence des sélections.
- UTC, fin exclusive, jours partiels et horloge client en avance (fin future rejetée).
- Environ 21 lectures d'agrégats plus validation du périmètre ; mesurer la latence
  réelle. Aucune durée maximale de période, derniers relevés non paginés :
  une pagination d'affichage locale ne réduit pas le payload backend.
- `calculated_at` commun sans garantie explicite de snapshot SQL entre agrégats ;
  rattachements/statuts actuels, pas de reconstruction historique.
- Nullabilité, catégories inconnues, couverture partielle et coûts en Float ;
  ne pas convertir en zéro ni présenter une précision comptable garantie.
- Responsive, longs noms et tables jusqu'à 320 px ; lecteur d'écran réel non testé,
  à vérifier si disponible sans prétendre à une certification.
- Bundle initial à la clôture Dashboard UI 2.8 : **565,38 ko** contre **500 ko** de warning (1 Mo d'erreur) :
  dépassement 65,38 ko. Référence Dashboard différé UI 2.6 : 52,00 ko ; après
  UI 2.7.1 : 51,98 ko. UI 2.4.1 a attribué 35,09 ko de la hausse initiale
  523,08 → 565,34 ko à Angular Forms : Nebular importe déjà FormsModule via
  NbSharedModule, et ReactiveFormsModule rend davantage du module FESM partagé
  utilisé. Le bundler émet cette dépendance dans un chunk initial commun.
  DashboardComponent, sa façade et ses sections restent différés ; aucun test
  dans le graphe production, un seul CSS global. Il ne s'agit pas d'un import
  direct de la page dans le Shell. Aucune réécriture des filtres ou migration
  Nebular n'est décidée pour masquer le warning ; budgets et dépendances inchangés.

L'absence d'autorisation multi-entreprises démontrée interdit de présenter cette
livraison comme prête pour une production SaaS multi-tenant. Le proxy local
fonctionnel ne constitue pas un déploiement de production.

## Companies MVP - architecture implémentée UI 3

UI 3.1 à UI 3.7.1 sont terminées. Le contrat backend détaillé et la conception
initiale sont conservés dans [etape-ui-3.1-companies.md](etape-ui-3.1-companies.md).
Les chemins ci-dessous sont relatifs à `frontend/src/app/` et existent au HEAD
`ac2dc3a` ; aucun fichier applicatif n'est modifié dans UI 3.8.

### DTO, services et structure

| Élément | Responsabilité réelle |
| --- | --- |
| `core/models/reference-data.model.ts` | CompanyRead : id, name, code, description nullable, created_at et updated_at conservés comme chaînes. |
| `core/models/page.model.ts` | Page et ReferencePageQuery réutilisés ; page/page_size/search. |
| `features/companies/models/company-write.model.ts` | CompanyCreate : name/code obligatoires, description optionnelle nullable ; CompanyUpdate : champs optionnels nullables fidèles au transport PATCH. Le formulaire ne transmet pas name/code null. |
| `features/companies/models/companies-state.model.ts` | CompaniesQuery et union discriminée CompaniesState pour la liste. |
| `features/companies/data-access/companies-api.service.ts` | list délègue au GET paginé ReferenceDataApiService ; getById, create et update utilisent HttpClient pour GET détail, POST et PATCH. Aucun DELETE, cache, souscription interne ou retry automatique. |
| `features/companies/companies-list.facade.ts` | Provider local à CompaniesListComponent, signals en lecture seule, snapshot figé de la requête appliquée, switchMap et nettoyage takeUntilDestroyed. |
| `features/companies/pages/` | Liste, détail et page de formulaire commune aux modes création/modification. Détail et formulaire portent leurs états locaux. |
| `features/companies/components/company-form/` | FormGroup de présentation réutilisé ; entrées signal et événements submitted/cancelled/edited ; aucune requête HTTP. |
| `features/companies/styles/_company-actions.scss` | Mixin locale pour les liens d'action du PageHeader, sans système de composants partagé supplémentaire. |

Base HTTP relative `/api/v1` et proxy développement existants, sans changement
FastAPI. Le service transmet les payloads sans normalisation silencieuse.
Nom/code sont trimés par le formulaire, obligatoires et limités à 150/50 points
de code Unicode (`Array.from`), sans regex ASCII ni changement de casse.
Description facultative sans maximum inventé : intacte en création, elle est
omise ; modifiée, son texte est conservé et une chaîne vide devient null.
Le DTO PATCH conserve la possibilité transport de name/code null ; les contraintes
SQL NOT NULL et les limites de validation backend ne sont pas corrigées par l'UI.

### Liste, détail et états

La liste charge à l'entrée, avec page 1 et 20 lignes par défaut. L'URL appliquée
est la source de page/page_size/search ; les paramètres invalides sont normalisés
avant GET (page_size entre 1 et 100). La recherche explicite nom/code ne lance
pas de requête à chaque frappe, revient à la page 1 et omet search vide. Elle
couvre le serveur entier ; `%` et `_` sont signalés comme jokers, sans promesse
de recherche littérale ou insensible aux accents. Aucun tri supplémentaire.

La façade expose idle/loading/success/empty/error, annule les lectures obsolètes
et relance manuellement les paramètres appliqués sur erreur réseau/5xx. Empty
est fondé sur total=0, avec ou sans recherche ; items vide avec total positif
reste success, accompagné d'une action manuelle vers une page disponible.
Il n'y a ni boucle de rattrapage automatique ni filtrage local de la page.

Le détail valide l'identifiant comme entier positif sûr avant HTTP et suit ses
changements avec paramMap/switchMap/toSignal. Il distingue loading/success/error,
404 métier et identifiant invalide. Les lectures réseau/5xx sont relançables
manuellement. Nom, code, id, description intégrale et horodatages sont affichés
comme texte ; aucun KPI ou chargement des actifs. Sans fuseau explicite, les dates
ne sont pas converties ni déclarées UTC. Le contexte liste est typé et conservé
par les RouterLink, sans redirection arbitraire ou store global.

### Formulaire et écritures

CompanyFormPageComponent choisit le mode avec `data.mode === 'edit'`. En création,
aucun GET détail initial. En modification, un GET précède le formulaire et les
changements d'id annulent les GET obsolètes. Les états locaux sont loading,
load-error, idle, saving, success et error. PageHeader/LoadingState/ErrorState
existants sont réutilisés ; les erreurs ne sont pas présentées comme des vides.

Le PATCH compare les valeurs au DTO d'origine : seuls les champs réellement
changés sont envoyés ; name/code trimés, description vide volontaire → null.
Une soumission inchangée ou revenue à l'origine affiche une notice sans PATCH.
Un verrou saving empêche les doubles soumissions et la sortie par navigation.
CanDeactivate utilise `canLeave()` et la confirmation native pour les saisies
modifiées ; beforeunload protège fermeture/rechargement. Aucune protection ne
constitue une annulation garantie d'une transaction déjà traitée par le serveur.

409 est associé au champ Code, 422 aux champs connus et à un résumé. Le texte
serveur n'est pas interprété comme HTML. Une erreur PATCH 404 conserve la saisie
et ne recrée rien. Réseau/5xx après écriture = issue incertaine : pas de retry
automatique, saisie conservée, lien de vérification liste/détail dans un nouvel
onglet puis confirmation utilisateur avant nouvelle soumission explicite.
Ni mise à jour optimiste, ni idempotency-key, ni verrou de version serveur.

Un succès utilise l'id renvoyé, navigue vers le détail et transmet dans l'état
de navigation createdCompanyId ou updatedCompanyId pour la confirmation textuelle.
Le détail effectue son GET ; les lectures ultérieures retrouvent le serveur.
Aucun bus global, polling ou sélection automatique de société dans Dashboard.

### Notifications Nebular

`app.config.ts` configure NbToastrModule.forRoot au niveau application : position
TOP_RIGHT, durée 5 000 ms, pas de fermeture au clic ni icône (configuration
`hasIcon: false` et `icon: { icon: '' }`). Le service NbToastrService émet une
notification de succès unique après POST/PATCH réussi ; l'overlay survit à la
destruction de la page lors de la navigation. Aucun toast de succès sur échec,
absence de changement ou requête annulée. Une confirmation textuelle persistante
dans le détail reste indépendante du toast éphémère. Le thème existant ajoute
uniquement le mixin toast et des styles ciblés ; aucun nouveau package.

### Validation, dette et limites

Les suites existantes couvrent le service HTTP, la façade, les pages, le
formulaire et le routing différé dans le Shell : chargeurs, titres, sélection,
focus, contextes URL, erreurs, annulations, null/omission, Unicode, soumissions
et notifications. Ces tests utilisent HttpTestingController et des doubles
de service Toastr ; ils ne prouvent pas des écritures réelles dans PostgreSQL.
UI 3.7 a complété par lectures FastAPI réelles et simulations navigateur des
écritures/toasts ; le [bilan de validation](project-status.md#companies-mvp---validation-historique-ui-37)
précise les preuves responsive et leurs limites.

UI 3.7.1 : trois suites complètes séquentielles à 348/348, build production,
cinq tests du correctif Sass et contrôles des quatre expressions/huit breakpoints/
thème unique réussis. Le défaut initial 404 « zéro lien » reste non reproduit ;
les timeouts sous concurrence n'établissent pas une synchronisation manquante.
Le [rapport validé](ui-3.7.1-test-stability.md) recommande des validations
séquentielles ; aucune correction spéculative ni assertion réduite. Aucun test
ou build n'est relancé dans UI 3.8 documentaire.

Mesure historique UI 3.7 / UI 3.7.1 : initial **600,89 ko** pour **500 ko** de
warning, dépassement **100,89 ko**, dont **+32,48 ko après intégration de
NbToastrService**, inclus dans le total. Liste 12,57 ko, détail 7,77 ko, formulaire
commun 15,97 ko et Dashboard 45,38 ko restent différés. Budgets inchangés.
Les 26 artefacts comparés en UI 3.7.1 sont identiques par SHA-256.

DELETE est exclu à cause de la cascade ; l'endpoint backend n'est pas supprimé.
Les écritures POST/PATCH réelles, le zoom Companies 200/400 % et le lecteur
d'écran réel restent non validés. L'autorisation multi-entreprises n'est pas
démontrée. **Le module n'est pas prêt pour une production SaaS multi-tenant.**

## Sites MVP - architecture implémentée UI 4

Routes sous le Shell : liste, new, :siteId/edit, :siteId, dans cet ordre.
La sélection Sidebar reste Sites. Les routes de formulaire appellent canLeave
via CanDeactivate ; les pages écoutent aussi beforeunload.

- SitesListComponent et son URL appliquée pilotent SitesListFacade locale.
  SitesApiService.list délègue à ReferenceDataApiService.getSites ; company_id
  est obligatoire côté UI, sans entreprise choisie automatiquement. Catalogue
  d'entreprises paginé et référence par id vérifiée, recherche nom/code explicite,
  pagination serveur et distinction vide/page indisponible sont conservés.
- SiteDetailComponent lit le Site puis son parent réel avec des états distincts.
  Création et édition ont leurs états locaux ; switchMap annule les lectures
  obsolètes, les abonnements sont nettoyés. Aucun store global ni polling.
- SiteRead, Page et références core sont réutilisés. SitesApiService porte
  GET détail/POST/PATCH ; SiteCreate contient company_id, SiteUpdate uniquement
  name/code/description. La whitelist PATCH exclut aussi les propriétés en trop
  d'un SiteRead. Aucun DELETE dans ce service.
- SiteFormComponent est partagé entre deux pages d'orchestration distinctes,
  SiteCreateComponent et SiteEditComponent, plutôt que la page unique envisagée
  en conception. En édition, comparaison des valeurs brutes initiales/courantes,
  pas du seul dirty ; aucun PATCH sans différence. Code globalement unique,
  entreprise en lecture seule, dates de suivi hors FormGroup et payload.
- Description inchangée omise ; effacement manuel envoyé comme chaîne vide,
  bouton Retirer envoyé comme null. Les champs intacts, Unicode et dates sont
  préservés. Le formateur administratif partagé n'invente pas de fuseau.
- Contexte company_id/search/page/page_size validé et conservé entre pages Sites,
  sans returnUrl externe. Toast unique après navigation réussie et confirmation
  role=status sur la fiche ; protections contre doubles soumissions et abandon.
- 409 reste un conflit générique sans désigner arbitrairement Code. 422 mappe
  uniquement les champs body reconnus, avec messages locaux et focus. Erreurs
  conservant la saisie, aucun retry automatique ; issue réseau/5xx incertaine
  nécessitant vérification explicite. Aucun verrou de version serveur promis.

Les liens croisés Companies/Sites proposés en UI 4.1 ne sont pas implémentés ;
ils restent un écart documenté, sans changement de décision métier en UI 4.8.
La validation réelle DEV et les résultats 583 tests/build sont centralisés dans
le [statut Sites](project-status.md#sites-mvp---livraison-préparée-ui-48), avec la
réserve sur le dialogue natif, les dettes de bundle/secrets et l'absence
d'authentification/autorisation multi-tenant. UI 4.8 ne relance aucune validation
applicative. Les décisions D001 à D014 et la conception restent inchangées.

## Équipements MVP - architecture implémentée UI 5

La [conception UI 5.1](etape-ui-5.1-equipments.md), EQ-01 à EQ-07 approuvés,
reste la référence métier. Routes lazy dans EQUIPMENT_ROUTES : liste, new,
:equipmentId/edit, :equipmentId. Shell, Sidebar, titres et 404 sont préservés.

- EquipmentsListFacade locale coordonne références paginées, appartenance du
  site, annulation des lectures et états sélection attendue/loading/vide/erreur.
  Aucune sélection automatique ni GET liste sans site_id valide. Recherche
  explicite nom/code/type, filtres statut et criticité, pagination serveur et
  tailles 20/50/100. Aucun tri local ou filtre Equipment company_id.
- Contexte validé company_id/site_id/search/status/criticality/page/page_size
  conservé entre liste, détail et formulaires. Le parent réel est indépendant de
  ce contexte de retour. SiteDetail propose Voir les équipements ; le détail
  Equipment lie son site réel et affiche Entreprise de rattachement.
- EquipmentsApiService réutilise EquipmentRead/Status/Criticality core, Page et
  ReferenceDataApiService pour les GET. EquipmentCreate exige site_id ;
  EquipmentUpdate limite les six champs name/code/equipment_type/status/
  criticality/description. Whitelist POST/PATCH, aucun company_id, métadonnée,
  descendant ou site_id en PATCH ; aucune méthode DELETE.
- EquipmentForm est partagé par EquipmentCreate et EquipmentEdit. Nom/code/type
  libres et non blancs, limites Unicode 150/100/100 ; casse préservée, trim à la
  création. Défauts operational/medium en création. Édition comparant les valeurs
  brutes initiales/courantes : espaces et Unicode intacts préservés, valeurs
  restaurées exclues, aucun PATCH sans différence. Description inchangée omise,
  effacée vide, retrait explicite null. Aucun déplacement d'équipement.
- GET Equipment puis Site puis Company réels ; détail utilisable malgré une
  erreur parent distincte, édition bloquée si parent non vérifié. En édition,
  rattachement en lecture seule, champs modifiables, suivi sans contrôle FormGroup,
  puis actions. Dates administratives via formateur partagé, sans fuseau inventé.
- Gardes CanDeactivate/beforeunload, blocage pendant saving et double soumission,
  focus du premier champ invalide, messages sûrs et saisies conservées. Erreurs
  409 génériques, 422 limitées aux champs body reconnus ; réseau/5xx incertains
  sans retry automatique. Navigation échouée après succès : lien de récupération,
  formulaire verrouillé, aucune réécriture. Toast unique après navigation réussie
  et confirmation persistante role=status sur le détail.
- _actions.scss reprend la référence Nouvelle entreprise ; _buttons.scss partage
  hover/focus/active, transitions, disabled/loading et mouvement réduit. Hiérarchie
  primaire/secondaire conservée, plus décoratif, noms accessibles et aides intacts,
  aucun tooltip redondant ajouté. Voir le [rapport boutons](ui-buttons-harmonization.md).

Les rapports [UI 5.2](ui-5.2-equipments-data-access.md),
[UI 5.3](ui-5.3-equipments-list.md), [UI 5.4](ui-5.4-equipment-detail.md),
[UI 5.5](ui-5.5-equipment-create.md) et [UI 5.6](ui-5.6-equipment-edit.md)
conservent leurs tests HTTP simulés et observations aux six largeurs CSS
1440/1024/1023/768/390/320 px. UI 5.6.1 précise la vérification finale de l'ordre.
Le dialogue natif reste réservé ; ces contrôles ne valent pas audit complet
lecteur d'écran, zoom ou accessibilité. Appui maintenu et mouvement réduit n'ont
pas été émulés dans l'audit navigateur des boutons.

[UI 5.7](ui-5.7-equipments-integration.md) ajoute les deux écritures réelles et
la persistance SQL ; 409/422 d'écriture et concurrence restent simulés. Références
864 tests / build / 604,81 ko et dettes centralisées dans le
[statut Équipements](project-status.md#équipements-mvp---livraison-préparée-ui-58).
Aucun endpoint ML ou descendant appelé par cette fiche. Aucun contrôle
d'authentification/autorisation multi-tenant ou verrou de version serveur ajouté.

## Autres composants partagés envisagés

La liste suivante décrit des besoins ultérieurs, sans engagement d'implémentation
dans UI 1.7.2 :

- KPI Card transversale (la carte de feature Dashboard est déjà implémentée)
- Status Badge
- Priority Badge
- Health Score Gauge
- Risk Gauge
- RUL Indicator
- Pagination
- Filter Bar

## Règles

1. Réutiliser les composants communs.
2. Ne pas dupliquer les appels API.
3. Ne pas mettre de logique métier complexe dans les composants.
4. Utiliser les types TypeScript correspondant aux schémas backend.
5. Respecter les contrats API existants.
6. Gérer loading, error et empty state.
7. Garder une navigation cohérente.
8. Concevoir les pages avant leur implémentation.

## Ordre d'implémentation

Le layout, Dashboard, Companies et Sites sont intégrés dans `main` (`667fe5b`).
Équipements MVP est implémenté sur feature/frontend-equipments (`39e2f0d`).
UI 5.8 prépare la [livraison documentaire](ui-5.8-equipments-delivery.md), avant
validation du commit puis de toute fusion. Les conceptions historiques restent
conservées ; les écrans métier et indicateurs prédictifs futurs nécessiteront
une conception et une autorisation distinctes. Aucun module suivant commencé.
