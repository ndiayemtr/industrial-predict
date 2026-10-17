# UI 4.5 - Création d'un site industriel

Suivi : UI 4.5 et ses finitions sont commitées dans `e8702b0`. Les états et
résultats ci-dessous sont historiques. La modification fait l'objet du
[rapport UI 4.6](ui-4.6-site-edit.md).

Date : 17 octobre 2026. Branche `feature/frontend-sites`, HEAD `491cb24`.
Dépôt propre au départ. Implémentation terminée, en attente de validation.
Aucun commit, push ou merge. UI 4.6 non commencée.

## Contrats vérifiés

Relecture de la [conception UI 4.1](etape-ui-4.1-sites.md), des bilans
[UI 4.2](ui-4.2-sites-data-access.md), [UI 4.3](ui-4.3-sites-list.md),
[UI 4.4](ui-4.4-site-detail.md), de l'[architecture frontend](frontend-architecture.md)
et des [règles visuelles](ui-design.md). Le formulaire Companies, ses tests,
guards, notifications et protections d'abandon servent de référence, sans
importer ses composants ou styles internes dans Sites.

Les [schémas Pydantic Site](../backend/app/schemas/site.py), le
[modèle SQL](../backend/app/models/site.py), le
[service](../backend/app/services/site_service.py) et les
[routes](../backend/app/api/routes/sites.py) confirment :

- POST `/api/v1/sites`, succès 201 avec SiteRead. SiteCreate impose name, code,
  company_id ; description est facultative, chaîne ou null, avec défaut null.
- SQL limite name à 150 caractères et code à 50, NOT NULL. L'index unique de
  code est global, toutes entreprises confondues. Aucune promesse supplémentaire
  d'unicité insensible à la casse ; aucune recherche préalable de doublon.
- Aucun maximum métier explicite pour description dans ce contrat TEXT.
- Pydantic ne garantit pas ces longueurs ou un texte non blanc : la validation
  frontend évite les entrées incompatibles, sans prétendre durcir le backend.
- Le service vérifie l'existence de Company puis le code. Plusieurs ValueError
  deviennent des 409 textuels sans code métier structuré. Un conflit ne permet
  donc pas d'accuser systématiquement Code. Les courses SQL ne sont pas toutes
  traduites en erreur métier ; aucun correctif backend n'est introduit.

SitesApiService.create et les DTO restent inchangés. Les identifiants restent
numériques dans le transport et les routes, sans être affichés dans les libellés.
Le filtrage et le contrôle d'existence du parent ne sont pas une autorisation
multi-entreprises. Aucune préparation à une production SaaS multi-tenant n'est
revendiquée.

## Formulaire et références entreprises

La route différée statique `/sites/new` précède `:siteId`, avec titre et Sidebar
Sites existants. La liste fournit un lien Nouveau site avec son contexte URL.
Aucune route d'édition ni action de suppression ou transfert n'est ajoutée.

SiteFormComponent est un composant de présentation propre à Sites. Son FormGroup
contient seulement company_id, name, code et description. Il n'inclut aucune date
ou donnée de suivi. SiteCreateComponent orchestre les références, l'écriture,
les messages et la navigation dans des états locaux, sans store global ni CRUD
générique anticipant UI 4.6.

- Entreprise obligatoire, sans sélection automatique. Un company_id positif sûr
  fourni à l'ouverture préremplit le contrôle mais doit réussir un GET individuel
  par ReferenceDataApiService.getCompanyById avant tout POST. Une réponse portant
  un autre identifiant est rejetée. Une valeur de contexte invalide est ignorée
  avec une indication, sans GET individuel invalide.
- Le catalogue est paginé par 50 via getCompanies. Les pages suivantes se
  chargent explicitement, avec déduplication ; une page échouée conserve les
  références antérieures et propose une relance manuelle réseau/serveur.
- Une entreprise hors première page est résolue directement puis ajoutée aux
  options, sans parcourir tout le catalogue. Nom/code utilisent le formateur
  métier partagé et ne se répètent pas s'ils sont identiques.
- Chaque changement explicite de sélection vérifie la nouvelle entreprise.
  switchMap annule les références obsolètes ; DestroyRef nettoie les lectures.
  L'erreur du catalogue reste distincte de l'erreur de l'entreprise sélectionnée.
  Un GET individuel réussi reste utilisable si le catalogue échoue séparément.
- Les options temporaires sont explicitement Vérification de l'entreprise ou
  Entreprise indisponible, jamais un identifiant ou un nom inventé.
- Nom/code : texte non blanc requis, espaces périphériques retirés avant POST,
  casse conservée. Les limites comptent les points de code Unicode comme SQL,
  sans maxlength natif qui compterait les unités UTF-16 différemment.
- Description non saisie : propriété omise. Une saisie explicitement effacée
  reste une chaîne vide. Le bouton Retirer la description produit null explicite.
  Le texte non vide, ses espaces, sauts de ligne et caractères Unicode restent
  intacts ; aucune limite artificielle ni trim de description.

Le contexte initial est capturé à l'ouverture, pour ne pas réinitialiser une
saisie lors des changements d'état. Retour et succès conservent page/page_size/
search si l'entreprise reste celle du contexte. Un changement d'entreprise
réinitialise la page à 1 et retire l'ancienne recherche. Les paramètres externes
de redirection ne sont pas repris ; page_size est borné de 1 à 100.

## Soumission, erreurs et navigation

Un verrou saving empêche les doubles POST et désactive les contrôles. Le corps
est reconstruit avec les quatre propriétés autorisées seulement ; les clés
supplémentaires d'une variable structurellement compatible sont exclues.
L'entreprise doit correspondre à la référence vérifiée. Aucun PATCH ou DELETE.

CanDeactivate et beforeunload protègent les valeurs réellement modifiées.
Une navigation pendant saving est refusée ; les autres abandons demandent
confirmation. Une sélection initiale préremplie sans autre modification ne
constitue pas à elle seule une saisie à abandonner.

Après 201, la page ouvre `/sites/{id retourné}` avec le contexte utile et un
état Router createdSiteId. Seulement après résolution positive de la navigation,
NbToastrService émet une confirmation unique. Le détail affiche indépendamment
un texte role=status, y compris pendant sa lecture initiale ; la confirmation
ne se propage pas à un autre site. Aucun identifiant n'est affiché.

Si la navigation est annulée, aucun toast n'est émis. Le formulaire indique le
succès et propose un lien vers la fiche ; un nouveau POST reste bloqué. Une
erreur de navigation conserve également ce lien, sans nouvelle écriture.

Erreurs traitées sans effacer les contrôles :

- 404 d'écriture : entreprise potentiellement devenue indisponible ; référence
  invalidée jusqu'à vérification explicite. Le POST réel décrit renvoie plutôt
  409 pour une entreprise absente ; 404 est également géré défensivement.
- 409 : conflit générique. Ni parsing d'un detail textuel, ni erreur Code
  fabriquée. Une action permet de revérifier explicitement l'entreprise.
- 422 : seules les erreurs body de company_id/name/code/description sont
  associées aux champs connus, avec messages frontend ; résumé générique pour
  les autres contraintes, sans rendu HTML ou message brut du serveur.
- Réseau/5xx : issue d'écriture incertaine. Aucun retry automatique. Le site
  peut avoir été créé ; lien vers la liste dans un nouvel onglet et acquittement
  explicite de vérification requis avant une nouvelle soumission.

Aucun toast de succès lors d'un échec ou d'un abandon. La protection contre les
doublons frontend ne remplace pas une clé d'idempotence backend ; aucune garantie
de résultat d'une écriture interrompue n'est inventée.

## Accessibilité et contrôles visuels

Un seul h1, legend et labels explicites, champs requis, aides/erreurs reliées
par aria-describedby et aria-invalid, états loading/status/alert accessibles.
Le premier champ invalide reçoit le focus, y compris pour les champs identifiés
par un 422. Le focus et les titres du Shell existants sont conservés.

Build production vérifié dans le navigateur avec une API simulée locale :
1440, 1024, 1023, 768, 390 et 320 px. Aucun débordement horizontal global.
Les champs conservent leur contenu au redimensionnement et au chargement des
références. Contrôle clavier : bouton de pagination des entreprises atteint par
Tab avec focus visible, validation et soumission par Entrée. Les limites native
du select sur un long libellé à faible largeur ne changent pas sa valeur ou son
nom accessible ; son popup garde le libellé complet.

Parcours navigateur simulés : entreprise 7 connue, pages 50/52 puis 52/52,
nom vide et focus, POST 409 conservant les champs, vérification du parent,
POST 201 et retour au contexte, préremplissage entreprise 99 absente de la
première page, second POST 201, un toast visible après navigation et confirmation
accessible sur le détail ; entreprise 777 introuvable. Le journal de prévisualisation
contient trois POST simulés : un conflit et deux succès en mémoire, aucun
PATCH/DELETE. Aucune connexion FastAPI réelle, aucune écriture PostgreSQL.

Captures dans le dossier de visualisation de cette tâche :

- `ui-4.5-site-create-{1440,1024,1023,768,390,320}.jpg`.
- `ui-4.5-site-conflict-320.jpg`, `ui-4.5-site-create-parent-outside-320.jpg`.
- `ui-4.5-site-created-320.jpg`, `ui-4.5-site-created-toast-320.jpg`.
- `ui-4.5-site-parent-unavailable-320.jpg`.

Les captures finales 1440/320 montrent le formulaire avant saisie avec entreprise
explicite. Les autres largeurs ont aussi été contrôlées avec les champs remplis.
Console sans erreur ni avertissement sur le dernier parcours contrôlé.
Serveur temporaire arrêté, viewport restauré. Lecteur d'écran réel, zoom réel
200/400 %, mobile physique et POST de bout en bout ne sont pas revendiqués.

## Tests et validations techniques

Commandes exécutées depuis frontend, séquentiellement, sans build concurrent :

| Validation finale | Résultat |
| --- | --- |
| `node node_modules/@angular/cli/bin/ng.js test --watch=false` | 542 tests réussis, 41 fichiers ; départ 09:20:31 UTC, durée 23,73 s |
| `node node_modules/@angular/cli/bin/ng.js build --configuration production --output-path tmp/ui-4.5/production` | Réussi à 09:21:22 UTC, durée 16,872 s ; avertissement de budget conservé |
| `node --test scripts/apply-nebular-sass-fix.test.mjs` | 5 tests réussis, 0 échec |
| `node scripts/verify-nebular-breakpoints.mjs` | Dart Sass 1.97.3 ; quatre expressions, huit breakpoints, media queries et thème unique vérifiés |
| `npm ls --all` | Code de sortie 0, arbre valide |
| `npm audit --json` | Code de sortie 0, zéro vulnérabilité, toutes sévérités |
| `git diff --check` | Réussi |

Premier passage de développement : 540 réussites et un échec de test, dû à la
soumission avant propagation de l'input blocked après acquittement. Le test a
été corrigé avec la détection Angular et whenStable déjà utilisées par ses
helpers, sans délai, skip ou retry. Un scénario de revérification après 409 a
également été ajouté avant la suite finale ci-dessus. Les résultats antérieurs
ne sont pas attribués à une nouvelle exécution.

Les 38 tests ajoutés par rapport aux 504 de la référence précédente couvrent
route statique, Shell/Sidebar/titres/focus, contexte valide/invalide, parent hors
première page, pagination/déduplication/erreurs, références obsolètes, Unicode et
limites SQL, description omise/vide/null/longue, POST exact et whitelist,
double soumission, ordre navigation/toast, navigation annulée, confirmation
accessible, erreurs 404/409/422/réseau/serveur, issue incertaine, abandon,
beforeunload, nettoyage et absence de PATCH/DELETE. Les suites existantes
Companies, Sites, Dashboard, dates, routing et 404 restent valides.

## Bundles et performances

Comparaison aux artefacts locaux UI 4.4.3 conservés, sans nouveau build de base :

| Mesure brute | UI 4.4.3 | UI 4.5 | Écart |
| --- | ---: | ---: | ---: |
| Initial | 601 509 octets | 601 509 octets | 0 |
| Création Site différée | Absente | 20 602 octets | +20 602 |
| Liste Sites différée | 17 177 octets | 17 548 octets | +371 |
| Détail Site différé | 8 016 octets | 8 359 octets | +343 |
| Dashboard différé | 52 700 octets | 52 700 octets | 0 |
| Ensemble JS/CSS | 747 966 octets | 769 505 octets | +21 539 |

Le chargement initial reste à 601,51 ko, au-dessus du budget de 500 ko de
101,51 ko. Aucun relèvement. Le formulaire ne charge qu'à l'ouverture de sa
route ; transfert estimé de son chunk : 6,01 ko. Le détail augmente pour la
confirmation accessible, la liste pour son lien de création. Pas de polling,
catalogue complet chargé automatiquement ou requête de détail Site sur /new.
Aucun benchmark de latence réelle FastAPI ou de charge n'est revendiqué.

## Fichiers et état Git

Créés : `features/sites/components/site-form/site-form.component.{ts,html,scss,spec.ts}`
et `features/sites/pages/site-create/site-create.component.{ts,html,scss,spec.ts}`
sous `frontend/src/app/`, plus ce rapport.

Modifiés : routes Sites et leurs tests ; liste Sites (HTML/SCSS/spec) ; détail
Sites (TS/HTML, confirmation accessible uniquement) ; README_AI.md,
project-status.md, roadmap.md et note de suivi historique de ui-4.4-site-detail.md.
Aucun fichier Companies/Dashboard, modèle de transport, service API, backend,
dépendance ou budget n'est modifié.

Branche `feature/frontend-sites`, HEAD `491cb24` inchangés. Index vide.
Les modifications restent dans le répertoire de travail, sans commit, push ou
merge. Journaux et serveur simulé dans `frontend/tmp/ui-4.5/`, ignoré par Git.
Validation utilisateur attendue avant livraison et avant UI 4.6.

## UI 4.5.1 - Finitions du formulaire

Vérifications du 17 octobre 2026 sur `feature/frontend-sites`, HEAD `491cb24`.
Les modifications UI 4.5 présentes au départ sont conservées sans commit.

### Comportements ajustés

- L'aide « Choisissez une entreprise pour rattacher le site. » apparaît tant
  qu'aucune sélection n'est vérifiée. Elle disparaît après vérification, y
  compris pour le préremplissage URL, et revient après effacement. La référence
  aria-describedby est adaptée à sa présence. Les états de chargement et
  d'erreur ainsi que la vérification du parent avant POST sont conservés.
- Le bouton « Retirer la description » apparaît uniquement pour une chaîne
  non vide, sans normalisation des espaces. Il est absent au départ et après
  effacement. Le retrait explicite conserve la valeur null et le champ dirty,
  puis remet le focus sur le textarea lorsque le bouton disparaît.
- La sérialisation reste inchangée : description non touchée omise du POST,
  effacement manuel transmis comme chaîne vide, retrait par bouton transmis
  comme null. Aucun changement du contrat ni de la logique de soumission.
- Une marge locale de 12 px sépare le textarea du bouton, aligné à gauche.
  Aucun conteneur vide n'est ajouté. Lorsque le bouton est absent, l'espace
  existant de 24 px avant les actions est conservé. Le message d'erreur reste
  associé au textarea et se trouve après le bouton lorsqu'il est présent.

Fichiers concernés par cette finition uniquement : les quatre fichiers
`site-form.component.{ts,html,scss,spec.ts}`, le test
`site-create.component.spec.ts` et ce rapport. Les autres modifications du
répertoire de travail appartiennent à UI 4.5.

### Validations propres à UI 4.5.1

Exécutions séquentielles, sans build concurrent :

| Contrôle | Résultat |
| --- | --- |
| Tests Angular complets | 545 réussites, 41 fichiers ; départ 10:32:48 UTC, durée 18,59 s |
| Build production | Réussi à 10:33:31 UTC, durée 9,554 s ; sortie `tmp/ui-4.5.1/production` |
| Tests du correctif Sass | 5 réussites, 0 échec |
| Compatibilité Sass | Dart Sass 1.97.3, quatre expressions, huit breakpoints, media queries et thème unique vérifiés |
| `git diff --check` | Réussi |

Trois tests supplémentaires couvrent notamment l'aide conditionnelle, les
transitions de description et le POST null après retrait réel dans le DOM.
Les contrôles fonctionnels UI 4.5 sont conservés. Une erreur de typage du helper
DOM des nouveaux tests a été corrigée avant les suites réussies. La suite
finale ci-dessus inclut le retour du focus après retrait. Les résultats npm
ls/audit de la section précédente restent historiques et ne constituent pas
une nouvelle exécution UI 4.5.1.

| Mesure brute | UI 4.5 | UI 4.5.1 | Écart |
| --- | ---: | ---: | ---: |
| Initial | 601 509 octets | 601 509 octets | 0 |
| Création Site différée | 20 602 octets | 21 009 octets | +407 |
| Ensemble JS/CSS | 769 505 octets | 769 912 octets | +407 |

Transfert estimé du chunk de création : 6,08 ko. Le dépassement initial du
budget de 500 ko reste inchangé : 601,51 ko, soit +101,51 ko.

Contrôle navigateur sur build production avec API simulée aux largeurs 1440,
1024, 1023, 768, 390 et 320 px : aucun débordement horizontal, écart de 12 px
entre textarea et bouton, alignement à gauche. À 320 px, Tab depuis le bouton
atteint « Créer le site » avec focus visible ; Entrée retire la description et
rend le focus au textarea. L'aide disparaît après sélection vérifiée, revient
après effacement et reste présente pour une entreprise introuvable. Les
informations de pagination des références restent affichées.

Captures de cette finition dans le dossier de visualisation de la tâche :
`ui-4.5.1-description-1440.jpg`, `ui-4.5.1-description-320.jpg`,
`ui-4.5.1-after-removal-320.jpg` et
`ui-4.5.1-unavailable-company-320.jpg`. Les largeurs intermédiaires ont été
inspectées avec des vues partielles lorsque la capture pleine page échouait.
Le journal HTTP de cette vérification visuelle ne contient que des GET
simulés. Les POST des tests unitaires sont interceptés. Aucune écriture réelle
FastAPI ou PostgreSQL. Lecteur d'écran réel, zoom réel et mobile physique non
testés. Serveur temporaire arrêté et viewport restauré.

Branche et HEAD inchangés, index vide. UI 4.5 et UI 4.5.1 restent non commités,
en attente de validation. Aucun début de UI 4.6.
