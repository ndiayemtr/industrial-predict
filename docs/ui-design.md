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

## Fondation visuelle validée - UI 1.1 à UI 1.6

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

## Contrats visuels et accessibles UI 1.7 - implémentés et validés

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

## Header et Sidebar selon la largeur - UI 1.8.2

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

## Validations et limites d'accessibilité - UI 1.8.3 / UI 1.8.4

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

UI 1.8 est terminée, commitée dans `12a18c3` et fusionnée via `acd872b`.
Les résultats ci-dessus sont historiques et ne sont pas relancés en UI 2.1.1.
UI 2.1 a validé la conception du Dashboard V1 ; UI 2.2 à UI 2.7.1 l'ont livré
et validé sur `feature/frontend-dashboard`. La fusion Dashboard dans main reste
à réaliser ; UI 2.8 finalise la documentation sans changement visuel.

## Dashboard V1 - présentation implémentée et validée

Les règles suivantes sont appliquées au Dashboard livré. DASH-01 à DASH-06
sont enregistrées dans D014 de [decisions.md](decisions.md). Le contrat et
l'architecture présente figurent dans [frontend-architecture.md](frontend-architecture.md).

### Composition livrée

Le Shell et son Header restent inchangés. PageHeader fournit le seul h1
« Dashboard », une description et les actions de page projetées. Le périmètre,
la période UTC avec fin exclusive et `calculated_at` restent lisibles.
Un formulaire de filtres précède les cinq sections :

| Section | Contenu affiché |
| --- | --- |
| Synthèse | Six cartes : équipements, capteurs actifs, couverture par capteurs actifs, mesures reçues, maintenances ouvertes et retards de démarrage ; périmètre et période au-dessus des sections |
| Équipements | Statuts et criticités, part opérationnelle, nombre high/critical et nombre high/critical indisponibles ; aucune liste nominative non fournie par le contrat |
| Capteurs | Statut déclaré, couverture en capteurs actifs, capteurs actuellement actifs ayant émis sur la période |
| Mesures | Qualité déclarée, volumes quotidiens UTC, derniers relevés par capteur avec valeur, unité, qualité, date et âge au calcul |
| Maintenance | Charge ouverte et priorités, retards de démarrage, terminées par type, part corrective, arrêt déclaré avec couverture et anomalies de dates |

Cartes KPI, tableaux de répartition et listes de relevés (DASH-02), avec texte
et effectifs accessibles ; aucune bibliothèque graphique ajoutée. Aucun Health
Score, RUL, risque de panne ou alerte fictive (DASH-01). L'affichage monétaire
est différé faute de devise (DASH-03), même si `maintenance.cost` est disponible.

### Portée et précision des libellés

| Libellé | Indicateurs concernés |
| --- | --- |
| État actuel | Inventaire, statuts, criticité, couverture capteurs, maintenances ouvertes ; anomalies de dates manquantes sur le périmètre |
| Sur la période | Volume/qualité des mesures, capteurs ayant émis, maintenances terminées, part corrective et arrêt déclaré dans `[start_time, end_time)` |
| Au calcul | Dernières mesures et leur âge, retards de démarrage, référence à `calculated_at` |

Les derniers relevés ne sont pas restreints à la période choisie : l'indiquer
dans cette section pour éviter une interprétation trompeuse. Ne pas appeler
« disponibilité » la part opérationnelle, ni « santé » la criticité, ni « télémétrie
complète » le volume reçu. Un capteur actif n'est pas nécessairement communicant.

Un vrai zéro s'affiche comme zéro ; un pourcentage null comme « Non calculable » ;
une valeur absente comme « Non renseignée ». Signaler les valeurs inconnues dans
« Autres / non reconnus », sans leur attribuer un état sain ou critique.
Une somme partielle affiche sa couverture de saisie, effectifs inclus.
La couleur ne remplace jamais les libellés, unités ou avertissements explicites.

### Filtres et états accessibles livrés

Entreprise obligatoire sans valeur inventée ; site et équipement facultatifs.
Le sélecteur d'équipement est proposé après choix du site (DASH-04), simple
politique UX qui ne supprime pas le support API d'un équipement sans site.
Labels explicites, ordre clavier naturel, focus visible et bouton Appliquer.
Les sélecteurs consomment les listes paginées : compteurs chargés/total et boutons
« Charger davantage » lorsqu'une page suivante existe. Aucun champ de recherche
de références n'est implémenté dans ce formulaire.
Changement d'entreprise : site/équipement effacés ; changement de site :
équipement effacé. Indiquer UTC et la fin exclusive dans les champs de période.

Sept jours glissants UTC (168 heures) sont le préréglage initial (DASH-05),
avec une fin fixée à l'application et sans évolution automatique après la requête.
Une période personnalisée conserve ses bornes validées. Au départ, inviter à
sélectionner une entreprise ; ne pas confondre cette invitation avec un résultat
vide de l'API, ni envoyer un GET Dashboard incomplet.

Réutiliser LoadingState pour loading (une seule annonce et reduced-motion),
EmptyState pour l'absence globale d'actifs, textes explicites pour les sections
sans lignes, ErrorState pour error
(relance manuelle réseau/serveur, correction des filtres sinon). success est le
rendu réel des cinq sections ; une période sans mesures n'efface pas le parc.
Conserver filtres, titres et focus pendant les états, sans annonces répétitives
ni déplacement automatique de focus après un simple rechargement.

### Responsive et limites de validation

Réutiliser marine, bleu actif, surfaces blanches, fond gris clair, typographie
et espacements des tokens ; aucun second thème. Cartes et filtres se replient
selon l'espace disponible, textes longs sans débordement ; derniers relevés
lisibles à 320/390 px. Les barres conservent des valeurs textuelles et les tableaux
une sémantique compréhensible. Le breakpoint du Shell reste 1024 px, inclus en desktop.

UI 2.7 a contrôlé le Dashboard à 1440/1024/1023/768/390/320 px CSS, hauteur 900 px,
sans débordement horizontal global, avec un seul h1 et huit tableaux dotés de
captions/en-têtes. Les cartes et les listes se replient selon la place disponible ;
les relevés sont présentés en listes avec définitions pour rester lisibles à 320 px.
Menu mobile : Tab/Shift+Tab, Échap, focus restauré et contenu inert ; skip link
activé par Entrée vers main-content, sans changement d'URL. Actualiser conserve
le focus et les filtres appliqués. Les états de chargement/erreur utilisent les
rôles status/alert des composants partagés et aria-busy sur la zone de résultats.

Les vérifications réelles PETROSEN couvrent idle/success, zéros, ratios null,
capteur sans relevé et dernier relevé hors période. Loading Dashboard, empty,
erreurs UI/retry, catégories inconnues et couverture partielle sont validés par
tests simulés, sans prétendre à des observations réelles de tous ces cas.
Les montants ne sont pas affichés. La précision des valeurs et l'âge API en
secondes sont conservés, sans seuil d'alerte ni compteur de fraîcheur live.
UI 2.7.1 remplace « 1 équipements » par la formulation neutre
« Équipements avec capteur actif : X sur Y », valeurs API inchangées, y compris 0/0.

### Zoom réel et limites restantes

La validation manuelle utilisateur du zoom réel **100 %, 200 % et 400 %** en
UI 1.8.4 concerne le socle. Elle est conservée comme historique et ne prouve
pas à elle seule le rendu du Dashboard V1 désormais enrichi.
En UI 2.7, Ctrl+0 a été appliqué dans le navigateur intégré ; ses raccourcis de
zoom sont restés sans effet, sans variation de viewport ou de ratio de pixels.
Le pourcentage exact n'est pas exposé : aucun zoom réel 200/400 % du Dashboard
n'est revendiqué par l'assistant, et aucun redimensionnement CSS n'est assimilé
à un zoom. En réponse à la clarification UI 2.8, **l'utilisateur confirme avoir
effectué et validé le zoom réel du Dashboard V1 à 100 %, 200 % et 400 %**.
Cette confirmation concerne bien le Dashboard enrichi, distinctement de
l'historique UI 1.8, et complète la limite de l'outillage de l'assistant.
Il s'agit d'un contrôle manuel utilisateur, pas d'un test automatisé.
**Lecteur d'écran réel non testé** : les contrôles DOM/ARIA/clavier ne valent
ni validation vocale ni certification d'accessibilité.

Le warning actuel est **565,38 ko initial pour 500 ko** ; références Dashboard
différé 52,00 ko en UI 2.6, 51,98 ko après UI 2.7.1. Les budgets restent inchangés.
