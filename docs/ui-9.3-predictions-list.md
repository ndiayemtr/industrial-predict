# UI 9.3 - Liste, sélection et filtres Predictions

Date : 24 octobre 2026. Implémentation terminée ; présentation générale validée
par l'utilisateur, deux finitions visuelles réalisées avant commit. Validation
finale attendue. Aucun commit effectué. UI 9.4 et UI 9.5 non commencées.

## Références et périmètre Git

Départ conforme : branche `feature/frontend-predictions`, HEAD
`f956c90f4ad187dc897132e48f36d53fac1e99b6`, arbre propre. main et la référence
locale origin/main restent à `05545a88dcd45940f00c1c029d9e567a9c5a4cee`.
Aucun fetch ou changement de branche réalisé pendant cette étape.

Références : [UI 9.1](etape-ui-9.1-predictions.md), décisions PRE-01 à PRE-16,
et [UI 9.2](ui-9.2-predictions-data-access.md). PredictionsApiService et ses
DTO de **14 champs réels** sont réutilisés sans modification.

Le périmètre est limité à la façade locale, aux catalogues et filtres de liste,
à une page standalone, à une route interne lazy et à leurs tests.
Aucun fichier préexistant modifié : backend, contrats UI 9.2, références core,
helpers Measurements/Maintenance, Sidebar, app.routes.ts et Equipment Detail
restent inchangés. Le chemin global `/predictions` mène donc encore au placeholder.
La nouvelle liste est exercée par un routeur de test et un environnement de
revue séparé, sans raccordement prématuré à la production.

## Architecture et fichiers créés

Quatorze fichiers dans `frontend/src/app/features/predictions/` :

| Fichier | Responsabilité |
| --- | --- |
| `models/predictions-state.model.ts` | Query UI avec trois références, pagination et filtres ; union d'états incluant out-of-range |
| `predictions-list.facade.ts` | Résolution réelle des références, lecture scoped, états et annulation switchMap, retry manuel |
| `predictions-list.facade.spec.ts` | Contrats de périmètre, états, erreurs, annulation et destruction |
| `predictions.routes.ts` | Route interne vide, full-match, loadComponent et titre Prédictions ; aucun détail |
| `predictions.routes.spec.ts` | Route interne et maintien du placeholder global jusqu'à UI 9.5 |
| `utils/prediction-query.ts` | Lecture stricte de l'URL, whitelist, pagination, enums, booléen et temporalité |
| `utils/prediction-query.spec.ts` | Valeurs absentes/invalides/répétées, false, tailles et dates précises |
| `utils/prediction-reference-catalog.ts` | Catalogues locaux paginés, accumulation explicite, validation et retry de la page échouée |
| `utils/prediction-period-draft.ts` | Validation UX du brouillon avec bornes inclusives et erreurs associées aux champs |
| `utils/prediction-period-draft.spec.ts` | Préservation des sources, égalité, saisies invalides et correction explicite |
| `pages/predictions-list/predictions-list.component.ts` | Formulaires, URL appliquée, brouillons, cascade et pagination |
| `pages/predictions-list/predictions-list.component.html` | Sélecteurs, filtres, rappel métier, états partagés et tableau accessible |
| `pages/predictions-list/predictions-list.component.scss` | Tokens et mixin d'actions existants, repli responsive, focus et scroll du tableau |
| `pages/predictions-list/predictions-list.component.spec.ts` | Liste complète via RouterTestingHarness et HttpTestingController |

Quinzième fichier : le présent rapport. Aucun autre fichier proposé au suivi Git.

La page fournit sa propre façade avec `providers`, utilise OnPush et signals.
Les subscriptions de page, de façade et de catalogues sont liées au DestroyRef.
Les lectures obsolètes sont annulées par switchMap ; aucun cache global
multi-équipements, polling, chargement exhaustif ou appel par ligne du tableau.

## Sélection, cohérence et parcours

Entreprise -> Site -> Équipement sont trois choix explicites. Aucun premier
élément sélectionné, même lorsqu'un catalogue ne contient qu'une option.
Les sélecteurs affichent les libellés métier nom/code. Un parent réel retrouvé
par GET détail peut être présenté même s'il n'est pas dans la première page
du catalogue ; cela ne sélectionne aucun descendant automatiquement.

Les catalogues utilisent ReferenceDataApiService : entreprises paginées,
sites filtrés par company_id, équipements filtrés par site_id, pages de 50.
« Charger plus » demande la page suivante, sans parcourir toutes les pages
automatiquement. Un changement de parent efface le catalogue descendant et
annule son éventuelle requête en cours. Une panne réseau/5xx permet de réessayer
explicitement la page demandée, y compris une page 2 échouée, sans perdre les
options déjà chargées dans le même périmètre. Les sites/équipements étrangers
au catalogue demandé sont rejetés.

Pour une sélection complète, la façade lit Equipment -> Site -> Company par
les GET détail. Elle compare chaque ID demandé à l'ID reçu, equipment.site_id
au site sélectionné et site.company_id à l'entreprise sélectionnée. Seulement
après cette validation, elle appelle l'historique de cet équipement.
Une sélection partielle cohérente peut vérifier ses parents et charger les
catalogues suivants ; elle ne lance aucun GET Predictions.

Un changement d'entreprise efface site, équipement, filtres et résultats ; un
changement de site efface équipement, filtres et résultats ; un changement
d'équipement efface ses anciens résultats et critères. La taille de page est
conservée, et la page repasse à 1. La façade ne conserve que les parents dont
les IDs sont inchangés pendant la vérification suivante. Les catalogues dont
le parent ne change pas ne sont pas rechargés à chaque choix d'équipement.

Les contextes URL contradictoires, références invalides et doublons de clés
reconnues sont bloqués. Aucune inférence d'ancêtre ni lecture globale de
prédictions n'est utilisée pour réparer une URL. « Recommencer la sélection »
est une action explicite effaçant le périmètre ; la correction d'un filtre
préserve les références de l'URL et doit toujours repasser la validation réelle.
Ces protections concernent la cohérence UI et ne sont pas une autorisation tenant.

## Filtres, pagination et temporalité

Historique consommé exclusivement par PredictionsApiService :
`GET /api/v1/equipments/{equipment_id}/predictions`.
L'API ne reçoit jamais company_id ou site_id depuis la liste.

Filtres : quatre types exacts (`anomaly`, `failure_risk`, `health_score`, `rul`),
level libre exact de 1 à 50 points de code Unicode lorsqu'il est renseigné,
alerte Tous/Oui/Non, et bornes de predicted_at. Les espaces du niveau sont
conservés. Tous omet is_alert, Non envoie explicitement false. La valeur query
`null` est invalide, sans conversion en omission ; les réponses peuvent en
revanche contenir is_alert=null, affiché « Non renseignée ».

Les filtres, y compris les sélecteurs de type et d'alerte, sont des brouillons
appliqués avec « Appliquer les filtres ». Aucune lecture à chaque frappe ou
changement de brouillon. L'état appliqué et ses chaînes sources sont rappelés
sous les champs. Pagination, taille et actualisation utilisent les critères
appliqués, sans appliquer les brouillons en attente. Les brouillons sont
préservés lors d'un changement de page ou de taille dans le même périmètre.

La pagination est serveur : page 1 et taille 20 par défaut, choix 20/50/100,
avec ajout du choix URL valide éventuel (par exemple 37). Toute taille 1..100
est acceptée. Une valeur URL invalide est signalée, sans normalisation
silencieuse ou lecture élargie. Changement de filtre appliqué ou de taille :
page 1. Aucun tri local ou recherche absent du backend. L'ordre du serveur est
conservé et expliqué dans la caption. Aucun rechargement automatique d'une
page hors plage : le bouton propose explicitement la page 1.

Période `[start_time, end_time]` : début inclus, fin incluse, égalité permise,
comparaison à la microseconde. Chaque borne saisie comporte date et heure UTC
avec secondes, et une fraction optionnelle jusqu'à six chiffres. Les champs
natifs peuvent représenter une minute entière sans secondes textuelles ; la
sérialisation partagée conserve alors les secondes nulles de cette heure
explicitement saisie, sans inventer une heure quand seule la date est fournie.
Aucune date courante, période ou heure par défaut.

Les calculs d'instants et les fonctions pures de restauration/sérialisation
d'une borne existantes sont réutilisés depuis Measurements. Les validateurs
de période à fin exclusive ne sont pas appelés. La nouvelle validation UX
utilise validatePredictionPeriod de UI 9.2 pour accepter l'égalité.
Une source inchangée garde sa chaîne ISO, son offset et ses six décimales,
y compris les zéros terminaux. Les contrôles montrent ses composantes UTC ;
une modification explicite crée une nouvelle borne UTC avec Z. Il n'y a pas
de normalisation silencieuse d'une source inchangée ou de perte de précision.

La soumission implicite du formulaire est neutralisée ; seul le bouton
d'application lance la validation. Une date incomplète, heure invalide,
fraction trop longue, période inversée ou niveau trop long ne remplace pas
les résultats appliqués. Les erreurs sont associées aux champs et regroupées
dans une zone d'alerte ; le focus est placé sur ce résumé après le rendu.
La correction met à jour les erreurs sans GET, puis peut être appliquée.
Effacer la période conserve les autres filtres appliqués. Réinitialiser les
filtres et la pagination est une action distincte et explicite.

## États et présentation de liste

| État | Comportement |
| --- | --- |
| idle | Invite à sélectionner les trois références, sans historique global |
| loading | Vérification/lecture en cours ; aucune ligne de l'ancien équipement n'est affichée |
| success | Tableau paginé et rappel du contexte métier validé |
| empty sans filtre | « Aucune prédiction enregistrée pour cet équipement » |
| empty avec filtres, y compris is_alert=false | « Aucune prédiction ne correspond aux filtres » et action d'effacement |
| out-of-range | Page vide avec total non nul conservé et bouton vers la page 1 |
| error | Erreur explicite, sans résultat fictif ni élargissement de périmètre |

Réseau/5xx : retry manuel des mêmes critères appliqués. 404 : références à
vérifier ; 422 : paramètres/filtres/pagination à corriger ; 401/403 : accès
refusé si ces statuts sont reçus. Erreur de contrat ou de rattachement : pas
de retry automatique. Une liste vide ne diagnostique pas un modèle absent.

PageHeader, LoadingState, EmptyState et ErrorState sont réutilisés. Le tableau
comporte cinq colonnes : predicted_at intégral avec offset, type, **score brut
déclaré**, niveau déclaré et alerte déclarée. Aucun pourcentage universel,
unité supposée, reclassement, probabilité inférée ou score agrégé.
Les niveaux inconnus restent affichables et les alertes sont textuelles.
Métadonnées modèle/horizon, JSON dépliable et présentation métier avancée
restent UI 9.4. Aucun détail, lien Equipment ou navigation globale ajouté.

## Tests et build exécutés

Configuration locale Vitest à deux workers réutilisée, sans modification
suivie des configurations ou dépendances. Commandes depuis `frontend/`,
exécutées séquentiellement après stabilisation :

```powershell
node node_modules/@angular/cli/bin/ng.js test --watch=false --include=src/app/features/predictions/**/*.spec.ts --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false
node node_modules/@angular/cli/bin/ng.js test --watch=false --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false
node node_modules/@angular/cli/bin/ng.js build --configuration production --progress=false
```

| Vérification | Résultat exact |
| --- | --- |
| Tests ciblés finaux Predictions | **314 réussis dans 7 fichiers**, 0 échec ; durée Vitest 8,36 s |
| Tests UI 9.3 ajoutés | **96**, en plus des 218 tests UI 9.2 conservés |
| Suite Angular complète | **2 226 réussis dans 79 fichiers**, 0 échec ; durée Vitest 51,05 s ; une seule exécution |
| Build production | **Réussi**, génération en 25,942 s ; une seule exécution |
| Bundle initial | **605 998 octets (606,00 kB)** ; transfert estimé 153,92 kB ; inchangé |
| Avertissement | Dépassement initial existant de **106,00 kB** au-dessus du budget 500 kB ; aucun autre warning signalé |

La taille exacte est mesurée par la somme des neuf fichiers initiaux produits
dans `frontend/dist/industrial-predict-ui/browser`. Le build de production
n'inclut pas encore de chunk Predictions accessible : la route interne n'est
pas importée par le routeur global. La réussite ne prouve donc pas son
intégration dans le Shell, qui reste UI 9.5. Les templates et styles de la
liste sont compilés/exercés par les tests et la revue de développement isolée.
Budgets inchangés : initial 500 kB/1 MB, composants 4/8 kB.

Stabilisation ciblée avant ces résultats : une compilation a signalé le
typage d'une union d'Observable nullable, corrigé explicitement ; une passe
suivante a eu 312 réussites et 1 échec de scénario catalogue. L'orchestration
des changements de périmètre a été affinée pour garder les seuls parents
inchangés, éviter les relectures de catalogues inchangés et annuler les autres
lectures ; les attentes ont été adaptées et un scénario supplémentaire ajouté.
La passe finale initiale a les 314 réussites indiquées. Ces résultats complets
et la mesure du bundle précèdent les finitions de libellés et de SCSS décrites
ci-dessous ; les contrôles complémentaires portent sur leur version finale.
La logique TypeScript, les contrats HTTP et la validation temporelle restent
inchangés depuis la suite complète et le build.

Scénarios couverts : choix explicites/cascade, références partielles ou
contradictoires, refus de lecture sans chaîne complète, catalogues paginés et
retry, références hors première page, changement rapide de périmètre,
annulation/destruction, filtres seuls/combinés, false/null/absence, doublons
URL et corrections explicites, périodes inclusives égales avec offsets et
microsecondes, brouillons, soumission implicite neutralisée, erreurs UX et
focus, tailles arbitraires valides, pagination/hors plage, vides distincts,
404/422/5xx/réseau, et interdiction des écritures/calculs.

Les tests utilisent HttpTestingController et un routeur isolé. Aucun HTTP
métier réel, PostgreSQL, test backend ou calcul ML pendant ces validations.

## Revue navigateur : exécution réelle, données simulées

Revue réalisée avec la compétence [computer-use](C:/Users/Matar/.codex/plugins/cache/openai-bundled/computer-use/26.1016.62342/skills/computer-use/SKILL.md),
dans le navigateur intégré. Une application Angular temporaire de développement
charge la véritable route interne et les véritables composants UI 9.3, sans
modifier app.routes.ts. Elle est placée dans
`frontend/tmp/ui-9.3/preview/`, ignoré par Git, et sert uniquement sur
`127.0.0.1:4213`.

Un intercepteur HTTP de fixture en mémoire répond aux GET métier attendus et
refuse toutes les autres requêtes. Aucun proxy FastAPI, accès PostgreSQL,
seed, écriture ou inférence. Le bandeau visible indique explicitement
« REVUE ISOLÉE - DONNÉES FICTIVES - Aucun accès DEV ». Les quatre lignes
synthétiques ne sont pas des données DEV réelles. Ce serveur de développement
ne constitue pas un second build production.

Observations réellement réalisées :

- Liste des quatre types et valeurs brutes, références nom/code, null/false/true
  visibles sans probabilité ou unité inférée.
- Changement d'alerte vers Non : brouillon distinct, quatre lignes inchangées
  avant application ; application au clavier avec Entrée sur le bouton,
  is_alert=false dans l'URL et deux lignes après lecture simulée.
- Date seule puis Appliquer : heure non inventée, résultat appliqué conservé,
  aria-invalid sur l'heure manquante, focus réel du navigateur sur le résumé.
  Tab depuis le résumé atteint le bouton Appliquer avec contour visible.
- Correction vers deux bornes UTC égales `2026-10-23T12:00:00.123456Z` :
  application réussie, deux lignes simulées retenues, fractions présentes dans
  l'URL et dans le rappel de période ; horodatages de ligne avec +05:30 conservés.
- Largeurs **CSS mesurées** : 320, 391, 768, 1023, 1024 et 1440 px. Aucun
  scrollWidth global supérieur au viewport ; sélecteurs empilés sur petit
  écran, grille sur grand écran, tableau défilant dans son propre conteneur.
  Le réglage de viewport a été adapté au facteur de zoom déjà présent pour
  obtenir ces largeurs CSS ; aucun changement du zoom utilisateur revendiqué.
- Aucun message console warn/error dans le parcours de revue consulté.

Captures locales ignorées, examinées pendant la revue :

- [Liste 1440 px CSS](../frontend/tmp/ui-9.3/screenshots/list-1440.png).
- [Liste 320 px CSS](../frontend/tmp/ui-9.3/screenshots/list-320.png).
- [Erreur de période](../frontend/tmp/ui-9.3/screenshots/period-error.png).
- [Période égale appliquée](../frontend/tmp/ui-9.3/screenshots/equal-period-1440.png).

Mesures complémentaires : `frontend/tmp/ui-9.3/responsive.json` pour
391/768/1023/1024/1440 px ; la mesure 320 px est consignée dans l'observation
de revue et sa capture. Dimensions temporaires du navigateur réinitialisées,
onglet de revue fermé et seul serveur de revue 4213 arrêté avant la suite complète.

Limites : revue hors Shell global, données et filtrage simulés, pas de preuve
SQL ou DEV. Zoom réel 200/400 % et lecteur d'écran réel non testés ; tous les
comportements des calendriers natifs et chaque combinaison de filtres n'ont
pas été rejoués visuellement. Les changements rapides, multipages, pannes et
URLs contradictoires sont principalement prouvés par les tests automatisés.
Validation visuelle finale de l'utilisateur toujours attendue.

## Finitions visuelles avant commit

Après validation de la présentation générale par l'utilisateur, seules deux
finitions de présentation ont été apportées :

- Libellés temporels raccourcis en « Date », « Heure UTC » et « Fraction
  (0 à 6 chiffres) ». Les légendes de fieldset conservent « Début UTC (inclus) »
  et « Fin UTC (incluse) ». L'aide est allégée tout en rappelant égalité,
  secondes, six décimales facultatives, absence d'heure par défaut et conservation
  des offsets inchangés. Associations label/for, IDs et aides de validation conservés.
- Trois boutons de filtres sans étirement (`flex: 0 1 auto`), groupés à gauche
  avec retour à la ligne, alignement en début de groupe et gap commun de 8 px.
  Le mixin d'actions existant garde géométrie, hauteur minimale et focus.

Seuls `predictions-list.component.html`, `predictions-list.component.scss`
et ce rapport ont changé depuis la passe initiale UI 9.3. Les empreintes
SHA-256 avant/après des 15 fichiers ont permis de vérifier ce périmètre.
Aucun test ajouté ou modifié, aucun changement TypeScript, API, URL, pagination,
état, brouillon, score brut ou règle temporelle.

Contrôle Angular ciblé depuis `frontend/` :

```powershell
node node_modules/@angular/cli/bin/ng.js test --watch=false --include=src/app/features/predictions/pages/predictions-list/predictions-list.component.spec.ts --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false
```

Résultat après finitions : **37 tests réussis dans 1 fichier**, 0 échec ; durée
Vitest **9,61 s**. La compilation ciblée inclut le template et le SCSS finaux.
Les scénarios de formulaire, focus, filtres/brouillons, dates inclusives,
pagination et annulations existants restent vérifiés. Ni suite Angular complète
ni build production relancé : les **2 226 tests / 79 fichiers**, le build réussi
et les **605 998 octets** restent les références historiques avant ces finitions,
sans nouvelle mesure production revendiquée. La logique et le routage global
sont inchangés ; la compilation ciblée et le serveur de revue vérifient les
modifications de présentation, sans justifier une nouvelle exécution complète.

Revue navigateur complémentaire sur les mêmes fixtures isolées, sans DEV :

| Largeur CSS mesurée | Largeur globale scrollWidth | Boutons et disposition |
| --- | --- | --- |
| 320 px | 300 px | Trois lignes, à gauche ; 44/44/65,78 px de hauteur, dernier texte sur deux lignes sans débordement |
| 390 px | 370 px | Trois lignes à gauche ; trois boutons de 44 px de hauteur |
| 768 px | 748 px | Trois boutons sur une ligne à gauche ; trois hauteurs de 44 px |

Le navigateur intégré arrondit les dimensions de sa surface selon son facteur
de zoom. Pour le cas exact 390 px, un iframe de revue de **390 px CSS** charge
la même page réelle et les mêmes fixtures ; son innerWidth et son scrollWidth
ont été mesurés à l'intérieur du cadre. Ce cadre est ajouté uniquement au
lanceur temporaire ignoré, jamais au code de la feature. À 320/768 px, mesures
dans la page directement. Les différences de 20 px ci-dessus correspondent à
la place du défilement vertical, sans débordement horizontal global. Le tableau
conserve son défilement horizontal interne attendu sur les petits écrans.

Gap mesuré : **8 px** ; justify-content : flex-start ; flex-grow des trois
boutons : 0. Largeurs des deux premiers boutons : environ **174,78 et 160,65 px** ;
troisième : **304,86 px** à 390/768 px, réduit à **249,78 px** avec texte replié
à 320 px. La cible minimale de 44 px est préservée, sans imposer une hauteur
fixe qui couperait le libellé long. Tab vers « Effacer la période » : focus
effectif et contour solid constatés à 320 px et dans le cadre 390 px.
Aucun warn/error console relevé dans la revue complémentaire.

Limite : l'outil de capture a échoué pendant cette passe. Les captures de la
première revue restent des preuves historiques avant finitions ; aucune capture
actualisée n'est présentée comme vérifiée. La présente vérification repose sur
le DOM rendu, les mesures CSS dans le navigateur et les contrôles clavier.
Mesures et journal ciblé dans `frontend/tmp/ui-9.3/finish/responsive.json` et
`targeted-tests.log`, ignorés. Dimensions de revue réinitialisées, onglet fermé
et serveur 4213 arrêté. Validation finale utilisateur attendue.

## Risques B-PRE conservés

| Réserve | Situation après UI 9.3 |
| --- | --- |
| B-PRE-01 | Authentification, autorisation de ressource et isolation multi-tenant toujours absentes ; la cascade UI n'est pas une barrière SaaS serveur |
| B-PRE-02 | Scores/niveaux backend génériques inchangés ; affichage brut explicite, sans échelle ou probabilité déduite de la valeur |
| B-PRE-03 | Validation offset/période côté client ; backend inchangé, bornes inclusives conservées |
| B-PRE-04 | Intégrité Equipment/Sensor/Measurement backend toujours partielle ; aucun lien vers les descendants à partir de ces seuls IDs |
| B-PRE-05 | JSON backend générique/volumineux toujours possible ; aucun JSON rendu ici, limites de présentation futures sans limite réseau/backend |
| B-PRE-06 | Cascades backend inchangées ; aucune suppression UI |
| B-PRE-07 | OFFSET/COUNT distincts et index simples inchangés ; pagination serveur, annulation et absence de lectures exhaustives |
| B-PRE-08 | Risques des POST RUL/artefacts inchangés ; aucun de ces endpoints appelé |
| B-PRE-09 | Aucun mécanisme d'alimentation de l'historique ajouté ; vide neutre, aucune génération automatique ou diagnostic de modèle absent |
| B-PRE-10 | Données historiques/provenance potentiellement invalides ou incomplètes ; contrat UI 9.2 défensif conservé sans correction des données |
| B-PRE-11 | Aucun GET détail/latest exposé ; seule liste utilisée, aucune page détail créée |

La recette DEV et la présence réelle des prédictions restent différées à UI 9.6.
La nouvelle page n'affirme aucune aptitude à la production SaaS multi-tenant.

## État Git final et validation attendue

- Branche `feature/frontend-predictions`, HEAD `f956c90f4ad187dc897132e48f36d53fac1e99b6` inchangés.
- main et origin/main local inchangés à `05545a88dcd45940f00c1c029d9e567a9c5a4cee`.
- **15 fichiers nouveaux non suivis** : 14 fichiers Predictions et ce rapport.
- Aucun fichier préexistant modifié ; index vide. Aucun secret ou artefact
  ajouté au périmètre proposé. Captures, preview et journaux restent ignorés.
- `git diff --check` et contrôle d'espaces des nouveaux fichiers réussis.
- Aucun commit, push, merge, rebase, package, changement backend ou accès DEV.

Journaux de validation : `frontend/tmp/ui-9.3/targeted-tests.log`,
`full-tests.log`, `build.log`, ignorés par Git.
Attente de validation technique et visuelle avant commit ou poursuite.
