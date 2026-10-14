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
- HttpClient prévu pour l'intégration API, pas encore configuré dans l'application

État vérifié le 14 octobre 2026 sur `feature/frontend-shared-components`,
HEAD `e3a2a2c`, avec les corrections UI 1.8.2 non commitées.
Voir `decisions.md` pour les limites de compatibilité.

## Structure réellement présente — UI 1.1 à UI 1.8.3

```text
frontend/
├── src/app/
│   ├── app.component.* / app.config.ts / app.routes.ts / app.routes.spec.ts
│   ├── layout/
│   │   ├── shell/
│   │   ├── sidebar/
│   │   ├── header/
│   │   └── navigation/ (modèle et configuration)
│   ├── features/dashboard/ (DashboardPlaceholderComponent)
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

## Politique responsive réelle — UI 1.8.2

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
| `/` | — | Redirection vers `/dashboard`, `pathMatch: 'full'` | Dashboard après redirection |
| `/dashboard` | Dashboard | DashboardPlaceholderComponent | Dashboard, correspondance exacte |
| `/companies` | Entreprises | FeaturePlaceholderComponent | Entreprises |
| `/sites` | Sites | FeaturePlaceholderComponent | Sites |
| `/equipments` | Équipements | FeaturePlaceholderComponent | Équipements |
| `/sensors` | Capteurs | FeaturePlaceholderComponent | Capteurs |
| `/measurements` | Mesures | FeaturePlaceholderComponent | Mesures |
| `/maintenance` | Maintenance | FeaturePlaceholderComponent | Maintenance |
| `/predictions` | Prédictions | FeaturePlaceholderComponent | Prédictions |
| `/recommendations` | Recommandations | FeaturePlaceholderComponent | Recommandations |
| `/equipments/:equipmentId` | Détail équipement | FeaturePlaceholderComponent | Équipements |
| `**` (dernière route) | Page introuvable | NotFoundComponent, `data.isNotFound: true` | Aucune sélection trompeuse |

Chaque page a un titre de document `pageTitle | Industrial Predict AI`.
Le paramètre `equipmentId` est un paramètre Router ; aucun équipement n'est
encore récupéré ou validé par appel backend. Un changement d'identifiant
sans retour à la liste est couvert par les tests de routing.

Rapports et Administration n'ont ni chemin dans la navigation ni route dédiée.
Ils sont désactivés et libellés « À venir ». `/reports`, `/administration` et
les autres URL inconnues affichent la 404 dans le Shell, sans changer l'URL.
Pour `/equipments/42/inconnu`, le marqueur 404 force une correspondance
exacte des liens et évite une sélection Équipements incorrecte ; le détail
valide `/equipments/42` conserve la sélection de section.

Le Shell, le Dashboard placeholder, le placeholder commun et la 404 utilisent
`loadComponent` avec import dynamique. Il n'y a pas de module métier chargé
par `loadChildren` ni de préchargement configuré. Les huit destinations métier
et le détail partagent le même placeholder, sans créer neuf pages définitives.
Les tests contrôlent les chargeurs différés sans dépendre des noms de chunks.
Les placeholders n'affichent aucun faux KPI et ne déclenchent aucun appel API.

## Structure générale cible

Les dossiers métier autres que `dashboard` et le dossier `core` ci-dessous
constituent la cible, et ne sont pas encore implémentés.

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

Les fonctionnalités ci-dessous sont des objectifs métier futurs ; les routes
actuelles ne rendent que des placeholders.

### Dashboard

- KPI globaux
- état de santé des équipements
- risques de panne
- alertes critiques
- activité récente

### Équipements

- liste
- filtres
- Health Score
- Failure Risk
- RUL
- statut
- dernière maintenance

### Détail équipement

Onglets :

- Vue d'ensemble
- Capteurs
- Mesures
- Prédictions
- Recommandations
- Maintenance
- Documents

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
Ce flux est la cible d'intégration ; aucune façade ni service API frontend
de cette liste n'est encore implémenté.

## Gestion API

Les appels HTTP sont centralisés dans des services dédiés.

Exemples :

- EquipmentApiService
- DashboardApiService
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
dans `e3a2a2c`. UI 1.7 est terminée. Ils ne sont pas encore intégrés aux pages
métier définitives et ne créent aucune route de démonstration persistante.

Les contrats suivants ont été validés dans la discussion de conception
Industrial Predict AI puis transmis pour cette synchronisation documentaire.

### PageHeaderComponent — implémenté en UI 1.7.2

- Emplacement : `shared/components/page-header/`.
- Entrée obligatoire : `title: string` ; entrée optionnelle : `description?: string`.
- Projection `ng-content` pour les actions spécifiques à la page.
- Titre sémantique `<h1>` ; description rendue uniquement si renseignée.
- Actions à droite sur grand écran, sous le titre sur petit écran.
- Aucun appel API ni logique métier. Il ne remplace pas le Header global du Shell.
- API : `input.required<string>()` pour title, `input<string>()` pour description.
- Une description vide ou composée uniquement d'espaces n'est pas rendue.

### LoadingStateComponent — implémenté en UI 1.7.3

- Emplacement : `shared/components/loading-state/`.
- Entrée optionnelle : `message: string`, valeur par défaut « Chargement des données… ».
- Indicateur visuel et `role="status"` pour annoncer le chargement.
- Animation respectant les préférences de réduction du mouvement.
- Aucun déclenchement de requête HTTP.
- Une entrée signal avec défaut et un message de repli si le texte est vide ;
  une seule région status, `aria-atomic="true"`, indicateur décoratif `aria-hidden`.

### EmptyStateComponent — implémenté en UI 1.7.4

- Emplacement : `shared/components/empty-state/`.
- Entrées : `title: string` et `message: string`.
- Illustration ou icône décorative optionnelle.
- Projection facultative d'une action fournie par la page métier.
- État distinct d'une erreur réseau ; aucun appel API ni création automatique de données.
- title et message utilisent `input.required<string>()` ; titre sémantique `<h2>`.
- Entrée optionnelle `icon: LocalIconName | undefined` : réutilisation de
  `IconComponent` et de son entrée existante `name`, sans enrichir le catalogue.

### ErrorStateComponent — implémenté en UI 1.7.5

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

## Validation UI 1.8.3 et finalisation UI 1.8.4

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

## Autres composants partagés envisagés

La liste suivante décrit des besoins ultérieurs, sans engagement d'implémentation
dans UI 1.7.2 :

- KPI Card
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

1. Layout global
2. Dashboard
3. Liste des équipements
4. Détail équipement
5. Prédictions
6. Recommandations
7. Maintenance
8. Autres modules
