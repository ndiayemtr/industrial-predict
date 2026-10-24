# UI 8.8 - Finitions UX Sensors, Measurements et Maintenance

24 octobre 2026. Départ vérifié : main = origin/main = HEAD = `2365259`, dépôt
propre. Branche créée : `feature/frontend-ux-polish`. HEAD reste inchangé.
Aucun accès PostgreSQL, FastAPI DEV, Docker, seed ou migration ; aucun package,
contrat API, modèle backend ou décision métier modifié. UI 9.1 non commencée.

## Validation finale et revue avant commit

L'utilisateur valide visuellement l'ensemble UI 8.8, y compris les infobulles,
l'alignement des champs, les erreurs groupées et l'espacement final de 16 px.
La revue Git couvre exactement les 17 fichiers frontend et ce rapport. Aucun
service API, modèle, façade, route ou code backend modifié ; UTC, offsets,
microsecondes et navigation conservés. Lors de cette revue, le role=alert de
l'erreur de recherche Maintenance a été restauré à l'identique de HEAD : sa
suppression involontaire était hors du périmètre des erreurs temporelles.
Cette restauration de l'attribut d'accessibilité d'origine ne change ni la
validation de recherche ni les requêtes ; aucune nouvelle exécution Angular ou
build n'est revendiquée pour ce rétablissement.

Références conservées sans relance : 381 tests ciblés/9 fichiers et 1 912 tests
Angular/72 fichiers, build production réussi, initial 605 998 octets (606,00 kB).
Le build précède la dernière finition CSS ; celle-ci est couverte par les contrôles
Sass/esbuild/jsdom et la validation visuelle utilisateur. CSS finaux locaux :
Measurements 3 559 octets, Maintenance 3 985 octets. Budget initial historique,
captures complémentaires indisponibles, réserve 389/391 pour 390 px et dettes
backend/sécurité demeurent documentés. Aucun accès PostgreSQL ni recette DEV relancé.

Le point de départ vérifié est feature/frontend-ux-polish à 2365259, index vide ;
les états Git ci-dessous décrivent les phases avant commit. Le commit unique de
livraison UI 8.8 est explicitement autorisé par la demande utilisateur courante.
Aucun push, merge ou rebase autorisé ; UI 9.1 non commencée.

## Dernière finition - Espacement sans erreur

Les corrections précédentes sont **visuellement validées par l'utilisateur**.
La validation visuelle utilisateur finale est désormais confirmée, y compris
l’espacement de 16 px sur les deux listes. Cette confirmation est distincte des
tests automatisés et ne constitue ni une nouvelle capture ni une recette DEV.

Cause exacte : la zone period-feedback vide restait une ligne de grille avec
min-height: 2.75rem (44 px), plus le gap de 16 px avant et après, soit environ
76 px entre les champs et les actions. Les messages avaient été déplacés dans
cette zone lors du complément précédent, mais son espace restait réservé à vide.

Même correction dans les deux feuilles locales :
`.period-feedback:empty { display: none; }`.
Sans erreur, la zone sort de la grille et **un seul gap existant de 16 px** reste
entre les champs et les boutons. Avec une erreur, la règle ne s'applique plus :
messages groupés, hauteur minimale, focus, bordures et alignements validés sont
conservés. Après correction ou effacement, l'espace vide disparaît naturellement.
Les commentaires d'ancrage Angular ne font pas obstacle au sélecteur :empty.
Aucun template ni comportement DOM applicatif modifié, aucune touche de logique,
date, validation ou service API ; responsive et boutons des autres pages inchangés.

Fichiers de cette finition seulement : les SCSS Measurements List et Maintenance
List, et le présent rapport. Pour conserver le budget SCSS Maintenance, deux
déclarations strictement redondantes des champs sont retirées : border-box est
déjà fourni par le reset global existant, et max-width:100% n'ajoutait aucune
limitation à width:100% avec ce box-sizing. Aucun changement de géométrie attendu.

Vérifications ciblées exécutées : compilation Sass/minification esbuild des styles,
puis contrôle du sélecteur avec jsdom installé, sur zone vide avec commentaire
Angular, zone avec message et zone de nouveau vide. Les deux pages passent.
CSS local minifié avec saut de ligne : **Measurements 3 559 octets**, **Maintenance
3 985 octets**, sous le warning de 4 000 octets ; aucun budget modifié.
Les contrôles jsdom vérifient le sélecteur, pas la géométrie d'un navigateur.

Aucun test Angular ni build production relancé : les **1 912 tests**, le dernier
build réussi et son initial **606,00 kB** sont les références de la validation
précédente, applicables à la logique et aux templates inchangés. Les tailles des
chunks de ce build restent historiques, sans nouvelle mesure production de cette
finition CSS. Aucun test ajouté ou modifié, aucune nouvelle capture revendiquée.
`git diff --check` réussi. Branche feature/frontend-ux-polish, HEAD 2365259
inchangé, diff antérieur conservé et index vide. Aucun commit, push, merge ou rebase.

## Corrections complémentaires après revue utilisateur

Les sections « Première passe » ci-dessous conservent le bilan antérieur.
La revue utilisateur a identifié deux corrections nécessaires ; les premières
captures ne constituent donc pas une validation du rendu final.

### Erreurs temporelles : cause et correction finale

Les messages étaient insérés dans les cellules de la grille, alignée par le bas.
Leur hauteur décalait les champs voisins ; le résumé rouge répétait l'information.
Les deux pages déplacent désormais leurs messages dans **une zone commune sous
les six champs, avant les boutons**, avec **44 px minimum réservés** et des marges
de paragraphe nulles. Cette zone peut grandir pour plusieurs erreurs ou des textes
longs, sans décaler les inputs individuellement ni tronquer les explications.

Les erreurs précises sont préfixées Début ou Fin et restent associées aux champs
par leurs ids/aria-describedby. Un seul role=alert avec aria-atomic ; aucun résumé
générique rendu en plus. Seuls les champs invalides reçoivent aria-invalid et une
bordure rouge. Aucun message dans les cellules de saisie.

La validation partagée et les règles de la première passe sont conservées :
composition initiale silencieuse, application explicite, correction et effacement,
aucune heure par défaut, maintien de la période/résultats/pagination appliqués en
cas de brouillon invalide, aucune requête par frappe. UTC, six décimales, offsets
source et intervalle [début, fin) restent inchangés. Une URL invalide reste bloquée
et signalée, sans lecture élargie. Aucun service ni façade API modifié.
Pour conserver le budget local, le hover primaire redondant de Maintenance List
est retiré : _buttons.scss fournit déjà ce traitement dans le Shell, sans changement
global ni changement des boutons Modifier des détails.

### Audit Equipment, Sensor et Maintenance Detail

Avant le complément, le DOM montre un title natif sur app-page-header :
« Détail équipement » hérité par les quatre actions Equipment et « Détail
intervention » hérité par le retour Maintenance. Aucun nbTooltip, nb-tooltip ou
role=tooltip dans ces fiches. Sensor était déjà corrigé lors de la première passe.

Equipment et Maintenance utilisent désormais [title] comme Sensor : l'entrée du
composant et le h1 visible sont conservés, sans attribut HTML title redondant.
Contrôle DOM final sur les trois fiches : aucun ancêtre title ni composant de
tooltip pour les actions. Libellés et href Equipment/Maintenance strictement
identiques avant/après ; tests des contextes URL conservés. Actions mesurées à
44 px : secondaires blanches, Modifier bleu primaire sur Equipment/Sensor,
focus clavier visible. Aucun Modifier ajouté à Maintenance. Pas de refonte des styles.

### Validation finale exécutée après stabilisation

Les templates/styles et deux fiches supplémentaires ont changé : les résultats
de la première passe restent historiques. Une seule suite complète et un seul
build finaux ont donc été exécutés pour le complément, séquentiellement.

| Contrôle | Résultat final |
| --- | --- |
| Tests ciblés | **381 réussis dans 9 fichiers** |
| Suite Angular complète | **1 912 réussis dans 72 fichiers**, contre 1 908 à la première passe et 1 899 historiquement |
| Build production | **Réussi** |
| Initial | **605 998 octets, 606,00 kB**, inchangé |
| CSS Sensor Detail | 2 264 octets, inchangé depuis la première passe |
| CSS Measurements List | 3 523 octets, contre 3 399 à la première passe |
| CSS Maintenance List | 3 986 octets, contre 3 952 à la première passe |
| maintenance-list-component | 41843 octets |
| measurements-list-component | 39427 octets |
| sensor-detail-component | 16453 octets |
| maintenance-detail-component | 16417 octets |
| equipment-detail-component | 14808 octets |

Aucun nouveau warning SCSS ; seul le warning initial historique à +106,00 kB.
Budgets inchangés (initial 500 kB/1 MB ; composant 4/8 kB). CSS local compilé et
minifié avec saut de ligne, distinct du CSS encapsulé dans les chunks.
Quatre tests ajoutés : zone commune sur chacune des listes et absence de titre
hérité sur Equipment/Maintenance. Les scénarios UTC, saisie incomplète, application
valide, correction/effacement, focus et absence de GET parasite restent couverts.
Les ciblés précèdent le dernier regroupement des marges CSS ; suite complète et
build sont exécutés sur les sources finales, sans autre changement exécutable ensuite.

Journaux ignorés : [ciblés](../frontend/tmp/ui-8.8/complement/targeted-tests.log),
[suite](../frontend/tmp/ui-8.8/complement/full-tests.log),
[build](../frontend/tmp/ui-8.8/complement/build.log).

### Vérifications navigateur finales et limites

Aperçu sur fixtures GET uniquement à 127.0.0.1:8108 ; aucun proxy DEV, FastAPI ou
PostgreSQL. Les [observations DOM finales](../frontend/tmp/ui-8.8/complement/dom-checks.json)
distinguent état avant et après. À 1440 px, les six inputs de chaque liste ont
une hauteur de 44 px et sont tous à 145 px du début du formulaire, avant comme
après affichage de l'erreur (tolérance numérique <0,01 px). L'heure manquante est
le seul champ invalide et reçoit le focus. La zone de message reste à 44 px pour
ce cas. Après correction, elle redevient vide sans application ni changement de
l'URL. Effacement Maintenance également vérifié.

Mesures après stabilisation du Shell : 1440/1024/1023/768/320 px exacts et 389/391
pour encadrer 390. Six champs présents, scrollWidth égal à clientWidth sur les deux
pages. Un débordement transitoire a été observé lors du redimensionnement rapide
vers mobile ; la relecture stabilisée est conforme, sans correctif spéculatif.

**Nouvelles captures indisponibles** : les API documentées de capture ont renvoyé
« Unable to capture screenshot », y compris après affichage du navigateur et via
l'autre méthode documentée. Les captures de la première passe sont historiques
et montrent l'ancienne disposition des erreurs. Elles ne prouvent pas le rendu
complémentaire. Géométrie, attributs et interactions DOM sont vérifiés ;
**validation visuelle utilisateur confirmée depuis ce relevé pour le complément**. Pas d'audit lecteur d'écran
exhaustif ; réserve sur la cible exacte 390 px conservée.

### Fichiers cumulés finaux

**17 fichiers frontend modifiés, plus le rapport existant actualisé : 18 fichiers.**
Aucune nouvelle branche et aucune perte des changements initiaux. Liste exacte :

- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.html`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.spec.ts`
- `frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.html`
- `frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.spec.ts`
- `frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.html`
- `frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.scss`
- `frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.spec.ts`
- `frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.ts`
- `frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.html`
- `frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.scss`
- `frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts`
- `frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.ts`
- `frontend/src/app/features/measurements/utils/measurement-period-draft.spec.ts`
- `frontend/src/app/features/measurements/utils/measurement-period-draft.ts`
- `frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.html`
- `frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.scss`
- `frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.spec.ts`
- `docs/ui-8.8-ux-polish.md`

Aucun second rapport créé. Les sections suivantes conservent la première passe
comme historique et sont remplacées par le présent bilan pour l'état final.

## Première passe - Causes et comportement avant/après

### Actions Détail capteur

Le template portait un attribut statique `title="Détail capteur"` sur le host
app-page-header. Cet attribut natif reste dans le DOM et peut fournir une
infobulle héritée à ses liens projetés. Aucune directive nbTooltip ni tooltip
propre aux liens n'est présente. Le contrôle navigateur avant correction retrouve
cet attribut sur leur ancêtre ; après correction il est absent.
La liaison Angular [title] fournit toujours le titre visible au composant sans
produire cet attribut HTML. Les libellés accessibles et le h1 restent présents.

Les styles navigation-action étaient déjà employés : les mesures initiales
confirment 44 px dans les vues observées, pas une absence de styles partagés.
Les deux actions secondaires sont désormais regroupées dans la même règle SCSS,
sans duplication de mixin, avec le même traitement des libellés non coupés que
Modifier à partir de 768 px. Le flex-wrap de PageHeader reste utilisé : plusieurs
lignes restent possibles sur tablette/mobile, sans forcer trois boutons dans une
largeur insuffisante. Tous les boutons mesurés font 44 px de haut ; les deux
secondaires gardent fond blanc/bordure et Modifier son bleu primaire.
Aucun changement de lien, query params, condition de visibilité ou gestion des
parents ; les trois destinations sont vérifiées par les tests.

### Composition des périodes

Avant correction, les deux formulaires liaient submit à applyPeriod et possédaient
un bouton submit. Entrée depuis un champ pouvait donc appliquer implicitement un
brouillon incomplet. Reproduction sur le build antérieur, sur fixtures : saisir
seulement une date Maintenance puis Entrée affiche l'erreur d'heure manquante,
sans activation explicite du bouton Appliquer. La saisie seule ne déclenchait pas
une validation en continu avant cette soumission ; la cause n'est pas un GET à
chaque frappe.
Measurements conservait ensuite son erreur générale jusqu'à une nouvelle action,
marquait les six champs invalides et ciblait toujours la date de début.
Maintenance affichait plusieurs role=alert (champs et résumé), avec une validation
plus détaillée mais distincte de celle de Measurements.

Après correction, les formulaires neutralisent submit. Appliquer est un bouton
explicite type=button : clic, Entrée ou Espace sur ce bouton lance la validation ;
Entrée dans les champs ne soumet plus la période. Tab permet de rejoindre le
bouton, sans blocage des touches des sélecteurs natifs.

- Composition initiale incomplète : aucune erreur rouge ni aria-invalid ajouté.
- Tentative explicite invalide : une seule alerte principale et explications
  proches des seuls champs concernés, associés par aria-describedby/aria-invalid.
  Focus du premier champ invalide, aucune heure complétée par défaut.
- Correction pertinente : validation locale uniquement tant qu'une erreur est
  affichée ; messages supprimés une fois le brouillon valide ou effacé. Modifier
  un champ sans corriger le problème ne masque pas artificiellement l'erreur.
- Une correction valide ne lance pas automatiquement la requête. Une nouvelle
  activation d'Appliquer applique le brouillon, remet la page à 1 et garde les
  autres filtres selon le contrat existant. Un brouillon invalide conserve la
  période appliquée, les résultats et la pagination, sans nouvelle requête.
- Effacer conserve son périmètre existant : Measurements efface les critères
  qualité/période ; Maintenance seulement la période. Les règles de navigation
  et de pagination des autres actions restent inchangées.
- Une période invalide provenant de l'URL reste signalée immédiatement et ne
  devient pas une requête élargie. Elle n'est pas une saisie initiale incomplète.

La fonction pure validateMeasurementPeriodDraft est partagée dans l'utilitaire
temporel déjà réutilisé par Maintenance. Elle réemploie serializeMeasurementBound
et validateMeasurementPeriod : calendrier réel, bornes avec offset, six décimales,
comparaison précise, intervalle [début, fin). Les champs natifs badInput sont pris
en compte même si leur valeur exposée est vide. Aucun Date, troncature, heure par
défaut ou transformation d'un offset source inchangé. Ni façade ni service API
n'est modifié ; aucun GET n'est ajouté à chaque saisie.

## Première passe - Fichiers concernés

Douze fichiers frontend modifiés et le présent rapport nouveau, soit **13 fichiers** :

- `frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.html`
- `frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.spec.ts`
- `frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.ts`
- `frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.html`
- `frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.scss`
- `frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts`
- `frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.ts`
- `frontend/src/app/features/measurements/utils/measurement-period-draft.spec.ts`
- `frontend/src/app/features/measurements/utils/measurement-period-draft.ts`
- `frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.html`
- `frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.scss`
- `frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.spec.ts`
- `docs/ui-8.8-ux-polish.md`

Aucun fichier shared global modifié : PageHeader et _buttons.scss/_actions.scss
ont été examinés et réutilisés. La feuille Measurements évite de répéter dans les
boutons les déclarations déjà fournies par navigation-action, afin de conserver
le budget local malgré les messages de champs supplémentaires.

## Première passe - Tests et build réellement exécutés

- Ciblés : **200 tests réussis dans 5 fichiers**. Deux listes, détail Sensor,
  navigation Sensor -> Measurements et utilitaire de brouillon temporel.
- Suite Angular complète : **1 908 tests réussis dans 72 fichiers**, exécutée
  **une seule fois** après stabilisation, contre 1 899 historiquement, soit +9.
- Build production : **réussi**, exécuté **une seule fois**, après la suite.
- Couverture : composition silencieuse, soumission implicite neutralisée,
  tentative explicite incomplète/valide, correction pertinente et effacement,
  focus, alerte unique, conservation des résultats et page en erreur, absence de
  GET de saisie, UTC/microsecondes/offsets inchangés, bornes unilatérales,
  égalité/inversion, mauvaise saisie native, liens et visibilité Sensors.

Une première tentative ciblée dans le bac à sable n'a exécuté aucun test, à cause
d'un EPERM sur le cache temporaire Vitest. Les ciblés ont ensuite été exécutés
hors de cette restriction ; un ancien test qui soumettait volontairement le
formulaire a été adapté pour activer le bouton explicite. La suite complète et
le build n'ont pas été répétés. Un espace terminal dans un test a été retiré
après validation, sans changement d'instruction ni d'exécution.
Configuration temporaire à deux workers et journaux dans `frontend/tmp/ui-8.8`,
ignoré par Git, aucun package ni configuration suivie modifié.

| Mesure | Résultat UI 8.8 |
| --- | ---: |
| Bundle initial | **605 998 octets, 606,00 kB**, inchangé par rapport aux 605 998 octets UI 8.5 |
| maintenance-list-component | 42811 octets |
| measurements-list-component | 40261 octets |
| sensor-detail-component | 16453 octets |
| maintenance-detail-component | 16404 octets |
| CSS Sensor Detail | 2 264 octets |
| CSS Measurements List | 3 399 octets |
| CSS Maintenance List | 3 952 octets, inchangé |

CSS compilé/minifié localement avec Sass/esbuild, saut de ligne inclus, distinct
du CSS encapsulé dans les chunks. Aucun nouveau warning SCSS. Budgets inchangés :
initial warning 500 kB/erreur 1 MB, composant warning 4 kB/erreur 8 kB. Le seul
avertissement du build est le dépassement initial historique de **106,00 kB**.
La mutualisation peut déplacer du code entre chunks différés ; les tailles de
chunks ne représentent pas à elles seules le total chargé d'une navigation.

## Première passe - Revue navigateur et accessibilité

Build production servi sur `127.0.0.1:8108`, avec fixtures synthétiques GET
uniquement et aucun proxy FastAPI/PostgreSQL. Les observations ne constituent
ni une recette DEV réelle ni une comparaison SQL. Un premier aperçu sandbox
sur 8099 était inaccessible ; seul l'aperçu 8108 a servi aux contrôles aboutis.

Contrôles Sensors, Measurements et Maintenance aux cibles 1440, 1024, 1023, 768,
390 et 320 px : les cinq autres cibles exactes sont obtenues ; **390 est encadré
à 389/391 px** à cause de l'arrondi du navigateur. Aucune largeur document scrollWidth
supérieure à clientWidth aux largeurs mesurées. Les barres/marges du navigateur
sur certaines captures ne sont pas assimilées à un débordement de l'application.
Six champs temporels toujours présents, boutons accessibles et repliés selon
les styles existants ; tableau à défilement local. Mesures locales :
[Sensor](../frontend/tmp/ui-8.8/responsive-sensor.json) et
[listes](../frontend/tmp/ui-8.8/responsive-lists.json).

Sur les deux listes : saisie d'une date puis Entrée silencieuse après correction ;
activation Appliquer donnant une erreur principale et focus de l'heure manquante ;
correction de l'heure et de la fraction supprimant les messages sans modifier
l'URL appliquée. Effacement Maintenance vérifié. Sur Sensors : focus clavier
visible sur Voir les mesures, aucun ancêtre title, hauteur de 44 px mesurée sur
les trois actions, destinations et apparence secondaire/primaire conservées.

Captures de la première passe enregistrées et examinées, hors Git :

- [Sensor desktop et focus](../frontend/tmp/ui-8.8/screenshots/sensor-1440.png)
- [Sensor mobile et focus](../frontend/tmp/ui-8.8/screenshots/sensor-320.png)
- [Erreur après Appliquer Measurements](../frontend/tmp/ui-8.8/screenshots/measurements-error-1440.png)
- [Erreur après Appliquer Maintenance mobile](../frontend/tmp/ui-8.8/screenshots/maintenance-error-320.png)

Une seule zone role=alert principale réduit les annonces concurrentes ; les
explications locales restent associées aux champs. Audit lecteur d'écran et
ensemble des comportements des calendriers natifs non exhaustifs. Validation
visuelle utilisateur encore attendue, aucune approbation déduite des tests.

## Réserves et état Git

B-SEN-02/03, réserves Measurements, B-MAIN-01 à B-MAIN-09, dates administratives
naïves, absence d'authentification/autorisation de ressource/isolation multi-tenant,
seed strict et budget initial restent ouverts. Aucun contrat backend corrigé.
La précision stockée, l'intégrité PostgreSQL et les preuves HTTP DEV historiques
ne sont pas revalidées ici. Aucun POST/PATCH/DELETE Measurements ou Maintenance,
aucun transfert ni transition ajouté.

Branche feature/frontend-ux-polish, HEAD 2365259 inchangé ; main et origin/main
restent à 2365259. Dix-sept fichiers frontend modifiés, rapport existant actualisé, index
vide. git diff --check réussi. Serveurs et onglet de revue arrêtés après vérification ; dimensions temporaires
du navigateur réinitialisées. Captures, fixtures et journaux
restent ignorés ; aucune donnée sensible ou DSN introduit. Aucun commit, push,
merge ou rebase. Attente de validation visuelle et technique avant livraison.
UI 9.1 non commencée.
