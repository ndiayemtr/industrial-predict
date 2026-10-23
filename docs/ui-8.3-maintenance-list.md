# UI 8.3 - Liste Maintenance

23 octobre 2026. Branche `feature/frontend-maintenance`, HEAD initial `740a947`,
dépôt initial propre. Implémentation de la consultation paginée uniquement.

## Périmètre et fichiers

Trois fichiers existants adaptés :
- [Routage global](../frontend/src/app/app.routes.ts) : remplacement du seul placeholder Maintenance par un chargement lazy.
- [Tests Sidebar](../frontend/src/app/layout/sidebar/sidebar.component.spec.ts) : remplacement de l’attente historique du placeholder par la liste réelle et son lien actif.
- [Tests du routage global](../frontend/src/app/app.routes.spec.ts) : invariant de chargement différé.

Dix nouveaux fichiers, présent rapport compris :
- [Routes Maintenance](../frontend/src/app/features/maintenance/maintenance.routes.ts) et [tests Shell](../frontend/src/app/features/maintenance/maintenance.routes.spec.ts).
- [État de liste](../frontend/src/app/features/maintenance/models/maintenance-state.model.ts).
- [Façade locale](../frontend/src/app/features/maintenance/maintenance-list.facade.ts) et [tests](../frontend/src/app/features/maintenance/maintenance-list.facade.spec.ts).
- Page standalone : [TypeScript](../frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.ts), [HTML](../frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.html), [SCSS](../frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.scss) et [tests](../frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.spec.ts).

Les modèles et le service API UI 8.2 restent inchangés. Aucun composant ou style
partagé modifié. Réutilisation de ReferenceDataApiService, Page, PageHeader,
LoadingState, EmptyState, ErrorState, businessReferenceLabel, tokens SCSS et du
mixin actions.navigation-action. Les fonctions pures de période Measurements
sont réutilisées directement, sans dépendance à son service HTTP ni à son état.

## Comportement livré

Conforme à [MAIN-01 à MAIN-16](etape-ui-8.1-maintenance.md) dans le périmètre liste :

- Route `/maintenance` lazy, liste seule. Les routes détail, new et edit restent
  absentes ; aucun lien d’intervention trompeur ni navigation Equipment anticipée.
- Entreprise, site puis équipement choisis explicitement. Même une option unique
  n’est pas sélectionnée. Les URL doivent fournir les ancêtres explicites si
  elles désignent un site ou un équipement ; aucun parent supposé n’est fabriqué.
- Les GET détail des références vérifient les ids retournés, Equipment.site_id
  et Site.company_id avant tout GET Maintenance. Un parent absent, refusé ou
  contradictoire bloque la liste. Les catalogues ne valent pas preuve du rattachement.
- Catalogues par pages de 50, boutons de suite et reprise manuelle après erreur
  réseau/serveur. La référence résolue hors première page est incluse dans les
  options. Un catalogue contenant un enfant d’un autre parent est rejeté.
- Les aides de sélection disparaissent seulement après validation réelle ; elles
  reviennent quand le contexte est effacé ou invalide. Les descendants sont vidés
  sur changement de parent. switchMap annule références, résultats et catalogues
  obsolètes ; destruction du composant annule les abonnements.
- GET singulier `/api/v1/maintenance` paginé exclusivement. equipment_id est
  obligatoire et vérifié. company_id et site_id restent dans le contexte URL,
  jamais dans la requête Maintenance. Aucun GET global ou non paginé par équipement.
- Filtres combinés : type (3 valeurs), statut (4, alias HTTP status), priorité
  (4), recherche explicite et période de création. Les libellés sont français.
  Prédictive désigne un type déclaré, sans calcul IA implicite.
- Recherche sur action Rechercher uniquement, jamais à la frappe. Chaîne brute
  conservée, 100 points de code Unicode maximum ; vide supprimé explicitement.
  Une recherche URL vide ou trop longue est bloquée. Les espaces et jokers ne sont
  pas transformés côté UI ; le trim et ILIKE du backend restent son contrat.
- Période sur **created_at uniquement**, début inclus et fin exclue. Calendrier,
  heure avec secondes, fraction facultative de 0 à 6 chiffres. Les contrôles
  affichent UTC ; une borne restaurée non modifiée conserve sa chaîne source,
  son offset et sa précision. Une nouvelle borne est sérialisée en UTC sans Date.
  Bornes unilatérales acceptées ; naïves, malformées, égales ou inversées bloquées.
  Aucune suppression silencieuse d’une borne invalide pour élargir la lecture.
- Critères appliqués et pagination conservés dans l’URL. Changement de filtre :
  page 1. Changement de parent/équipement : recherche et période effacées ; enums
  et taille valides conservés. Brouillon de recherche distinct du filtre appliqué.
- Page initiale 1, taille 20 ; options 20/50/100 et conservation d’une taille URL
  valide 1..100. Pagination serveur, sans chargement intégral de l’historique.
  Pagination URL invalide normalisée avec message avant lecture. Page hors plage
  conservée et retour proposé manuellement, jamais corrigée en silence.
- Tableau : #ID, titre, type, statut, priorité, date planifiée et date de création.
  Tri backend created_at DESC, id DESC, sans tri local ou réglable. Null planifié
  affiché « Non renseignée », titre vide distingué. Dates ISO sources conservées,
  microsecondes intactes. Date administrative naïve affichée avec « fuseau non
  fourni » ; aucun Z ajouté, aucune hypothèse UTC. Les dates aware gardent leur offset.
- États sélection attendue, catalogues vides/chargement/erreur, chargement de liste,
  aucune intervention, aucun résultat filtré, page hors plage, référence invalide,
  HTTP et réponse invalide. Aucun remplacement d’erreur par une page vide.
  Actualisation manuelle et reprise réseau/serveur sans retry automatique.
- Labels liés, aides conditionnelles, aria-busy, erreurs annoncées, région tableau
  focalisable, focus visible et boutons harmonisés. Tableau défilant localement.

Aucun formulaire métier, coût/devise/durée calculée, indicateur, écriture ou transition.
La chaîne de références ne constitue pas une autorisation multi-tenant.

## Validation UI 8.3 (historique)

### Tests et build réellement exécutés

- Tests ciblés : **325 réussis**, 5 fichiers (Maintenance API, façade, page,
  routes et routage global). Commande : `npx ng test --watch=false
  --include='src/app/features/maintenance/**/*.spec.ts'
  --include='src/app/app.routes.spec.ts' --runner-config=tmp/ui-8.3/vitest.config.mjs`.
- Suite finale : **1 786 tests réussis, 70 fichiers**. Commande :
  `npx ng test --watch=false --runner-config=tmp/ui-8.3/vitest.config.mjs`.
- Un premier lancement ciblé a été bloqué avant les tests par EPERM dans les
  fichiers temporaires Windows ; relance hors sandbox. Une première suite
  complète a donné 1 785 succès et un échec : le test Sidebar attendait encore
  le placeholder Maintenance. Après adaptation de ce seul test historique,
  une relance complète a été nécessaire et réussie. Ce n’est donc pas une
  unique tentative complète ; aucune autre répétition après succès.
- Build production exécuté **une fois**, réussi :
  `npx ng build --configuration production`.
- Référence UI 8.2 : 1 717 tests et build réussis. Ces résultats restent historiques,
  distincts des 1 786 tests exécutés ici (69 tests supplémentaires).

La façade teste choix explicites, contexte incomplet/contradictoire, ids reçus,
parents indisponibles, annulation à chaque niveau et à la liste, HTTP/réseau,
réponse invalide, whitelist, période précise et page hors plage. La page teste
catalogues et suite/reprise, références hors première page, filtres/URL, recherche
brute Unicode, période et offset, invalidités, changement de parent/équipement,
vides, chargement, erreurs, actualisation et accessibilité structurelle.
Les tests Shell/Sidebar vérifient titre, route lazy et navigation active ; détail,
création et édition demeurent sur la 404 globale. Les tests transport UI 8.2
sont inclus et vérifient notamment les enums, dates et l’absence de mutations.

### Poids des bundles

| Mesure | UI 8.2 | UI 8.3 | Évolution |
| --- | --- | --- | --- |
| Initial, valeur affichée Angular | 605,65 kB | **605,75 kB** | +0,10 kB |
| Chunk liste Maintenance | Absent | **42 117 octets, 42,12 kB** | Nouveau lazy chunk |
| Ensemble JS/CSS émis | 1 038 094 octets | 1 080 769 octets | +42 675 octets |

Avertissement initial conservé : budget 500 kB dépassé de 105,75 kB. Aucun budget
relevé. Estimation de transfert initial 153,84 kB ; chunk liste 10,02 kB.
Le découpage partagé des utilitaires peut redistribuer les autres chunks ;
la taille du chunk liste seule n’est pas la taille totale de son parcours réseau.

### Recette navigateur et responsive

Navigateur intégré sur `http://127.0.0.1:8098`, build production et serveur de
fixtures GET uniquement, sans proxy, FastAPI ni base. Serveur temporaire arrêté
après contrôle. Le contrôle ne constitue pas une intégration DEV.

Parcours exécuté par actions UI : entreprise 7, site 9, équipement 12 choisis
séparément ; aucun choix enfant automatique ; aides retirées progressivement ;
43 dossiers fictifs, première page de 20 lignes et sept colonnes. Recherche
Inspection saisie sans lecture, puis soumise au clavier : un résultat et URL
actualisée ; effacement explicite : retour aux 20 lignes. Trace locale :
**25 requêtes API, toutes GET, dont 4 listes Maintenance**, toutes avec
`equipment_id=12`. Ce sont des preuves sur fixtures, pas des preuves backend.

Dimensions CSS mesurées après stabilisation du resize du Shell, zoom existant
compensé dans la taille de viewport demandée. À 1024 px, navigation latérale
ouverte ; en dessous, Shell mobile replié. Mesure `scrollWidth = clientWidth`
du document et aucun contrôle hors largeur à toutes les cibles ci-dessous.

| Cible | Largeur CSS obtenue | Largeur visible du tableau | Largeur interne du tableau | Aide défilement |
| --- | --- | --- | --- | --- |
| 1440 | 1440 | 1066 | 1066 | Masquée |
| 1024 | 1024 | 650 | 960 | Visible |
| 1023 | 1023 | 905 | 960 | Visible |
| 768 | 768 | 666 | 960 | Visible |
| 390 | **389 et 391** | 319 et 321 | 960 | Visible |
| 320 | 320 | 250 | 960 | Visible |

Réserve : 390 CSS exact non obtenu à cause de l’arrondi du zoom ; les deux
largeurs voisines sont contrôlées. Le tableau défile localement ; l’aide est
conditionnée à sa largeur disponible, masquée sur desktop quand il tient.

À 320 px, Tab depuis la recherche atteint Rechercher, focus-visible avec contour
solid ; Entrée soumet une seule recherche ; le focus reste sur le bouton. La
région tableau reçoit le focus et Flèche droite fait progresser scrollLeft,
sans élargir le document. Ces contrôles complètent les tests de labels et aria.
Ils ne remplacent pas un audit lecteur d’écran ou de contraste complet.

**Captures indisponibles** : les deux API de capture du navigateur, en mode
viewport et page complète, renvoient « Unable to capture screenshot » malgré
le DOM accessible. Aucune image n’est créée ou présentée comme preuve. Les
contrôles responsive reposent sur le DOM, les styles calculés et la géométrie,
pas sur une revue visuelle par captures ; cette réserve doit rester visible.
Mesures et traces temporaires sont dans `frontend/tmp/ui-8.3`, ignoré par Git.


## UI 8.3.1 - Finitions UX

Le même ensemble de 13 fichiers UI 8.3 est conservé. Cette finition ne modifie
que les quatre fichiers de la page Maintenance (TypeScript, HTML, SCSS, tests)
et le présent rapport. Aucun changement de façade, contrat, route ou service API.
Les résultats UI 8.3 ci-dessus restent historiques.

### Corrections

- Deux groupes compacts Début UTC / Fin UTC, chacun avec date, heure et secondes,
  fraction facultative. Leurs dispositions dépendent de la largeur réelle du
  panneau via container queries, puis les deux boutons restent côte à côte quand
  l’espace le permet. Sur mobile les contrôles et actions se replient.
- La période saisie est un brouillon distinct des bornes appliquées, dont les
  chaînes ISO exactes sont affichées. Aucune lecture à la frappe. Le brouillon
  reste intact pendant pagination et changements d’enum ; la lecture continue
  d’utiliser les anciennes bornes appliquées. Un message annonce le brouillon.
- Validation près du champ : date sans heure, heure sans date, fraction invalide,
  date impossible, heure hors bornes, borne source naïve/invalide et ordre strict.
  aria-invalid et aria-describedby désignent l’erreur locale avec role=alert ;
  Appliquer place le focus sur le premier champ erroné. Correction d’un champ
  revalide les erreurs déjà affichées sans GET. Aucun défaut d’heure ajouté.
- Les contrôles UTC conservent le transport précis de UI 8.3 : microsecondes et
  offset source intacts si la borne n’est pas modifiée, aucun Date/toISOString.
  Une période invalide ne remplace pas les données par une lecture élargie.
- **Effacer la période** modifie seulement start_time, end_time et page=1 dans
  l’URL. Type, statut, priorité, recherche, contexte et taille de page sont
  conservés, y compris les paramètres invalides à réparer explicitement.
- Recherche et bouton alignés en largeur suffisante, empilés sur mobile. Brouillon
  de recherche annoncé séparément de la recherche appliquée ; conservé lors des
  autres actions. Soumission explicite, brut Unicode 100 caractères maximum,
  page 1 et absence de trim frontend inchangés.
- Titre légèrement renforcé, colonne plus large ; statut et priorité en badges
  discrets avec texte lisible. Tokens et mixin actions existants réutilisés,
  aucune information communiquée uniquement par couleur. Sept colonnes conservées,
  dates naïves toujours signalées sans ajout de Z, aucun lien détail anticipé.

### Validation UI 8.3.1

- **353 tests ciblés réussis, 6 fichiers**. Commande : `npx ng test --watch=false
  --include='src/app/features/maintenance/**/*.spec.ts'
  --include='src/app/app.routes.spec.ts'
  --include='src/app/layout/sidebar/sidebar.component.spec.ts'
  --runner-config=tmp/ui-8.3.1/vitest.config.mjs`.
- **1 803 tests Angular réussis, 70 fichiers**, sur les sources finales.
  Commande : `npx ng test --watch=false --runner-config=tmp/ui-8.3.1/vitest.config.mjs`.
  Soit 17 tests supplémentaires par rapport aux 1 786 de UI 8.3.
- Transparence d’exécution : première passe ciblée 352 succès et suite
  intermédiaire 1 802 succès ; un dernier cas ajouté a renforcé Effacer pour
  préserver aussi les filtres URL invalides. Après ce changement, 353 ciblés
  puis une suite complète finale de 1 803 succès. La suite n’a pas été répétée
  après ce succès final. Les nombres UI 8.3 restent historiques.
- **Build production exécuté une fois et réussi** :
  `npx ng build --configuration production`. Aucun budget changé.

| Mesure | UI 8.3 | UI 8.3.1 |
| --- | --- | --- |
| Initial | 605 752 octets, 605,75 kB | **605 752 octets, 605,75 kB**, inchangé |
| Lazy liste Maintenance | 42 117 octets, 42,12 kB | **48 024 octets, 48,02 kB** |
| Transfert estimé du chunk liste | 10,02 kB | 11,39 kB |

Le build conserve le dépassement initial de 105,75 kB au seuil de 500 kB.
**Nouvel avertissement de style** : SCSS compilé de la page à **4,58 kB**, soit
**576 octets au-dessus du seuil de 4 kB** ; maximum d’erreur de 8 kB inchangé.
Ce dépassement est documenté, pas masqué par une hausse des budgets.

### Recette locale UI 8.3.1 et limites

Build production servi sur 127.0.0.1:8098 avec fixtures GET exclusivement, sans
proxy FastAPI ni SQL. Serveur arrêté en fin de contrôle. Les éléments visuels
ci-dessous sont vérifiés par DOM, styles calculés, géométrie et actions clavier.

- En desktop 1440, deux groupes UTC côte à côte ; boutons Appliquer/Effacer sur
  une même ligne, hauteur 44 px. Les bas du champ recherche et du bouton sont
  alignés exactement. Badges textuels de poids 600, fond #f4f6fa, texte sombre
  #17253b / #14243d ; titre renforcé, aucune route détail.
- Date saisie sans heure puis Appliquer : message sous l’heure, aria-invalid et
  aria-describedby corrects, focus déplacé sur l’heure. Les 20 lignes et l’URL
  restent inchangées. Trace de fixtures avant/après : **7 GET et 1 liste** dans
  les deux relevés, donc aucun GET additionnel pour ce brouillon invalide.
- Période appliquée avec début `2026-10-23T12:00:00.123456Z`, fin
  `2026-10-23T12:00:01.000001Z`, fractions et URL intactes. Modification du
  brouillon début en .654321 puis statut Planifiée : la requête conserve
  .123456 ; le brouillon et son message restent visibles.
- Recherche Inspection en brouillon puis Effacer la période : le statut planned
  reste appliqué et la recherche reste en brouillon. Tab atteint Rechercher,
  focus-visible avec contour solid ; Entrée applique la recherche et donne
  une ligne fictive, en conservant planned. Aucun déclenchement à la frappe.
- À 320, fraction de sept chiffres : erreur locale accessible, focus sur le
  premier champ manquant, résultat précédent conservé et aucun débordement.
- Trace finale : **23 requêtes API, toutes GET, dont 5 listes Maintenance**,
  toutes limitées à equipment_id=12. Ces preuves sont simulées sur serveur
  local ; elles ne valident pas une intégration DEV réelle.

| Cible CSS | Obtenue | Tableau visible / interne | Actions période | Recherche |
| --- | --- | --- | --- | --- |
| 1440 | 1440 | 1066 / 1066 | Même ligne, 44 px | Alignée |
| 1024 | 1024 | 650 / 960 | Même ligne, 44 px | Alignée |
| 1023 | 1023 | 905 / 960 | Même ligne, 44 px | Alignée |
| 768 | 768 | 666 / 960 | Même ligne, 44 px | Alignée |
| 390 | **389 et 391** | 319 et 321 / 960 | Empilées, 44 px | Empilée |
| 320 | 320 | 250 / 960 | Empilées, 44 px | Empilée |

Document : scrollWidth égale clientWidth partout ; aucun contrôle déborde de
la largeur disponible. Défilement local du tableau aux petites largeurs,
aide masquée à 1440 où le tableau tient. 390 exact reste non obtenu à cause du
zoom et de l’arrondi du viewport. Mesures après stabilisation du Shell.

**Réserve captures maintenue** : tentative viewport desktop et tentative page
complète mobile échouent avec « Unable to capture screenshot ». Aucune capture
desktop/tablette/mobile n’est disponible ni revendiquée. La revue par images
reste à compléter ; aucun audit complet de lecteur d’écran n’est revendiqué.
Traces et mesures dans `frontend/tmp/ui-8.3.1`, ignoré par Git.


## UI 8.3.2 - Optimisation SCSS ciblée

Seuls le SCSS de Maintenance List et ce rapport évoluent dans cette finition.
Les 13 fichiers cumulés UI 8.3/8.3.1 sont conservés. Aucun changement TypeScript,
HTML, tests applicatifs, style partagé ou global. Les résultats précédents restent
historiques, distincts de la validation UI 8.3.2.

### Budget et simplification

Budget production `anyComponentStyle` inchangé dans angular.json : avertissement
à **4 000 octets (4 kB)**, erreur à **8 000 octets (8 kB)**. Il porte sur le CSS
compilé/minifié avant encapsulation, pas sur la longueur du fichier SCSS source,
ni sur la chaîne CSS encapsulée incluse dans le chunk JavaScript.

- Le mixin actions.navigation-action fournit une seule fois la base des boutons,
  leur géométrie, typographie, hover secondaire et focus. La variante primaire
  ne redéclare que fond, bordure, texte et couleurs de hover, identiques au mixin
  existant. Le mixin partagé reste inchangé.
- Les propriétés de contrôles déjà fournies aux boutons par cette base ne sont
  plus émises une seconde fois pour button dans le groupe input/select.
- Les deux blocs badge sont fusionnés avec leur padding final inchangé ; la
  déclaration de padding immédiatement remplacée est supprimée.
- Le sélecteur a:focus-visible inutilisé est retiré : cette liste ne contient
  aucun lien et n’anticipe aucune fiche détail. Le focus de tous les contrôles
  existants et de la région tableau reste défini.

Aucun déplacement vers un style global ou autre fichier pour contourner le
budget. Aucun changement de sélecteur fonctionnel ou de règle responsive.
La minification locale Sass/esbuild, avec les dépendances déjà installées,
projette 4 575 -> 3 960 octets hors saut de ligne. Ce contrôle intermédiaire
ne constitue pas un build production supplémentaire ; le build final fait foi.

### Validation UI 8.3.2

- **353 tests ciblés réussis, 6 fichiers** (Maintenance et routage/Shell), une
  exécution après stabilisation : `npx ng test --watch=false
  --include='src/app/features/maintenance/**/*.spec.ts'
  --include='src/app/app.routes.spec.ts'
  --include='src/app/layout/sidebar/sidebar.component.spec.ts'
  --runner-config=tmp/ui-8.3.2/vitest.config.mjs`.
- **1 803 tests Angular réussis, 70 fichiers**, suite complète exécutée **une
  seule fois** : `npx ng test --watch=false --runner-config=tmp/ui-8.3.2/vitest.config.mjs`.
- **Build production réussi, exécuté une seule fois** :
  `npx ng build --configuration production`.
- **Avertissement anyComponentStyle supprimé**. Seul subsiste le dépassement
  initial historique de 105,75 kB au seuil de 500 kB. Aucun budget changé.

| Mesure | UI 8.3.1 | UI 8.3.2 | Variation |
| --- | --- | --- | --- |
| CSS compilé/minifié local Sass/esbuild, saut de ligne compris | 4 576 octets | **3 961 octets (3,96 kB)** | **-615 octets** |
| Initial production | 605 752 octets, 605,75 kB | **605 752 octets, 605,75 kB** | Inchangé |
| Chunk Maintenance List | 48 024 octets, 48,02 kB | **47 213 octets, 47,21 kB** | **-811 octets** |
| Transfert estimé du chunk | 11,39 kB | 11,30 kB | -0,09 kB |

La mesure CSS locale est produite avec les dépendances Sass/esbuild installées,
au même chemin de résolution des imports, sans nouveau package. Le build
production confirme le respect du budget de 4 000 octets par l’absence de
l’avertissement ciblé ; marge de la mesure minifiée : **39 octets**. La chaîne
CSS après encapsulation Angular est plus longue (5 823 octets contre 6 634) et
n’est pas le budget anyComponentStyle. Son retrait explique aussi le gain du
chunk JavaScript, différent du gain avant encapsulation.

### Comparaison du rendu et responsive UI 8.3.2

Serveurs de fixtures locaux GET uniquement, aucun proxy API ni SQL. Pour comparer
sans ambiguïté de chargement/animation du Shell, une référence temporaire sert
le même JavaScript avec uniquement la chaîne CSS précédente substituée dans
le chunk de la page (port 8097) ; le build final est servi au port 8098.
Ces fichiers restent dans tmp, aucun code applicatif n’est modifié pour la recette.

Comparaison DOM après résolution du contexte, chargement des résultats et état
stabilisé du Shell : **39 éléments par largeur, 27 propriétés CSS calculées et
4 mesures géométriques**. Inputs, selects, boutons primaires/secondaires,
pagination avec état désactivé, grilles UTC, recherche, titre et badges :
**aucune différence dans les sept relevés** ci-dessous. Les lectures prises
durant un état transitoire ont été écartées puis contrôlées à état identique,
sans changement de source, nouveau test Angular ou rebuild.

| Cible CSS | Obtenue | Tableau visible / interne | Débordement global | Écart de comparaison |
| --- | --- | --- | --- | --- |
| 1440 | 1440 | 1066 / 1066 | Aucun | Aucun |
| 1024 | 1024 | 650 / 960 | Aucun | Aucun |
| 1023 | 1023 | 905 / 960 | Aucun | Aucun |
| 768 | 768 | 666 / 960 | Aucun | Aucun |
| 390 | **389 et 391** | 319 et 321 / 960 | Aucun | Aucun |
| 320 | 320 | 250 / 960 | Aucun | Aucun |

scrollWidth égale clientWidth et aucun contrôle hors largeur partout. Groupes
UTC compacts, recherche alignée, boutons de 44 px et repli mobile conservés ;
aide de défilement masquée à 1440 et visible lorsque le tableau déborde localement.
Les badges gardent leur texte, typographie, couleurs, padding et dimensions.

À 320 px, date sans heure puis Appliquer : même état d’erreur et de brouillon,
mêmes styles et géométrie qu’avant, focus sur l’heure, role=alert conservé.
Tab depuis la fraction de fin atteint Appliquer : focus-visible, contour bleu,
espacement du contour, fond bleu, texte blanc et hauteur 44 px **identiques**
avant/après. Aucun changement de borne, offset, recherche ou règle métier.

Réserves conservées : 390 exact non obtenu (389/391 contrôlés), captures non
disponibles lors de UI 8.3/8.3.1, revue par images et audit lecteur d’écran complet
non revendiqués. Cette validation repose sur les styles calculés et la géométrie,
pas sur de nouvelles captures. Les réserves B-MAIN restent ouvertes.
Traces, snapshots et mesures dans `frontend/tmp/ui-8.3.2`, ignoré par Git.
Serveurs temporaires arrêtés après vérification.


## Réserves et état Git

B-MAIN-01 à B-MAIN-09 restent ouverts, notamment état fusionné/chronologie, null
SQL, contenu et longueurs, non-finis et minutes, workflow, transactions/concurrence,
dates administratives, sécurité tenant, pagination volumineuse et devise/audit.
Voir le rapport UI 8.1, qui reste inchangé. Les bornes filtrent created_at malgré
la limite des défauts administratifs naïfs côté backend. Aucun correctif serveur.

Les résultats Angular sont simulés avec HttpTestingController ; la recette visuelle
utilise des fixtures locales fictives. Aucune recette DEV Angular/FastAPI/PostgreSQL,
aucune opération SQL ou Docker. L’identité et l’intégrité DEV restent à vérifier
lors de UI 8.6. Les références historiques de tests ne remplacent pas ces preuves.

Aucun package, backend, migration, contrat API ou budget modifié. Treize fichiers concernés (3 existants et 10 nouveaux). Liens locaux vérifiés,
absence de secret et d’artefact dans le périmètre Git contrôlée ; `git diff --check`
réussi. HEAD `740a947` inchangé. Index vide,
aucun commit, push, merge ou rebase. UI 8.4 non commencée. Validation utilisateur
attendue avant commit.
