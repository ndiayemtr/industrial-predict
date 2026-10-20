# UI 6.5 - Création d’un capteur industriel

20 octobre 2026. Branche feature/frontend-sensors, HEAD initial e9cdf7f.
Branche, HEAD et dépôt propre vérifiés avant toute modification. Cette étape
implémente uniquement la création ; UI 6.6 n’est pas commencée. Aucun commit,
push ou merge. Aucun changement backend, SQL, migration, Docker ou package.
Aucune écriture PostgreSQL ni accès aux bases réelles.

## Fichiers et conventions

- Les quatre fichiers components/sensor-form/sensor-form.component.* : formulaire
  réactif strictement typé, validations, événements et présentation.
- Les quatre fichiers pages/sensor-create/sensor-create.component.* : page de
  création, cycle d’écriture, navigation, erreurs et tests HttpTestingController.
- pages/sensor-create/sensor-create-references.facade.ts : catalogues paginés et
  validation de la chaîne réelle. Tests intégrés aux scénarios de création.
- Les quatre fichiers pages/sensors-list/sensors-list.component.* : bouton et
  contexte de navigation, tests d’interaction et styles partagés.
- sensors.routes.ts et son test : création lazy avant la route paramétrée.
- Les trois fichiers détail .ts/.html/.spec.ts : confirmation de création.
- frontend/src/styles/_buttons.scss : inscrire .new-sensor dans les trois listes
  des actions harmonisées, avec les mêmes transitions, états et mouvement réduit.
- Le présent rapport. Tous les chemins applicatifs ci-dessus sont relatifs à
  frontend/src/app/features/sensors.

Les modèles et SensorsApiService UI 6.2, la façade de liste, les autres modules
restent inchangés. Le seul ajustement partagé inscrit le nouveau bouton dans les sélecteurs
des actions harmonisées ; les règles existantes elles-mêmes ne sont pas changées. La conception SEN-01 à SEN-10 a été
relue ainsi que Equipment Create, son formulaire et ses références.

SensorFormComponent expose données de références, identifiants vérifiés,
initialisation, états bloqués et événements typés. Cette séparation permet sa
réutilisation future sans implémenter dès maintenant l’édition ou un PATCH.

## Bouton Nouveau capteur

Le PageHeader de la liste reçoit un vrai RouterLink, disponible même sans parent.
SVG + identique à Nouvel équipement, 20x20, stroke currentColor blanc, décoratif,
aria-hidden et non focusable. Libellé « Nouveau capteur », sans tooltip redondant.

La classe utilise exactement actions.navigation-action(primary: true), comme
Nouvel équipement : géométrie, bleu, typographie, espacement, survol et focus.
Aucune copie locale des styles du bouton. Le comportement actif et la transition
sont ceux du stylesheet partagé _buttons.scss, y compris prefers-reduced-motion,
sans ajout d’un effet divergent. Aucun état désactivé
artificiel : la création reste disponible pour permettre la sélection de parents.
Le RouterLink assure une seule navigation, sans handler concurrent.

## Contexte de création et retour

La destination est /sensors/new. Les trois paramètres company_id/site_id/
equipment_id ne sont fournis pour le préremplissage depuis la liste que lorsque
ses trois références sont vérifiées. Le snapshot appliqué de la liste est transmis
séparément par return_company_id, return_site_id, return_equipment_id, return_page,
return_page_size, return_search, return_status. Aucun returnUrl libre.

La page normalise les IDs positifs sûrs, statut exact, recherche trimée de 1 à 100,
page positive et taille 1 à 100. Sans return_* explicite, les paramètres ordinaires
servent aussi au retour, ce qui permet les accès directs.

Contexte complet : lectures unitaires Company, Site, Equipment, contrôle des IDs
reçus, de Site.company_id et Equipment.site_id. Préremplissage seulement après
validation complète, même si les références ne figurent pas dans la première
page des catalogues. Le préremplissage ne modifie pas les textes déjà saisis et
ne constitue pas une modification non enregistrée.

Contexte absent, partiel ou syntaxiquement invalide : aucune sélection de parent,
seul le catalogue entreprises est lu. Une notice explique les paramètres partiels
ou invalides. Un contexte complet contradictoire affiche une erreur, sans remplacer
ses parents par ceux d’une autre chaîne. La sélection manuelle permet de repartir.

Le contexte de retour est un snapshot à l’ouverture ; changer les sélections dans
le formulaire ne le réécrit pas. Les paramètres inconnus et fragments ne sont pas
propagés. Les paramètres de contexte restent des informations UI.

Annuler revient au snapshot initial, avec garde si nécessaire. Après création,
si la chaîne est la même que celle du retour, ce snapshot est conservé sur le
détail. Si elle diffère ou si le retour était incomplet, le détail utilise une
liste cohérente avec le capteur créé, page 1, taille 20, sans recherche ni statut
hérité. Les valeurs de search/status de la liste ne deviennent pas des valeurs
initiales du capteur : son statut initial reste Actif.

## Rattachement industriel et catalogues

Entreprise -> site -> équipement obligatoires, sans premier choix automatique.
Site désactivé jusqu’à vérification de l’entreprise ; équipement désactivé jusqu’à
vérification du site. Les textes métier restent modifiables pendant les lectures.

Chaque choix déclenche la vérification réelle des références sélectionnées.
Changer entreprise vide site/équipement ; changer site vide équipement. Les
switchMap annulent les lectures précédentes et les catalogues devenus hors scope.
La destruction annule les souscriptions. Une réponse obsolète ne restaure pas
l’ancien rattachement.

Les trois catalogues utilisent page_size=50 et des boutons de chargement explicite
de la suite. Filtre company_id pour Sites, site_id pour Equipments. Déduplication
par id ; les pages déjà reçues sont conservées après un échec de page suivante,
avec reprise ciblée pour réseau/5xx. Un catalogue contenant un parent incohérent
est rejeté. Une première page partielle ne prouve jamais l’absence d’une référence.

Seul equipment_id part au POST Sensors. Aucun POST ne passe si la chaîne n’est
pas vérifiée, si les champs de sélection ne correspondent pas aux références
résolues ou si les rattachements sont incohérents.

## Formulaire et payload

Nom/code/type/unité : obligatoires, non blancs et limites respectives 150/100/100/30
caractères Unicode, comptés par points de code avec Array.from. Pas de maxlength
HTML en unités UTF-16. Les espaces périphériques sont retirés lors de la création,
la casse et les caractères internes sont conservés. Aucune conversion de °C,
mm/s ou bar. Type/unité libres, aucun catalogue physique inventé.

Statut : active par défaut, inactive disponible. Libellés français uniquement
à l’affichage. Le statut est administratif, sans promesse d’arrêt d’acquisition.
Code unique dans l’ensemble de l’application, sans précontrôle par lecture de
tous les capteurs ni normalisation de casse.

Payload POST strict : equipment_id, name, code, sensor_type, unit, status et
éventuellement description. Les champs company_id/site_id et de navigation,
identifiant, dates ou champs inconnus ne sont jamais copiés.

Description initiale null en mémoire : tant qu’elle n’est pas touchée, propriété
omise. Saisie puis effacement : chaîne vide explicite. Action Retirer la description :
null explicite. Espaces et sauts de ligne conservés. Aucun retrait implicite ni
limite métier de description inventée.

Formulaire sémantique avec deux fieldsets, legends, labels, aides et erreurs liées
par aria-describedby/aria-invalid ; focus sur le premier champ invalide. Les
boutons utilisent les conventions existantes, actions repliées sur mobile.

## Erreurs, garde et succès

Double soumission bloquée par l’état saving et le formulaire désactivé. Pendant
l’écriture, Annuler et la garde empêchent de quitter la page. beforeunload protège
la fermeture/recharge ; le navigateur décide du texte final de cette alerte.
Les modifications réelles déclenchent une confirmation de sortie ; la baseline
préremplie seule n’en déclenche pas.

409 : conflit générique demandant de vérifier équipement et code global, sans
assimiler tous les conflits à Code. 422 : seuls les loc body/champ connus sont
rattachés aux champs, avec message français sûr ; le texte serveur n’est pas
injecté. 404 : références invalidées et revérification nécessaire avant un autre
POST. Les valeurs saisies restent présentes.

Réseau/5xx : écriture incertaine, aucun retry automatique, soumission bloquée.
Un lien ouvre la liste dans un autre onglet ; un acquittement explicite après
vérification autorise une nouvelle soumission manuelle. Ce mécanisme n’est pas
une garantie d’idempotence et n’affirme pas qu’un capteur n’a pas été créé.

Après 201, l’id doit être positif sûr et equipment_id correspondre au parent
soumis. Sinon la réponse est traitée comme incertaine, sans réémettre un POST.
Succès valide : état success verrouillé, navigation vers la fiche, confirmation
accessible via l’état de navigation createdSensorId et un toast unique. Un
paramètre query homonyme ne peut pas fabriquer cette confirmation.

Si la navigation retourne false ou lève une erreur, la page garde le succès,
les valeurs et un lien de récupération vers l’id créé. La récupération ne fait
que naviguer ; aucun nouveau POST. Une ouverture simultanée est bloquée, et le
toast est émis une seule fois après navigation réussie.

## Validation

Commandes depuis frontend :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.5/vitest.config.mjs --include=src/app/features/sensors/**/*.spec.ts --include=src/app/app.routes.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.5/vitest.config.mjs
npm.cmd run build -- --configuration production
```

Runner temporaire ignoré, maxWorkers=2 comme aux étapes précédentes, sans timeout
augmenté ni exclusion de test. Tests HTTP uniquement simulés. Exécution hors bac
à sable pour les accès temporaires Vitest Windows déjà bloqués aux étapes antérieures.

Premier ciblage : 238 réussis sur 240 ; deux tests soumettaient avant que le
nouvel input blocked ait été propagé après acquittement d’une écriture incertaine.
Ajout du cycle de rendu manquant au test, puis scénarios supplémentaires de
références, annulation et récupération. Ciblage : 249 réussis dans huit fichiers,
compilation 23,737 s, Vitest 19,09 s.

La première suite complète passe avec 1 092 tests dans 56 fichiers (43,63 s).
Le premier build réussit mais signale 14 octets au-dessus du budget de style de
la liste. Les deux inclusions identiques du mixin primaire (Nouveau capteur et
Rechercher) sont regroupées dans une règle commune ; aucun budget relevé.

La recette détecte ensuite la recoloration du lien par Nebular au focus. Le stylesheet
_buttons.scss disposait déjà de tous les états harmonisés mais son sélecteur ne
contenait pas .new-sensor. Cette classe est ajoutée aux trois listes : interactions
générales, actions primaires et mouvement réduit. Aucune règle d’interaction ni
aucun contrat des autres modules n’est modifié.
Les boutons n’ont pas de style primaire recopié localement.

Ciblage final élargi Sensors, routage et liste Equipments : **281 tests réussis
dans neuf fichiers**, compilation 18,483 s et Vitest 13,97 s. Deux libellés de chargement de
catalogues sont également corrigés : d’entreprises et d’équipements.

Suite complète définitive : **1 092 tests réussis dans 56 fichiers**, compilation
14,409 s et Vitest 22,99 s. Référence UI 6.4 : 1 032 tests dans 54 fichiers, soit
60 scénarios supplémentaires et deux nouveaux fichiers de tests. Aucun test
désactivé et aucune augmentation de timeout.

Build production définitif : **réussi en 14,249 s**. Bundle initial **605 008 octets
(605,01 kB)** contre 604 900 octets en UI 6.4, soit **+108 octets** liés aux sélecteurs
globaux. Transfert estimé 153,83 kB. Chunk lazy création 33 505 octets (8,49 kB
estimés transférés), liste 29 660 octets, détail 13 530 octets. Ensemble JS/CSS :
43 fichiers, 956 205 octets, contre 42 fichiers et 920 938 octets, soit +35 267 octets.
La création reste lazy et n’est pas incluse dans le chargement initial.

Seul avertissement final : budget initial warning de 500 kB dépassé de 105,01 kB.
Maximum error initial 1 MB, styles warning 4 kB/error 8 kB inchangés. Le dépassement
de style temporaire a disparu. Aucun budget relevé.

## Recette navigateur et captures

Build production final servi par un script temporaire sur 127.0.0.1:8099,
sans proxy, upstream ou connexion SQL. Les seules créations de recette navigateur
sont des objets synthétiques conservés en mémoire du serveur temporaire. L’audit
recense 70 GET synthétiques et trois POST synthétiques Sensors : une création en
°C, un conflit 409 volontaire avec le code DUPLICATE, puis une création en mm/s.
Les trois payloads ne contiennent que les six champs obligatoires/autorisés,
sans company_id/site_id, contexte de retour, dates ou id.

Sur le build définitif, la comparaison des boutons Sensors/Equipments dans le
même état clavier est identique pour couleur, fond, min-height 44 px, padding
8/16 px, gap 8 px, font-size 15 px, poids 600, interligne 22,5 px, rayon 8 px,
contour de focus et les quatre transitions de 120 ms. Icône et texte restent
blancs au focus. Les pseudo-états hover/active et le mouvement réduit proviennent
exactement des mêmes règles partagées, sans variante Sensors.

Parcours contrôlés : bouton disponible sans sélection ; validation locale avec
focus Site quand l’entreprise seule est sélectionnée ; choix séquentiel des
parents ; préremplissage complet réel après lecture ; statut initial Actif même
avec un retour liste Inactif ; affichage 409 générique conservant les valeurs ;
Annuler restitue page 2, recherche temperature et statut inactive ; création
synthétique 201, détail du nouvel id, unité mm/s et confirmation accessible.

Les dialogues natifs confirm/beforeunload sont vérifiés par les tests unitaires.
Le parcours Annuler navigateur a restitué le contexte mais l’outil n’a pas permis
d’isoler le refus manuel du dialogue natif : ce refus n’est pas revendiqué comme
preuve navigateur. Le texte natif beforeunload dépend du navigateur.

| Largeur cible CSS | innerWidth mesuré | Bouton et formulaire | Actions formulaire |
| --- | --- | --- | --- |
| 1440 | 1440 | Sans débordement global | Ligne |
| 1024 | 1024 | Sans débordement global | Ligne |
| 1023 | 1023 | Navigation repliée, sans débordement | Ligne |
| 768 | 768 | Sans débordement global | Ligne |
| 390 | 391 | Sans débordement global | Colonne |
| 320 | 320 | Sans débordement global | Colonne |

Réserve de mesure : le navigateur intégré applique un zoom 0,75 et exige des
viewports entiers. La cible 390 exacte nécessiterait 292,5 ; le réglage 293 donne
391 mesurés, comme aux étapes précédentes. Les autres cibles sont exactes.
Aucun champ, bouton ou textarea ne dépasse la largeur mesurée. Les captures
complètes montrent les légendes, labels, aides, descriptions et actions. Les
captures en pixels image peuvent être plus grandes que les dimensions CSS.

Captures du formulaire : [1440](../frontend/tmp/ui-6.5/screenshots/sensor-create-1440.jpg),
[1024](../frontend/tmp/ui-6.5/screenshots/sensor-create-1024.jpg),
[1023](../frontend/tmp/ui-6.5/screenshots/sensor-create-1023.jpg),
[768](../frontend/tmp/ui-6.5/screenshots/sensor-create-768.jpg),
[cible 390, 391 mesurés](../frontend/tmp/ui-6.5/screenshots/sensor-create-390.jpg),
[320](../frontend/tmp/ui-6.5/screenshots/sensor-create-320.jpg).

Le bouton possède les six captures correspondantes sensors-new-action-*.jpg,
ainsi qu’une [capture focus](../frontend/tmp/ui-6.5/screenshots/sensors-new-action-focus.jpg).
Également : [conflit](../frontend/tmp/ui-6.5/screenshots/sensor-create-conflict-320.jpg)
et [succès](../frontend/tmp/ui-6.5/screenshots/sensor-create-success-320.jpg).
Les scripts, runner, audit HTTP et mesures JSON sont ignorés dans frontend/tmp/ui-6.5.
Aucun de ces artefacts n’est inclus dans les vingt fichiers livrés.

Serveur temporaire arrêté, onglets créés fermés et viewport réinitialisé. Aucun
warning ni erreur console lors du dernier contrôle. Le contrôle de contenu des
vingt fichiers ne détecte aucun secret ou fichier temporaire. git diff --check
réussi, index vide et HEAD e9cdf7f conservé. Aucun commit/push/merge.

## Limites et réserves

B-SEN-02 et B-SEN-03 restent des réserves backend distinctes : écarts de validation
API/SQL, erreurs d’intégrité non traduites et transactions repository/service.
Le frontend ne corrige ni les contraintes SQL ni les courses d’unicité.

Aucune authentification ou isolation tenant n’est ajoutée ; les contrôles de
références UI n’en constituent pas une garantie. Pas d’ETag, version ni clé
d’idempotence serveur. Les références sont vérifiées à la lecture, sans garantie
d’instantané jusqu’au POST. Les tests isolés et la recette synthétique ne remplacent
pas une recette PostgreSQL, qui n’est pas autorisée ici.

Aucun DELETE, transfert, PATCH d’édition, mesure, compteur, graphique ou prédiction.
UI 6.6 reste hors périmètre. Attendre validation avant tout commit.
