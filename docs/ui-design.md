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

Le `PageHeaderComponent` livré en UI 1.7 appartient au contenu d'une page. Il fournit
son `<h1>`, sa description éventuelle et les actions spécifiques projetées
par cette page. Il ne commande pas la Sidebar et ne remplace pas le Header
global. La page consommatrice fournit son contenu et organise sa hiérarchie
de titres sémantiques.

## Contrats visuels et accessibles UI 1.7 — implémentés et validés

Les contrats conçus en UI 1.7.1 sont implémentés en UI 1.7.2 à UI 1.7.5,
validés globalement en UI 1.7.6 et commités dans `e3a2a2c`.
Leurs contrats techniques sont également décrits
dans `frontend-architecture.md`.

### PageHeaderComponent

Emplacement : `shared/components/page-header/`.
Entrée obligatoire `title: string`, entrée optionnelle `description?: string`.
Le titre utilise `<h1>` et la description n'est affichée que si renseignée.
Les actions sont fournies par `ng-content`, alignées à droite sur grand écran
et repositionnées sous le titre sur petit écran. Le composant utilise une
disposition en colonne par défaut et en ligne dès **48 rem** (768 px avec
la taille de police par défaut). Ce seuil de présentation locale est distinct
du seuil 1024 px du Shell. Aucun appel API ni logique métier.

### LoadingStateComponent

Emplacement : `shared/components/loading-state/`.
Entrée optionnelle `message: string`, par défaut « Chargement des données… ».
L'indicateur visuel s'accompagne de `role="status"` pour annoncer le chargement.
L'animation respecte la réduction du mouvement demandée par l'utilisateur.
Le composant ne déclenche aucune requête HTTP.

### EmptyStateComponent

Emplacement : `shared/components/empty-state/`.
Entrées `title: string` et `message: string`, illustration ou icône décorative
optionnelle, projection facultative d'une action fournie par la page métier.
Le titre utilise `<h2>` ; l'icône optionnelle est fournie via l'entrée `icon`
typée `LocalIconName` et reste décorative. L'absence de données est explicitement distincte d'une erreur réseau.
Aucun appel API ni création automatique de données.

### ErrorStateComponent

Emplacement : `shared/components/error-state/`.
Entrées obligatoires `title: string` et `message: string`, `retryable: boolean`
avec valeur par défaut `false`. Le titre utilise `<h2>`.
L'événement de sortie `retry` est émis uniquement lors de l'activation de
« Réessayer ». Ce bouton est visible uniquement si `retryable` est vrai et
reste accessible au clavier. Le message utilise `role="alert"` ou un mécanisme
équivalent adapté, sans répétition excessive ; l'implémentation utilise une
seule région alert contenant le titre et le message, sans le bouton.
La relance HTTP appartient à
la page consommatrice, jamais au composant.

### Principes communs

Les composants sont standalone, en TypeScript strict, légers et indépendants
du backend et des modules métier. Ils réutilisent les tokens SCSS et le thème
existant, sans nouvelle dépendance. HTML sémantique, focus visible, contrastes
et accessibilité clavier sont requis ; leurs contrats sont couverts par les
tests unitaires existants.

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
interactions utilisateur.

## Header et Sidebar selon la largeur — UI 1.8.2

| Largeur CSS | Sidebar | Header global |
| --- | --- | --- |
| **>= 1024 px**, seuil inclus | Latérale, ouverte initialement, repli manuel possible | Design desktop conservé : titre, identité secondaire et emplacements Notifications/Profil « À venir » |
| **< 1024 px** | Fermée initialement ; panneau superposé à l'ouverture, contenu non comprimé | Bouton menu et titre prioritaires ; identité secondaire et emplacements Notifications/Profil masqués, espacements réduits |

Le mode vient du Shell. Les couleurs marine, bleu actif, blanc et gris clair
et les tokens existants restent identiques entre modes ; aucun thème concurrent
n'est ajouté. Le Header conserve une hauteur de 4,5 rem ; le titre se replie
si nécessaire et reste lisible avec les titres actuels à 320 et 390 px.
Le Header n'ajoute pas de `<h1>` : le titre de page appartient au contenu,
avec PageHeader lorsqu'une page consommatrice l'utilise.

Le panneau mobile conserve la navigation avec ses icônes et libellés.
Il fournit un bouton « Fermer la navigation », une couche de fond cliquable
à l'extérieur, la fermeture par Échap et un confinement clavier via le CDK.
À l'ouverture, le focus se place sur le bouton de fermeture ; l'arrière-plan
est inert et le scroll du panneau reste disponible, y compris à faible hauteur.
Après fermeture sans navigation, le focus revient au bouton du Header.
Après navigation réussie, le panneau se ferme et la politique de focus du
contenu s'applique. Les changements de mode ne laissent pas de fond bloquant.

## Validations et limites d'accessibilité — UI 1.8.3 / UI 1.8.4

- Validation navigateur : 1440, 1024, 1023, 768, 390 et 320 px, hauteur 900 px,
  sur Dashboard, détail équipement et 404, menu ouvert/fermé ; pas de débordement
  horizontal observé. Transitions répétées, clic extérieur, Échap, Tab/Shift+Tab,
  focus visibles et skip link contrôlés.
- **Zoom réel 100 %, 200 % et 400 % validé manuellement par l'utilisateur** :
  les cinq vérifications ont été déclarées OK dans la demande UI 1.8.4.
  L'assistant n'attribue pas cette validation à son navigateur intégré ; ses
  essais à 720 × 450 et 360 × 225 px ne prouvent que le reflow à ces dimensions.
- **116 tests Angular**, **5 tests de correctif Sass** et build production
  réussis. Les contrôles Sass valident les breakpoints et le thème unique.
- Bundle initial **504,68 ko**, budget d'avertissement **500 ko** : avertissement
  conservé et seuils inchangés, sans masquage de dépréciations Sass.
- **Lecteur d'écran réel non testé**. La sémantique ARIA, le clavier et le focus
  ont été contrôlés ; cela ne constitue pas une certification d'accessibilité
  ni une preuve de comportement vocal sur chaque lecteur d'écran.

UI 1.8.1 à UI 1.8.3 sont validées ; UI 1.8.4 finalise les documents et contrôles
avant validation du livrable et autorisation du commit. Les écrans métier et
l'intégration API restent une phase ultérieure non commencée.
