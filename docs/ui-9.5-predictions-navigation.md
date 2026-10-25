# UI 9.5 — Routing et navigation Predictions

## Périmètre et préconditions

Branche `feature/frontend-predictions`, HEAD initial
`da9f0e07ad33b4f3ea65b13f59ce2e72743596e3`, dépôt propre vérifié avant les
modifications. Références : conception UI 9.1 et bilans UI 9.2, 9.3, 9.4.
Les conventions de routage, d'actions et de retour existantes Sensors,
Measurements et Maintenance ont été examinées.

Le module Prédictions devient accessible dans le Shell. Aucun changement de
contrat backend, de DTO ou de transport Predictions ; aucun calcul ML. Les
quatre types, les scores/détails UI 9.4, les états et les bornes inclusives avec
égalité, offsets et microsecondes restent inchangés. UI 9.6 non commencée.

## Fichiers concernés

**17 fichiers existants modifiés**, sous `frontend/` :

- `src/app/app.routes.ts` et `src/app/app.routes.spec.ts` : lazy Predictions et
  tests des invariants de routage, titres et 404.
- `src/app/features/predictions/predictions.routes.ts` et son `.spec.ts` :
  commentaire et attente de connexion au routage global.
- `src/app/features/predictions/pages/predictions-list/predictions-list.component.ts`,
  `.html`, `.scss`, `.spec.ts` : lien Equipment à partir des références vérifiées
  et adaptation d'une assertion de rendu aux nouvelles actions.
- `src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts`,
  `.html`, `.scss`, `.spec.ts` : nouvelle action et retour typé ; cinq actions
  au maximum, avec une seule action Predictions selon le contexte validé.
- `src/app/features/equipments/pages/equipment-detail/equipment-maintenance-navigation.spec.ts` :
  ordre attendu actualisé pour l'action ajoutée ; comportement Maintenance conservé.
- `src/app/layout/sidebar/sidebar.component.spec.ts` : véritable liste au lieu
  du placeholder, entrée unique et sélection active.
- `src/app/layout/shell/shell-focus.spec.ts` et `shell-responsive.spec.ts` :
  parcours Predictions ajoutés aux contrôles de focus et tiroir mobile.
- `src/styles/_buttons.scss` : ajout des trois sélecteurs d'actions Predictions
  aux conventions hover, active, focus et reduced-motion existantes.

**Quatre nouveaux fichiers** :

- `frontend/src/app/features/predictions/utils/prediction-navigation.ts`.
- `frontend/src/app/features/predictions/utils/prediction-navigation.spec.ts`.
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-predictions-navigation.spec.ts`.
- Le présent rapport `docs/ui-9.5-predictions-navigation.md`.

Soit **21 fichiers proposés**. Aucun code Sidebar, Shell ou autre module modifié
au-delà de l'intégration décrite ; leurs tests sont adaptés. Aucun package,
budget Angular, backend, migration, seed ou outillage DEV modifié.

## Routage lazy et navigation

`/predictions` utilise `loadChildren` vers `PREDICTION_ROUTES`, puis le
`loadComponent` existant de la liste. Une seule route interne, vide et
`pathMatch: full` ; aucun `/predictions/:id`. Les chemins inconnus, dont
`/predictions/17` et `/predictions/new`, restent sur la 404 globale.
Entrée, icône, thème, titre dynamique et sélection Sidebar conservés. Le Shell
continue de gérer le focus et son tiroir responsive.

Equipment Detail expose « Voir les prédictions » seulement lorsque les lectures
Equipment → Site → Company ont confirmé les trois IDs positifs et les deux
rattachements. La destination est `/predictions` avec les parents réellement
lus, `equipment_id`, `page=1`, `page_size=20`. Les filtres Equipment ne sont
pas copiés. Les actions retour liste, capteurs, interventions et modifier sont
conservées. Action secondaire, libellé visible, aucun tooltip et mixin partagée.

La liste expose « Voir la fiche équipement » seulement pour un périmètre
entièrement vérifié et correspondant à sa requête appliquée. Un `UrlTree`
construit la destination fixe `/equipments/{id}`. Aucun appel supplémentaire
d'historique n'est associé à ce lien.

## Contexte URL typé

`PredictionNavigationContext` transporte `from: 'predictions'` et une
`PredictionsQuery`. La whitelist est exactement :

`company_id`, `site_id`, `equipment_id`, `page`, `page_size`, `prediction_type`,
`level`, `is_alert`, `start_time`, `end_time`.

Le lien vers Equipment préfixe ces seules clés avec `pre_`, après validation
par le parseur Predictions existant. Les valeurs URL sont des chaînes ; false
devient explicitement `false`, jamais une absence. Les chaînes temporelles,
offsets et fractions ne sont ni convertis ni normalisés. Les champs absents
sont omis. Aucun brouillon non appliqué ne quitte la liste.

Equipment Detail propose « Retour aux prédictions » uniquement lorsque le
contexte d'origine est valide, et masque alors « Voir les prédictions ».
Cette action occupe le même emplacement que l'action de consultation, après
les interventions et avant Modifier. Son contexte est indépendant de
`listQuery` Equipment et des parents réels relus sur la fiche. Validation de
`from` unique, clés reconnues non dupliquées, filtres/période/pagination valides,
trois IDs présents et `pre_equipment_id` égal à l'ID de la fiche. Une origine
Predictions invalide, partielle ou contradictoire ne donne aucun bouton de
retour. En l'absence de contexte valide, seule « Voir les prédictions » peut
apparaître, après vérification de la chaîne Equipment → Site → Company, avec
le périmètre réel et une pagination neuve. Avant cette vérification, aucune
action de consultation Predictions n'est proposée. Un retour validé reste
disponible même pendant le chargement ou l'échec de la fiche ; la liste cible
revalide ses références avant toute lecture d'historique.

Clés inconnues, `returnUrl`, `pre_returnUrl`, fragments et filtres Equipment
ne sont jamais suivis ni propagés. Aucun chemin libre. Les liens Sensors,
Maintenance, modifier et retour liste Equipment ne reçoivent pas de `pre_`.
Les conventions des autres modules restent inchangées.

Au retour, la liste reconstruit ses filtres appliqués et sa pagination depuis
l'URL validée, puis revalide les références réelles. Un changement de parents
entre deux écrans bloque la lecture ; le contexte URL n'est pas une autorisation.
Les brouillons locaux et panneaux ouverts ne sont pas persistés après destruction
de la page, conformément au retour par URL appliquée.

## Tests réellement exécutés — passe initiale avant finition UX

Toutes les requêtes des tests sont simulées par HttpTestingController ou les
providers de test du routage. Les tests de navigation dédiés refusent toute
méthode autre que GET. Aucune fixture de test n'est envoyée au backend réel.

Passe ciblée finale : **642 tests réussis sur 20 fichiers**, compilation 17,741 s,
Vitest 21,22 s. Commande exécutée depuis `frontend/`, via le CLI local :

```text
ng test --watch=false
  --include=src/app/features/predictions/**/*.spec.ts
  --include=src/app/features/equipments/pages/equipment-detail/*.spec.ts
  --include=src/app/app.routes.spec.ts
  --include=src/app/layout/sidebar/sidebar.component.spec.ts
  --include=src/app/layout/shell/*.spec.ts
  --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false
```

Les passes de mise au point ne sont pas présentées comme réussies : première
passe 596 réussis/16 échoués, avec l'ancien test placeholder et une erreur
d'alerte lors de la sérialisation du nouveau contexte ; correction par chaînes
URL avant validation. Deuxième passe 641 réussis/1 échoué : listener popstate
non initialisé par le harness. Le test active désormais le listener du Router
et attend NavigationEnd, sans modification de la politique de navigation réelle.

Couverture : Sidebar, lazy/404/titres, actions Equipment et parents absents ou
incohérents, absence d'historique avant validation complète, contexte complet ou
partiel, clés dupliquées, paramètres invalides, égalité temporelle et offsets,
false/absence, origine contradictoire, repli sûr, isolation des filtres des autres
modules, brouillon distinct de l'appliqué, retours directs/rechargés, changement
de périmètre et arrière/avant. Les tests UI 9.2 à UI 9.4 restent inclus.

**Une seule suite Angular complète** : **2 376 tests réussis sur 84 fichiers**,
compilation 19,180 s, Vitest 53,63 s :
`ng test --watch=false --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false`.

**Un seul build production**, réussi en **14,412 s** :
`ng build --configuration production --progress=false`.
Bundle initial exact **606 501 octets**, somme des neuf fichiers initiaux émis,
soit **+503 octets** par rapport à UI 9.4. Affichage CLI 606,50 kB ; transfert
estimé 153,84 kB. Chunk lazy `predictions-list-component` : **48 938 octets**,
transfert estimé 13,13 kB. Avertissement initial au-delà de 500 kB conservé
(+106,50 kB), aucun budget changé. Aucun dépassement de budget de style signalé.
Ordre : ciblés stabilisés, suite complète, build. Ces résultats et la taille
du bundle précèdent la finition UX ci-dessous ; ils ne sont pas présentés comme
une nouvelle validation complète de la version corrigée. Le périmètre limité
de cette correction est revérifié par tests ciblés et compilation de
développement, sans relance de la suite complète ni du build production.

Journaux locaux ignorés : `frontend/tmp/ui-9.5/targeted.log`,
`targeted-initial.log`, `targeted-history-mock.log`, `full-tests.log`, `build.log`.

## Navigateur : preuves DEV réelles, uniquement en lecture

Services permanents déjà actifs sur 4201/8001 ; aucun lancement Angular
supplémentaire, aucun port de prévisualisation isolée, aucune opération Docker.
Guide utilisé : `infra/development/README.md`. Avant les lectures métier, les GET
`/__dev/identity` direct et via le proxy ont confirmé mode `local-development`,
base `industrial_predict_dev`, rôle `ui47_app`, superuser false, révision
`09ac8101e9fe` et instance correspondant à la configuration privée. Aucun secret
ou identifiant d'instance privé n'est publié.

Lectures observées dans l'application réelle sur `http://127.0.0.1:4201` :

- Sidebar et véritable page Prédictions avec sélection attendue, titre et
  entrée active ; aucun placeholder.
- Sélection explicite de l'entreprise `id=1` INDUSTRIE DEMO A, site `id=1`
  Site de production, fiche de l'équipement `id=1` Pompe de circulation P101.
  Ces données de démonstration sont déjà présentes dans PostgreSQL DEV ; elles
  ne sont pas les fixtures HTTP en mémoire des tests et n'ont pas été créées ici.
- Action Equipment → Predictions : IDs 1/1/1 réels, page 1, taille 20 ;
  état **0 prédiction / Aucune prédiction enregistrée** observé pour P101.
- Application réelle du type RUL, alerte Non et période égale
  `2026-10-01T00:00:00.123456Z` aux deux bornes. État « Aucun résultat » observé.
  Un brouillon de niveau n'est pas exporté dans le lien Equipment. Au retour,
  seul l'appliqué est restauré ; niveau vide, false explicite et fractions intacts.
- Retour Equipment → Predictions, rafraîchissement du navigateur et
  arrière/avant : contexte appliqué conservé. Focus `main-content` après
  changement de page, titres Header/document et entrée active synchronisés.
- Contexte direct partiel `company_id=1` : sélection attendue sans lien fiche.
  Changement vers entreprise `id=2` : site/équipement remis à null.
  `company_id=1&company_id=1` : message local de paramètre répété observé.
- Sidebar mobile ouverte avec Entrée, focus sur Fermer, navigation Prédictions
  ferme le tiroir. Pour ce changement de query sur le même chemin, focus rendu
  au bouton Sidebar selon la politique existante ; route `/predictions` sans scope.
- Aucun warn/error console relevé pendant ces parcours.

Mesures réelles du navigateur, page Prédictions avec contexte appliqué :

| Largeur CSS | scrollWidth document | Contrôle |
| --- | --- | --- |
| 1440 | 1420 | Aucun débordement global ; actions de 44 px |
| 768 | 748 | Aucun débordement global ; actions de 44 px |
| 320 | 300 | Aucun débordement global ; actions >=44 px, libellé long de réinitialisation replié à environ 63 px |

Equipment à 320 px : document 300 px, cinq actions à 44 px, aucun débordement
global. Après finition, à 1440 px avec retour Predictions, cinq actions en deux
lignes, toutes de 44 px ; actions secondaires et Modifier primaire conservés.
Le facteur viewport du navigateur est 0,75, dimensions CSS mesurées directement.

Capture initiale : `frontend/tmp/ui-9.5/dev-equipment-desktop.png`, avant la
correction d'exclusivité ; preuve historique remplacée pour les actions par
les captures de finition ci-dessous. Les tentatives
de capture mobile et de l'état vide ont échoué avec le seul message « Unable
to capture screenshot » ; aucune cause interne accessible n'est inventée.
Les mesures, textes et parcours correspondants restent des preuves DOM/clavier,
dans `responsive.json` et `dev-duplicate-context-dom.txt`, ignorés. Aucune
capture manquante n'est présentée comme produite. Onglet fermé, viewport et
visibilité réinitialisés ; services DEV permanents laissés actifs.

## Finition UX — exclusivité des actions Equipment Detail

À la demande de revue visuelle, la présentation finale est désormais :

| Contexte de retour | Chaîne réelle | Action Predictions |
| --- | --- | --- |
| Valide et lié à l'ID de la fiche | Chargée, en cours ou en erreur | Retour aux prédictions, filtres et pagination appliqués conservés |
| Absent ou invalide | Entièrement vérifiée | Voir les prédictions, vrais IDs, page 1 et taille 20 |
| Absent ou invalide | Non résolue ou incohérente | Aucune action Predictions |

Le template utilise une branche `if / else if` et le computed de consultation
est également nul lorsqu'un retour valide existe : jamais les deux actions.
Les autres liens sont inchangés. Même emplacement dans l'ordre de tabulation,
même mixin secondaire et même flex-wrap partagé ; aucun style transverse
supplémentaire ni tooltip. La disparition de l'action redondante permet le
regroupement en deux lignes à 1440 px, sans Modifier isolé sur une troisième.

Correction limitée à cinq fichiers de la livraison UI 9.5 : Equipment Detail
`.ts`/`.html`, test `equipment-predictions-navigation.spec.ts`, commentaire de
`prediction-navigation.ts` et ce rapport. Aucune modification du service API,
du parseur `pre_`, des règles UTC, du backend ou du CSS partagé pendant cette
finition. La nouvelle règle d'affichage remplace le précédent retour sans
contexte vers `/predictions` en cas de `pre_` invalide.

Validation complémentaire : **163 tests ciblés réussis sur cinq fichiers**,
compilation 45,988 s, Vitest 37,62 s. Une seule passe complémentaire exécutée :

```text
ng test --watch=false
  --include=src/app/features/equipments/pages/equipment-detail/*.spec.ts
  --include=src/app/features/predictions/utils/prediction-navigation.spec.ts
  --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false
```

Les tests contrôlent l'exclusivité à chaque stabilisation, contexte valide,
absent, partiel, invalide/dupliqué/contradictoire, parents non résolus ou en
erreur, disponibilité du retour validé pendant une erreur Equipment, changement
de query sur la même fiche, conservation des quatre autres actions, absence de
tooltip, focus, aller-retour et historique arrière/avant. Filtres, offsets,
égalité et pagination sont restaurés par les tests de navigation conservés.
Journal ignoré : `frontend/tmp/ui-9.5/finish/targeted.log`. Les 2 376 tests de la
passe initiale et le build ne sont pas relancés : correction locale du choix
d'action, sans changement des contrats, du routage, du Shell ou du transport.
Le bundle de production après cette finition n'a donc pas été remesuré.

DEV permanent 4201/8001 à nouveau identifié avant toute lecture, mêmes contrôles
de base/rôle/mode/instance/révision, sans secret affiché. Sur la fiche P101,
contexte valide avec `pre_page=2`, RUL, alerte false et bornes identiques
`2026-10-01T00:00:00.123456Z` : uniquement Retour, quatre autres actions visibles.
Le retour au clavier restaure page 2, taille 20, filtres et précision ; focus
sur `main-content`. Arrière navigateur : Retour seul à nouveau. Avec
`from=predictions&pre_page=0`, puis sans origine : Voir seul, destination
réelle 1/1/1 avec page 1 et taille 20. Aucune écriture métier ou création de
prédictions ; état filtré vide observé, pas de recette SQL UI 9.6.

Mesures de la fiche avec retour validé :

| Viewport CSS | scrollWidth document | Actions |
| --- | --- | --- |
| 1440 | 1440 | Cinq actions, 44 px, deux lignes, écart vertical 8 px |
| 768 | 768 | Cinq actions, 44 px, trois lignes, écart vertical 8 px |
| 320 | 300 | Cinq actions, 44 px, cinq lignes, écart vertical 8 px |

Aucun débordement global mesuré. À 320 px avec contexte invalide, document
300 px et une seule action Voir. Tab depuis Interventions atteint l'action
Predictions dans les deux variantes ; contour solid, aucun attribut title.
Aucun warn/error console relevé. Mesures ignorées :
`frontend/tmp/ui-9.5/finish/responsive.json`.

Captures actualisées sur données déjà présentes dans PostgreSQL DEV :

- `frontend/tmp/ui-9.5/finish/equipment-return-desktop.png` : Retour seul,
  cinq actions et focus visible, disposition nette en deux lignes.
- `frontend/tmp/ui-9.5/finish/equipment-fresh-desktop.png` : Voir seul, même
  regroupement ; netteté et cadrage de cette seconde capture limités par l'outil,
  textes exacts confirmés dans le DOM.

Onglet fermé, dimensions et visibilité réinitialisées, services permanents
laissés actifs. Aucune instance supplémentaire lancée. La présentation corrigée
a reçu la validation visuelle finale utilisateur le 25 octobre 2026.

### Validation finale et préparation du commit — 25 octobre 2026

La nouvelle capture utilisateur est validée : Retour aux prédictions affiché,
Voir les prédictions masqué pour un contexte valide et autres actions préservées.
Le passage de Modifier sur une deuxième ligne est accepté pour cette étape.
Le regroupement et le flex-wrap restent inchangés ; aucune nouvelle finition
visuelle ni modification du code n'est apportée lors de cette préparation.

Branche et HEAD revérifiés : `feature/frontend-predictions`, `da9f0e0`.
Les **163 tests ciblés réussis sur cinq fichiers** sont confirmés par le
journal de la finition du 24 octobre, relu avec les assertions et les sources
concernées. Ils ne sont pas présentés comme une nouvelle exécution du 25 octobre.
Aucun test, build ou parcours DEV relancé pour cette mise à jour documentaire.
Les 2 376 tests complets et le bundle 606 501 octets restent les résultats
historiques de la première passe, avant finition, selon la distinction ci-dessus.

Relecture de non-régression : branche exclusive `if / else if`, contexte
`from=predictions` unique et whitelist `pre_`, rejet des doublons/valeurs
invalides, correspondance avec l'ID de fiche, retour à filtres appliqués et
pagination conservés, false explicite, offsets et six décimales inchangés.
Les tests aller-retour et arrière/avant sont présents ; aucun returnUrl libre
ni filtre Equipment propagé. Les vrais parents restent requis avant l'action
de consultation et avant tout GET historique à destination.

Contrôles de périmètre et d'espaces renouvelés sur les 21 fichiers UI 9.5,
y compris les nouveaux fichiers non suivis ; index vide, aucun ajout effectué.
Les réserves B-PRE-01 à B-PRE-11 sont conservées. Aucun accès PostgreSQL,
API DEV, Docker ou calcul ML lors de cette préparation. Aucun commit, push,
merge ou rebase ; autorisation de commit encore attendue, UI 9.6 non commencée.

## Limites et réserves conservées

L'état vide ne prouve pas la vacuité de toute la table Predictions : observation
limitée au seul équipement P101 et aux filtres visités. Aucune comparaison SQL
exhaustive, aucune requête SQL directe, recette DEV formelle réservée à UI 9.6.
Les quatre types et les détails sont couverts par fixtures de tests ; aucune
prédiction réelle de ces types n'est attestée par cette passe DEV vide.
La pagination non vide et les erreurs HTTP sont prouvées en tests isolés.
L'absence d'historique avant validation est vérifiée par les contrôleurs HTTP,
sans revendiquer une capture exhaustive du trafic réseau du navigateur.
Pas de nouvelle certification lecteur d'écran, zoom 200/400 % ou sécurité SaaS.

| Réserve | Situation après UI 9.5 |
| --- | --- |
| B-PRE-01 | Authentification, autorisation serveur et sécurité multi-tenant toujours absentes ; bloque la production SaaS, ni cascade UI ni identité DEV ne lèvent cette réserve |
| B-PRE-02 | Scores/niveaux backend génériques inchangés ; présentation prudente UI 9.4 conservée |
| B-PRE-03 | Durcissement temporel backend toujours absent ; validation frontend inclusive, offsets et précision préservés |
| B-PRE-04 | Intégrité capteur/mesure backend partielle ; aucun lien descendant ajouté ; chaîne Equipment/Site/Company revalidée |
| B-PRE-05 | JSON générique/volumineux possible ; échappement et limites visuelles 10 000 caractères/six niveaux conservés, aucune limite réseau/backend |
| B-PRE-06 | Cascades de suppression backend inchangées ; aucun DELETE Predictions |
| B-PRE-07 | OFFSET/COUNT distincts, concurrence et index inchangés ; pagination serveur conservée, pas de lecture exhaustive |
| B-PRE-08 | Risques des POST RUL/artefacts inchangés ; aucune mutation, inférence ou génération automatique appelée |
| B-PRE-09 | Aucun mécanisme d'alimentation ajouté ; état vide neutre, aucune déduction de modèle absent |
| B-PRE-10 | Données historiques et provenance potentiellement invalides/incomplètes ; contrat défensif et métadonnées déclarées conservés |
| B-PRE-11 | Aucun GET détail/latest disponible ou ajouté ; liste seule, détails locaux, aucun écran /predictions/:id |

## État Git et autorisation de commit attendue

Branche `feature/frontend-predictions`, HEAD
`da9f0e07ad33b4f3ea65b13f59ce2e72743596e3` inchangés. Index vide, 17 fichiers
suivis modifiés et quatre nouveaux fichiers non suivis. Contrôles de périmètre,
espaces, absence de secrets et d'artefacts de livraison réalisés ;
`git diff --check` et contrôle des nouveaux fichiers conformes. Journaux,
captures et mesures ignorés. Aucun changement backend/API/SQL, package,
migration, seed, Docker ; aucune écriture PostgreSQL ou HTTP métier, aucun
calcul ML. Aucun commit, push, merge ou rebase. UI 9.6 non commencée.

Validation visuelle finale utilisateur reçue le 25 octobre 2026 et bilan
technique confirmé. Aucun commit créé ; attente de l'autorisation explicite
du commit UI 9.5, sans commencer UI 9.6.
