# UI Design - Industrial Predict AI

## Objectif

Définir les règles visuelles et UX d'Industrial Predict AI afin de garantir une interface professionnelle, cohérente et adaptée aux usages industriels.

Le design doit permettre à un utilisateur de comprendre rapidement :

- l'état global du parc industriel ;
- les équipements nécessitant une attention ;
- les niveaux de risque ;
- les prédictions disponibles ;
- les recommandations de maintenance ;
- les actions prioritaires.

---

## Principes généraux

L'interface doit être :

- professionnelle ;
- claire ;
- sobre ;
- lisible ;
- orientée données ;
- adaptée aux environnements industriels ;
- cohérente entre les différentes pages ;
- utilisable principalement sur desktop et tablette.

Les informations critiques doivent être visibles immédiatement.

La couleur ne doit jamais être le seul moyen de transmettre une information.

---

## Structure globale

L'application utilise une structure SaaS classique :

```text
┌─────────────────┬──────────────────────────────────────┐
│                 │                                      │
│     Sidebar     │             Header                   │
│                 │                                      │
│                 ├──────────────────────────────────────┤
│                 │                                      │
│                 │          Contenu principal           │
│                 │                                      │
│                 │                                      │
└─────────────────┴──────────────────────────────────────┘
```

## Fondation visuelle validée — UI 1.1 à UI 1.6

La Sidebar bleu marine, la sélection bleue, le Header blanc, le fond principal
gris très clair et les cards blanches constituent les principes validés.
L'identité produit est compacte ; les entrées de navigation comportent des
icônes SVG locales cohérentes, sans bibliothèque d'icônes supplémentaire.
Les espacements, l'alignement et les cibles clavier restent lisibles.

Un seul thème Nebular clair personnalisé est émis. Les styles ciblent les
composants utilisés ; aucun CSS Nebular précompilé concurrent n'est chargé.
Les tokens sont centralisés dans `frontend/src/styles/_tokens.scss`.

| Usage | Valeur présente dans le code |
| --- | --- |
| Sidebar | `#14243d` ; texte `#ffffff` |
| Navigation active | `#2563eb` |
| Header et surfaces/cards | `#ffffff` |
| Fond principal | `#f4f6fa` |
| Texte principal / secondaire | `#17253b` / `#56657b` |
| Bordures | `#e1e7ef` |
| Typographie | Segoe UI, Arial, sans-serif |
| Espacements | 0.25 / 0.5 / 1 / 1.5 / 2 rem |

Ces valeurs décrivent l'implémentation actuelle. Les tokens conservent leur
mention de valeurs provisoires dans le code ; cette documentation ne prétend
pas prouver une comparaison pixel-perfect avec la maquette originale.
Les couleurs fonctionnelles (healthy, vigilance, dégradation, critique)
restent des intentions pour les futurs écrans métier.

## Header global et PageHeader : deux responsabilités distinctes

Le `HeaderComponent` existant appartient au Shell et persiste entre les pages.
Il affiche le titre issu des métadonnées Router, commande la Sidebar avec un
bouton accessible et expose des emplacements Notifications et Profil utilisateur
compacts, explicitement « À venir » et non interactifs. Aucun compteur,
notification ni identité utilisateur n'est inventé. Aucun fil d'Ariane n'est
affiché en l'absence de métadonnées définissant une hiérarchie cohérente.

Le futur `PageHeaderComponent` appartient au contenu d'une page. Il fournit
son `<h1>`, sa description éventuelle et les actions spécifiques projetées
par cette page. Il ne commande pas la Sidebar et ne remplace pas le Header
global. La page consommatrice fournit son contenu et organise sa hiérarchie
de titres sémantiques.

## Contrats visuels et accessibles validés UI 1.7.1 — non implémentés

Les quatre composants ci-dessous sont des spécifications de conception.
UI 1.7.2 n'a pas commencé. Leurs contrats techniques sont également décrits
dans `frontend-architecture.md`.

### PageHeaderComponent

Emplacement prévu : `shared/components/page-header/`.
Entrée obligatoire `title: string`, entrée optionnelle `description?: string`.
Le titre utilise `<h1>` et la description n'est affichée que si renseignée.
Les actions sont fournies par `ng-content`, alignées à droite sur grand écran
et repositionnées sous le titre sur petit écran. Aucun appel API ni logique métier.

### LoadingStateComponent

Emplacement prévu : `shared/components/loading-state/`.
Entrée optionnelle `message: string`, par défaut « Chargement des données… ».
L'indicateur visuel s'accompagne de `role="status"` pour annoncer le chargement.
L'animation respecte la réduction du mouvement demandée par l'utilisateur.
Le composant ne déclenche aucune requête HTTP.

### EmptyStateComponent

Emplacement prévu : `shared/components/empty-state/`.
Entrées `title: string` et `message: string`, illustration ou icône décorative
optionnelle, projection facultative d'une action fournie par la page métier.
L'absence de données est explicitement distincte d'une erreur réseau.
Aucun appel API ni création automatique de données.

### ErrorStateComponent

Emplacement prévu : `shared/components/error-state/`.
Entrées `title: string`, `message: string` et `retryable: boolean`.
L'événement de sortie `retry` est émis uniquement lors de l'activation de
« Réessayer ». Ce bouton est visible uniquement si `retryable` est vrai et
reste accessible au clavier. Le message utilise `role="alert"` ou un mécanisme
équivalent adapté, sans répétition excessive. La relance HTTP appartient à
la page consommatrice, jamais au composant.

### Principes communs

Les composants seront standalone, en TypeScript strict, légers et indépendants
du backend et des modules métier. Ils réutiliseront les tokens SCSS et le thème
existant, sans nouvelle dépendance. HTML sémantique, focus visible, contrastes
et accessibilité clavier sont requis ; les tests unitaires sont obligatoires
lors de l'implémentation.

Les états `loading`, `success`, `empty` et `error` restent distincts.
`success` correspond au rendu normal des données par la page métier et ne
nécessite pas de composant partagé spécifique. Aucune donnée fictive ne doit
être présentée comme une donnée industrielle réelle.

## Navigation accessible existante

Les états actifs suivent Angular Router, y compris le détail équipement.
Rapports et Administration sont non cliquables et portent le texte « À venir ».
La 404 conserve le Shell et l'URL inconnue sans sélectionner une section erronée.
Le lien d'évitement déplace réellement le focus vers `main#main-content`
sans altérer l'URL. Le focus après navigation respecte les fragments et les
interactions utilisateur. Le responsive avancé du layout reste une étape future.
