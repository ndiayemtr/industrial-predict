# UI 6.3 - Liste des capteurs

20 octobre 2026. Branche `feature/frontend-sensors`, HEAD de départ
`9efa8fa80f92c92ad395d38e9e39806fdeaa52e7`, dépôt propre avant intervention.
Implémentation autorisée de la liste uniquement, selon SEN-01 à SEN-10.
Aucun commit, push ou merge dans cette étape.

## Fichiers et périmètre

- [app.routes.ts](../frontend/src/app/app.routes.ts) et son test : délégation lazy
  de `/sensors`, remplaçant le placeholder, sans modification des autres destinations.
- [Test Sidebar](../frontend/src/app/layout/sidebar/sidebar.component.spec.ts) :
  remplacement de l’attente du placeholder Sensors par la vraie liste et sa
  sélection attendue ; autres placeholders inchangés.
- [sensors.routes.ts](../frontend/src/app/features/sensors/sensors.routes.ts) et
  [ses tests](../frontend/src/app/features/sensors/sensors.routes.spec.ts) : seule
  route enfant vide, full-match, liste chargée à la demande dans le Shell.
- [sensors-state.model.ts](../frontend/src/app/features/sensors/models/sensors-state.model.ts) :
  contexte UI séparé des paramètres API, états idle/loading/success/empty/error.
- [SensorsListFacade](../frontend/src/app/features/sensors/sensors-list.facade.ts)
  et [ses tests](../frontend/src/app/features/sensors/sensors-list.facade.spec.ts) :
  résolution et vérification du périmètre, pagination, annulation et erreurs.
- [SensorsListComponent](../frontend/src/app/features/sensors/pages/sensors-list/sensors-list.component.ts),
  [template](../frontend/src/app/features/sensors/pages/sensors-list/sensors-list.component.html),
  [styles](../frontend/src/app/features/sensors/pages/sensors-list/sensors-list.component.scss)
  et [tests](../frontend/src/app/features/sensors/pages/sensors-list/sensors-list.component.spec.ts) :
  sélections, catalogues, filtres, URL, tableau et pagination serveur.

SensorsApiService et les modèles UI 6.2 sont réutilisés sans modification.
ReferenceDataApiService fournit les lectures parent. Aucun formulaire Create/Edit,
fiche détail, suppression, transfert, donnée Measurement ou résultat IA ajouté.
Aucun bouton de création fictif. UI 6.4 n’est pas commencée.

## Sélection et validation des références

Sans contexte, seul le catalogue entreprises est chargé. Aucun premier élément
n’est sélectionné, même quand une liste contient une seule option. Le site reste
indisponible jusqu’à validation de l’entreprise ; l’équipement jusqu’à validation
du site et de son entreprise. Les références se lisent par id, sans déduire leur
existence d’une présence ou absence dans une première page de catalogue.

Les trois catalogues utilisent des pages de 50, avec chargement supplémentaire
explicite, déduplication par id et conservation des pages déjà reçues après échec
d’une page suivante. Le retry manuel reprend la page échouée pour réseau/5xx.
Les catalogues de sites et équipements sont vérifiés contre leur parent attendu.
Leur chargement ne présélectionne aucun descendant et ne filtre pas le statut
Equipment. Des références explicites hors première page sont ajoutées aux options
seulement après lecture ciblée et vérification.

Pour un équipement fourni, la façade lit Equipment, son Site puis sa Company.
Les ids retournés et les relations equipment.site_id et site.company_id sont
contrôlés contre les paramètres explicites. Toute contradiction bloque les
capteurs, sans réécriture silencieuse du parent fourni. Les trois références
sont validées avant le GET Sensors. Aucun company_id/site_id n’est envoyé à cet
endpoint : seulement equipment_id, status, search, page et page_size.

Un equipment_id seul en URL est une sélection explicite : ses parents réels sont
résolus et l’URL est complétée. Un site seul résout son entreprise puis attend le
choix d’équipement. Une entreprise seule attend site et équipement. Aucun choix
automatique du premier parent ou enfant n’est effectué.

## Filtres, URL et navigation

Snapshot appliqué dans l’URL : company_id, site_id, equipment_id, status, search,
page et page_size. Les paramètres inconnus et le fragment existants sont conservés
dans l’URL, sans fuite vers l’API. La comparaison du snapshot évite de recharger
pour un simple paramètre étranger ou la complétion d’un contexte déjà résolu.

- Recherche sur nom/code/type/unité uniquement après Entrée ou bouton Rechercher ;
  trim aux extrémités, vide omise, maximum 100. Le brouillon n’est pas appliqué à
  chaque frappe et n’est pas réutilisé lors d’un changement de statut ou de taille.
- Statuts Tous/Actif/Inactif, transport absent/active/inactive. Pagination serveur,
  choix 20/50/100, conservation d’une taille d’URL valide de 1 à 100. Aucun tri
  client, fusion de pages de capteurs ou agrégat multi-équipements.
- Changement d’entreprise : effacement du site, de l’équipement et de la recherche.
  Changement de site : effacement équipement/recherche. Changement d’équipement :
  effacement recherche. Statut et taille conservés, retour page 1. Recherche,
  statut ou taille modifiés : retour page 1.
- Identifiant de périmètre invalide en URL : notice et blocage, aucune liste
  globale ou sélection implicite. Pagination, recherche et enum invalides sont
  normalisés avant chargement, avec notice. Une contradiction entre parents est
  une erreur de périmètre, pas une invitation à charger un périmètre élargi.

Le nom prépare l’URL `/sensors/{id}` avec les sept paramètres de contexte via
detailUrl et data-detail-url. Le rendu reste non interactif : élément role=link,
aria-disabled=true, sans href ni tab stop, accompagné d’une indication « consultation
détaillée prochainement ». Aucun clic vers une 404 ni route de détail provisoire.
L’activation de ce lien appartient à UI 6.4. Les URLs `/sensors/{id}` et `/sensors/new`
restent hors du module livré et sont prises en charge par la 404 globale.

## États et annulation

Sélection attendue, chargement de chaque catalogue, parent sans descendant,
chargement des capteurs, équipement sans capteur, résultat filtré vide, page hors
plage avec total positif et erreur sont distingués. Aucun faux compteur zéro
avant succès. Le tableau affiche Nom, Code, Type, Unité et Statut en français.
Le rattachement est affiché au-dessus, sans GET parent par ligne.

Page hors plage : proposition de retour manuel à une page disponible, sans boucle
automatique. Total=0 : pas de pagination. Réseau/5xx : relance manuelle possible ;
401/403 : accès refusé ; 404 parent : référence absente ; 422 : paramètres à vérifier.
Aucun retry automatique et aucune écriture HTTP depuis la liste.

Les flux switchMap et takeUntilDestroyed annulent les lectures obsolètes : parents,
capteurs, catalogues et pages supplémentaires. Changer de périmètre retire les
résultats précédents. Une réponse Sensor d’un autre équipement ou un catalogue de
descendants incohérent est rejeté. Les changements rapides ne restaurent pas une
ancienne sélection et ne relancent pas une requête globale.

## Interface et accessibilité

PageHeader, LoadingState, EmptyState et ErrorState partagés ; composants standalone
OnPush, formulaires réactifs et signaux selon Equipments. Boutons utilisant le
mixin partagé et l’harmonisation globale, statut textuel, aides de sélection liées
par aria-describedby, champs étiquetés, erreur de recherche et états annoncés.
Les filtres restent stables pendant l’actualisation des résultats.

Le tableau est contenu dans une région défilable au clavier avec caption et
entêtes scope=col. Les parents sont en trois colonnes à partir de 768 px, empilés
en dessous ; les actions et la pagination se replient sur petit écran. Le Shell
conserve sa frontière desktop à 1024 px. Aucun budget n’est augmenté.

## Validation et preuves

HTTP Angular intégralement simulé par HttpTestingController. Aucun appel backend
réel ni accès PostgreSQL ; aucun changement SQL, Docker, migration ou package. Les captures
navigateur utilisent une prévisualisation isolée de données synthétiques, GET-only,
sans upstream vers une base ou une API réelle.

Commandes depuis frontend :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.3/vitest.config.mjs --include=src/app/features/sensors/**/*.spec.ts --include=src/app/app.routes.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.3/vitest.config.mjs
npm.cmd run build -- --configuration production
```

Le runner temporaire ignoré par Git limite Vitest à deux workers, sans augmentation
de délai ni exclusion. Premier essai ciblé : une fixture ajoutait un identifiant
invalide en doublon du paramètre valide, puis un échec de vérification HTTP a
contaminé le TestBed partagé. Fixture corrigée, nettoyage des nouvelles suites
assuré en finally, sans masquer une requête restante. Les 130 tests suivants
passent ; les trois tests de route ajoutés portent le ciblage final à **133 tests
réussis dans cinq fichiers**, durée Vitest 9,27 s, compilation 15,137 s.

Suite complète finale : **977 tests réussis dans 53 fichiers**, durée Vitest
34,12 s, compilation 22,653 s. Référence UI 6.2 : 929 tests dans 50 fichiers,
soit **48 tests ajoutés** et trois nouveaux fichiers de tests. Aucun test exclu,
aucun timeout augmenté. La première suite complète verte à 976 tests précédait
l’ajout du cas de reprise après erreur ; elle n’est pas le résultat final.

Build production final réussi, compilation 17,637 s. Bundle initial :
**604 900 octets**, contre 604 809 en UI 6.2, soit **+91 octets**. Nouveau chunk
lazy de liste Sensors : **30 096 octets**. Ensemble des actifs JS/CSS :
**40 fichiers, 907 241 octets**, contre 38 fichiers et 876 814 octets, soit
**+30 427 octets**. Le budget d’avertissement initial reste à 500 ko, avec un
dépassement de 104,90 ko ; seuil d’erreur 1 Mo et budgets de styles inchangés.
Aucun autre avertissement relevé dans ce build. Aucun seuil augmenté.

La première suite complète donne 975 réussis et un échec sur 976 tests : le test
Sidebar préexistant attendait encore le placeholder `/sensors`. Son attente est
remplacée par une vérification de la vraie liste et de la destination active,
sans retirer la couverture ni modifier les autres fonctionnalités.

Le contrôle de reprise après erreur a conduit à conserver les parents déjà
vérifiés lorsque seul le GET Sensors échoue, afin de pouvoir corriger la recherche.
Un échec de vérification d’un parent efface toujours les références non validées.
Un test spécifique vérifie la correction de recherche après un HTTP 500.
La notice de périmètre invalide disparaît lors d’une nouvelle sélection explicite,
avec test de reprise pour chacun des trois identifiants d’URL invalides.

Après cette correction fonctionnelle, le ciblage Sensors/routing/Sidebar donne
**146 tests réussis dans six fichiers**, durée 18,08 s, compilation 26,477 s.
Un essai précédent s’est arrêté sur « Worker exited unexpectedly », sans bilan
de tests exploitable ; la relance utilise les mêmes deux workers et les mêmes
délais. Dernier contrôle de la page après correction des notices : **20 tests
réussis**, durée 7,43 s, compilation 18,449 s. Aucun test désactivé.

### Contrôle navigateur et captures

Prévisualisation sur 127.0.0.1:8099, limitée aux GET et données synthétiques,
sans proxy ni upstream. Sélection manuelle entreprise/site/équipement vérifiée :
aucun capteur avant le troisième choix. Recherche tapée non appliquée, puis
recherche mm/s combinée à Inactif : quatre résultats cohérents ; pagination
page 2 avec SEN-021 en première ligne ; page 99 vide et récupération manuelle
vers page 3 (trois lignes) ; résultat vide et erreur HTTP 500 synthétique vérifiés.
Région tableau focalisable : défilement horizontal effectif par flèche droite,
sans débordement du document. Le journal d’audit ne contient que des GET et des
requêtes Sensors avec équipement valide, sans company_id/site_id.

Après le dernier build, la reprise depuis HTTP-500 vers mm/s est vérifiée dans
le navigateur : bouton Rechercher actif, trois parents conservés et 14 capteurs
portant tous l’unité mm/s. Audit final : 75 GET, dont 14 lectures Sensors ; aucune
écriture ni fuite company_id/site_id vers Sensors. La prévisualisation est arrêtée
après validation, et les onglets temporaires sont fermés.

Le navigateur de contrôle a un facteur d’échelle 0,75. Les réglages de viewport
ont été calibrés et les dimensions CSS mesurées via innerWidth, plutôt que de
déduire la largeur CSS du JPEG. La cible 390 px est arrondie à 391 px CSS par
l’outil ; **390 px exacts restent une réserve de cette recette visuelle**.
Les cinq autres dimensions sont exactes. Le viewport temporaire est restauré.

| Cible | Largeur CSS mesurée | Shell | Tableau défilable horizontalement | Capture |
| --- | --- | --- | --- | --- |
| 1440 | 1440 | Desktop | Non nécessaire | [1440](../frontend/tmp/ui-6.3/screenshots/list-1440.jpg) |
| 1024 | 1024 | Desktop | Non nécessaire | [1024](../frontend/tmp/ui-6.3/screenshots/list-1024.jpg) |
| 1023 | 1023 | Mobile | Non nécessaire | [1023](../frontend/tmp/ui-6.3/screenshots/list-1023.jpg) |
| 768 | 768 | Mobile | Non nécessaire | [768](../frontend/tmp/ui-6.3/screenshots/list-768.jpg) |
| 390 | 391 | Mobile | Oui, 608 px dans 321 px | [390 calibrée](../frontend/tmp/ui-6.3/screenshots/list-390.jpg) |
| 320 | 320 | Mobile | Oui, 608 px dans 250 px | [320](../frontend/tmp/ui-6.3/screenshots/list-320.jpg) |

Dans les six observations, scrollWidth du document égale clientWidth ; les
sélecteurs restent dans le viewport. À 1024 le Shell est desktop, à 1023 il est
mobile. Les trois parents restent côte à côte à 768, puis sont empilés sur mobile
étroit. Les captures ont été examinées visuellement.

Autres preuves locales : [sélection attendue](../frontend/tmp/ui-6.3/screenshots/selection-1440.jpg),
[filtre mobile](../frontend/tmp/ui-6.3/screenshots/filtered-320.jpg),
[page hors plage](../frontend/tmp/ui-6.3/screenshots/out-of-range-1440.jpg),
[vide](../frontend/tmp/ui-6.3/screenshots/empty-1440.jpg),
[erreur](../frontend/tmp/ui-6.3/screenshots/error-1440.jpg).
[Reprise après erreur](../frontend/tmp/ui-6.3/screenshots/recovery-1440.jpg).
Mesures et trace HTTP : frontend/tmp/ui-6.3/responsive.json et
browser-http-audit.json. Ces captures, le runner et le serveur de prévisualisation
sont ignorés par Git et ne sont pas des fichiers à committer ; leurs liens sont
locaux au poste de validation. Aucune capture de données réelles.

## Réserves et point d’arrêt

Les catalogues et les capteurs sont des lectures séparées ; une suppression ou
réaffectation concurrente backend peut invalider une référence entre deux lectures.
Aucune transaction de snapshot ou protection tenant n’est promise par le frontend.
B-SEN-02/03 restent inchangés. Les valeurs de statut historiques hors enum peuvent
encore provoquer une erreur de réponse backend.

Les tests et captures synthétiques ne constituent pas une recette PostgreSQL.
Un lecteur d’écran réel, le zoom exhaustif et les conditions de charge serveur ne
sont pas validés ici. Aucun écran Create/Edit/Detail ou lien Measurements activé.

Validation utilisateur attendue avant commit et avant tout début UI 6.4.
