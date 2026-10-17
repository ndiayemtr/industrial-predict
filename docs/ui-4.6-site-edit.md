# UI 4.6 - Modification d'un site industriel

Suivi : UI 4.6 validée par l’utilisateur et enregistrée dans la série de commits avant UI 4.7.4. Les résultats et états Git ci-dessous décrivent l’intervention initiale.

Date : 17 octobre 2026. Branche `feature/frontend-sites`, HEAD de référence
`e8702b0`, dépôt propre avant intervention. Implémentation terminée, en attente
de validation. Aucun commit, push ou merge. UI 4.7 non commencée.

## Contrats et périmètre

La [conception UI 4.1](etape-ui-4.1-sites.md), les bilans
[UI 4.2](ui-4.2-sites-data-access.md), [UI 4.3](ui-4.3-sites-list.md),
[UI 4.4](ui-4.4-site-detail.md), [UI 4.5](ui-4.5-site-create.md),
l'[architecture frontend](frontend-architecture.md) et les règles visuelles
servent de référence. Le formulaire Companies a été examiné sans être modifié.

Relecture directe des [schémas](../backend/app/schemas/site.py), du
[modèle SQL](../backend/app/models/site.py), des
[routes](../backend/app/api/routes/sites.py) et du
[service Site](../backend/app/services/site_service.py) :

- GET `/api/v1/sites/{id}` retourne SiteRead ou 404 ; la référence utilise
  GET `/api/v1/companies/{company_id}` avec le parent réel du SiteRead.
- PATCH `/api/v1/sites/{id}` applique les seuls champs fournis, via
  exclude_unset. Description omise, chaîne vide et null sont distincts.
- SQL impose name/code NOT NULL, avec limites 150/50 caractères. Le code est
  unique globalement, sans promesse d'unicité insensible à la casse.
- Le backend accepte techniquement company_id dans PATCH. Le DTO MVP et la
  whitelist existante de SitesApiService.update l'excluent et sont inchangés.
- 409 ne possède pas de code métier structuré fiable permettant d'en attribuer
  systématiquement la cause au code Site. Les courses d'intégrité SQL peuvent
  aussi produire une erreur serveur. Aucun correctif backend n'est introduit.

La route différée `:siteId/edit`, gardée par canDeactivate, précède `:siteId`.
`new` reste prioritaire. Un lien Modifier apparaît sur une fiche chargée,
avec le traitement visuel primaire de Companies, sans import de ses styles
internes. Aucun transfert d'entreprise ni DELETE.

## Formulaire, valeurs et états

SiteFormComponent est partagé entre création et édition. En édition, il reçoit
le SiteRead initial ; nom/code/description sont préremplis sans conversion.
L'entreprise est une définition en lecture seule, utilisant le formateur métier
partagé (sans répéter nom et code identiques). Aucun sélecteur ni identifiant
technique visible. Le contrôle company_id réutilisé pour la création est désactivé
en édition et ignoré dans les différences et le PATCH.

Les différences comparent les valeurs brutes aux valeurs initiales, et non le
seul drapeau dirty. Une valeur revenue à l'origine n'est plus une modification.
Le corps est recalculé depuis le formulaire avant l'appel au service ; aucune
propriété supplémentaire du signal de soumission n'est acceptée.

| Cas | Comportement PATCH |
| --- | --- |
| Aucun changement | Aucun appel ; notice accessible, aucun toast |
| Nom ou code modifié | Seulement le champ modifié, espaces et casse conservés |
| Nom ou code inchangé | Omis, même si sa valeur source contient des espaces |
| Description inchangée, y compris absente/null/vide | Omise |
| Description effacée manuellement | Chaîne vide explicite |
| Bouton Retirer la description | Null explicite ; bouton masqué et focus rendu au textarea |
| Entreprise, identifiant ou dates | Jamais dans PATCH |

Nom/code restent obligatoires et non blancs. Les limites sont comptées en points
de code Unicode, espaces compris en édition puisqu'ils sont préservés. La
création conserve son trim existant et son POST. Aucun maximum inventé pour
description. Le premier champ invalide reçoit le focus ; les erreurs sont
associées par aria-describedby/aria-invalid.

La page porte ses états loading, load-error, idle, saving, success et error.
Les flux paramMap/switchMap annulent les lectures Site et entreprise obsolètes.
Un changement d'identifiant réinitialise les données et les erreurs. Les
souscriptions sont nettoyées à la destruction ; une écriture ne peut pas être
soumise en double ni autoriser une sortie pendant saving.

Une référence entreprise indisponible reste explicite, sans nom inventé ni
solution de transfert. L'enregistrement et les champs sont bloqués jusqu'à sa
vérification. La relance manuelle réseau/5xx reste accessible hors du fieldset
désactivé ; elle ne recharge pas le Site et ne réinitialise pas les saisies.
Une 404 référence ne propose pas de relance automatique.

Les dates sont affichées dans Informations de suivi, entre les champs et les
actions, hors FormGroup. Le formateur partagé conserve les composantes sans
fuseau, convertit les offsets explicites en UTC et masque les fractions seulement
à l'affichage. Absence ou valeur invalide : Non disponible. Aucun contrôle
modifiable ni date envoyée au serveur.

## Navigation, erreurs et confirmation

company_id/page/page_size/search du contexte sont validés et conservés vers
l'édition, le détail après succès et le détail après annulation. Sans contexte,
le parent réel du site alimente le retour. Le contexte n'impose jamais le parent
de la requête métier. Aucun returnUrl externe.

Après succès PATCH, navigation vers le détail puis un toast unique
« Site modifié avec succès. ». L'état updatedSiteId fournit aussi une confirmation
persistante role=status dans le détail. Navigation refusée ou rejetée : conserver
un lien et une confirmation sur le formulaire, bloquer un second PATCH, sans
toast tant que la navigation n'a pas réussi.

404 Site : erreur explicite, sans formulaire vide ni recréation. 409 : conflit
générique sans désigner un champ. 422 : résumé et erreurs des seuls champs
éditables reconnus, avec focus. Réseau/5xx après écriture : résultat incertain,
saisie conservée, vérification de la fiche dans un nouvel onglet et acquittement
explicite avant nouvelle soumission ; aucune relance automatique.

CanDeactivate et beforeunload protègent les modifications non enregistrées.
Ces mécanismes ne constituent ni verrou serveur, ni annulation garantie d'une
transaction déjà reçue. Aucun contrôle de version/ETag disponible n'est ajouté.
L'absence d'autorisation multi-entreprises backend demeure une limite de sécurité.
Le module n'est pas déclaré prêt pour une production SaaS multi-tenant.

## Tests et validations de cette étape

Validations exécutées séquentiellement, sans build concurrent :

| Commande, depuis frontend sauf Git | Résultat final |
| --- | --- |
| `node node_modules/@angular/cli/bin/ng.js test --watch=false` | 577 tests réussis, 42 fichiers ; départ 10:56:41 UTC, durée 17,81 s |
| `node node_modules/@angular/cli/bin/ng.js build --configuration production --output-path tmp/ui-4.6/production` | Réussi à 10:57:24 UTC, durée 11,948 s ; warning initial existant |
| `node --test scripts/apply-nebular-sass-fix.test.mjs` | 5 réussites, aucun échec |
| `node scripts/verify-nebular-breakpoints.mjs` | Dart Sass 1.97.3, quatre expressions, huit breakpoints, media queries et thème unique vérifiés |
| `npm ls --all` | Code 0, arbre valide |
| `npm audit --json` | Code 0, zéro vulnérabilité signalée |
| `git diff --check` | Réussi |

32 nouveaux contrôles couvrent édition et intégration Shell : GET/préremplissage,
parent réel/indisponible/incohérent, absence de sélecteur, dates hors contrôles et
ordre DOM, PATCH différentiel/exact, champs restaurés, Unicode/espaces, description
omise/vide/null, retrait au clavier, doubles soumissions, abandon/unload,
navigation/contexte/toast/confirmation, échecs de navigation, erreurs
404/409/422/réseau/serveur, identifiants invalides et lectures obsolètes.
Les suites Companies, création Sites, Dashboard, routing et 404 restent valides.
Les assertions historiques du détail/routing sont adaptées à la nouvelle action,
sans supprimer les contrôles fonctionnels. Les suites de développement ont
également réussi ; seuls les résultats finaux ci-dessus décrivent la livraison.

## Bundles

Comparaison aux artefacts locaux UI 4.5.2 conservés, sans reconstruire la base :

| Mesure brute | UI 4.5.2 | UI 4.6 | Écart |
| --- | ---: | ---: | ---: |
| Initial | 601 509 octets | 601 509 octets | 0 |
| Liste Sites différée | 17 840 octets | 17 840 octets | 0 |
| Détail Site différé | 8 359 octets | 9 239 octets | +880 |
| Page création Site | 21 009 octets, formulaire inclus | 12 882 octets | Découpage différent |
| Formulaire Sites partagé | Inclus dans création | 10 457 octets | Différé, partagé création/édition |
| Page édition Site | Absente | 12 291 octets | +12 291 |
| Ensemble JS/CSS | 770 204 octets | 785 921 octets | +15 717 |

La baisse du chunk création ne représente pas une réduction équivalente du coût
de sa route : son formulaire est extrait dans un chunk partagé. Page et formulaire
ensemble : 23 339 octets, soit +2 330 par rapport à UI 4.5.2. Page édition et
formulaire : 22 748 octets, hors autres dépendances partagées. Estimations de
transfert : édition 4,08 ko, formulaire 3,27 ko. Dashboard reste à 52,70 ko.
Initial : 601,51 ko pour un budget de 500 ko, dépassement inchangé de 101,51 ko.
Aucun budget relevé ni dépendance ajoutée.

## Contrôle visuel et limites

Build production servi localement avec une API entièrement simulée. Largeurs
1440, 1024, 1023, 768, 390 et 320 px : aucun débordement horizontal ; entreprise
en lecture seule, labels, descriptions longues, suivi puis actions accessibles.
Sidebar Sites active et focus main conservés ; Tab atteint le Code avec focus
visible. Soumission vide : focus Nom. Parcours depuis Modifier, soumission
inchangée, conflit conservant la saisie puis succès et retour au contexte vérifiés.
Une entreprise introuvable conserve un état explicite et bloque l'enregistrement.

Le journal navigateur contient deux PATCH simulés en mémoire : un 409 avec
nom/code, puis un succès avec seulement le nom (espaces conservés). Aucun POST
ni DELETE dans ce parcours, aucune connexion FastAPI réelle, aucune écriture
PostgreSQL. Les tests HTTP utilisent HttpTestingController.

Captures dans le dossier de visualisation de cette tâche :

- `ui-4.6-site-edit-1440.jpg` et `ui-4.6-site-edit-1440-actions.jpg`.
- `ui-4.6-site-edit-320-top.jpg` et `ui-4.6-site-edit-320-actions.jpg`.
- `ui-4.6-site-edit-{1024,1023,768,390}.jpg` et `ui-4.6-site-updated-1440.jpg`.

La capture pleine page échoue dans l'outil : les vues de haut et de bas sont
fournies séparément. Les zones de suivi/actions ont été inspectées par capture
documentaire ciblée. Le retrait par Entrée et le retour du focus au textarea sont
également vérifiés au navigateur. La confirmation native d'abandon est couverte
par tests ; la tentative de contrôle manuel via l'outil navigateur n'a pas été
concluante et n'est pas comptée comme validation indépendante.
Lecteur d'écran réel, zoom 200/400 %, mobile physique et
écritures de bout en bout restent non validés. Pas de benchmark de latence réelle.

## Fichiers et Git

Créés sous `frontend/src/app/features/sites/pages/site-edit/` :
`site-edit.component.{ts,html,scss,spec.ts}` ; plus ce rapport.

Modifiés sous `frontend/src/app/features/sites/` :

- `components/site-form/site-form.component.{ts,html,scss}`.
- `pages/site-detail/site-detail.component.{ts,html,scss,spec.ts}`.
- `sites.routes.{ts,spec.ts}`.

Suivi documentaire : README_AI.md, project-status.md, roadmap.md et note de
livraison historique UI 4.5. Aucun changement Companies/Dashboard, backend,
PostgreSQL, DTO/service HTTP, dépendance ou budget.

État final : branche `feature/frontend-sites`, HEAD `e8702b0`, index vide.
13 fichiers suivis modifiés et 5 nouveaux fichiers ; aucun commit, push ou merge.
Journaux, build et serveur simulé sous `frontend/tmp/ui-4.6/`, ignoré par Git.
Serveur temporaire arrêté et viewport restauré après les contrôles.
Validation utilisateur attendue avant commit et avant toute étape suivante.
