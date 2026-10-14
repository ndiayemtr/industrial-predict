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
HEAD `82fc073`. Voir `decisions.md` pour les limites de compatibilité.

## Structure réellement présente — UI 1.1 à UI 1.6

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
existant, sans le recréer. Le header se situe à droite de la sidebar.

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
de routing (placeholder et 404). Les quatre nouveaux composants de présentation
seront placés dans `shared/components/`, distinctement de ces pages.
Ils ne sont pas encore implémentés ; UI 1.7.2 n'a pas commencé.

Les contrats suivants ont été validés dans la discussion de conception
Industrial Predict AI puis transmis pour cette synchronisation documentaire.

### PageHeaderComponent — prévu

- Emplacement : `shared/components/page-header/`.
- Entrée obligatoire : `title: string` ; entrée optionnelle : `description?: string`.
- Projection `ng-content` pour les actions spécifiques à la page.
- Titre sémantique `<h1>` ; description rendue uniquement si renseignée.
- Actions à droite sur grand écran, sous le titre sur petit écran.
- Aucun appel API ni logique métier. Il ne remplace pas le Header global du Shell.

### LoadingStateComponent — prévu

- Emplacement : `shared/components/loading-state/`.
- Entrée optionnelle : `message: string`, valeur par défaut « Chargement des données… ».
- Indicateur visuel et `role="status"` pour annoncer le chargement.
- Animation respectant les préférences de réduction du mouvement.
- Aucun déclenchement de requête HTTP.

### EmptyStateComponent — prévu

- Emplacement : `shared/components/empty-state/`.
- Entrées : `title: string` et `message: string`.
- Illustration ou icône décorative optionnelle.
- Projection facultative d'une action fournie par la page métier.
- État distinct d'une erreur réseau ; aucun appel API ni création automatique de données.

### ErrorStateComponent — prévu

- Emplacement : `shared/components/error-state/`.
- Entrées : `title: string`, `message: string`, `retryable: boolean`.
- Sortie : événement `retry`, uniquement lorsque l'utilisateur active « Réessayer ».
- Message accessible avec `role="alert"` ou mécanisme équivalent adapté, sans répétition excessive.
- Bouton « Réessayer » accessible au clavier, visible uniquement si `retryable` est vrai.
- Aucun appel HTTP dans le composant ; la page consommatrice gère la relance.

### Principes communs et validation d'implémentation

Angular 21 standalone, TypeScript strict, SCSS avec les tokens existants,
HTML sémantique, contrastes et navigation clavier. Ces composants restent
légers, indépendants des modules métier et du backend FastAPI, sans nouvelle
dépendance. Les tests unitaires seront obligatoires lors de UI 1.7.2 : contrats
d'entrée, rendu conditionnel, projection, sémantique accessible et émission
de `retry` seulement sur action utilisateur.

Les états restent distincts : `loading`, `success`, `empty`, `error`.
`success` est le rendu normal des données par la page métier ; aucun composant
partagé spécifique n'est prévu pour cet état.

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
