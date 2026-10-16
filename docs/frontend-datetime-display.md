# Finition UI - Dates et horodatages

Note de suivi : la section historique sur les contrôles natifs Dashboard est
remplacée par la [correction des modes simple et avancé](dashboard-date-precision.md).
Ce nouveau rapport contient les validations les plus récentes des filtres.

Date : 16 octobre 2026. Branche : `fix/frontend-datetime-display`.
Base : `main` propre, synchronisée par `git fetch origin` et comparée à
`origin/main` (0 commit d'écart), HEAD `537822c`. La branche demandée est créée
depuis cette base. Aucun commit, push ou merge effectué.

## Résultat et exemples avant/après

| Zone | Avant | Après |
| --- | --- | --- |
| Dashboard : début inclus, fin exclue, au calcul et derniers relevés | `2026-10-16T11:51:15.910577Z` | `16/10/2026 à 11:51:15 UTC` |
| Dashboard : instant avec décalage | `2026-10-16T13:51:15.910577+02:00` | `16/10/2026 à 11:51:15 UTC` |
| Companies : création ou modification sans fuseau | `2026-08-31T14:58:20.179290` | `31/08/2026 à 14:58` |
| Companies : décalage explicite | `2026-10-16T13:51:15.910577+02:00` | `16/10/2026 à 11:51 UTC` |
| Date absente ou invalide | Valeur brute ou ancien texte de repli | `Non disponible` |
| Companies : édition | Pas de dates de suivi | Section « Informations de suivi », « Créée le » et « Modifiée le » |

La section de suivi est placée après les champs modifiables et avant les boutons
de modification, comme texte sémantique `section/h2/dl/dt/dd`. Elle est projetée
dans le formulaire HTML, sans appartenir au FormGroup. Elle n'existe pas en création. Aucun input,
contrôle FormGroup ou champ PATCH administratif n'est ajouté.

## Fuseaux, précision et séparation de l'affichage

L'utilitaire commun `shared/utils/datetime-display.ts` fournit deux fonctions :
format administratif à la minute et format Dashboard à la seconde.
Il vérifie les composantes ISO, la validité calendaire et le décalage avant
formatage. Les dates impossibles (31 avril, faux 29 février, heures ou offsets
invalides) ne sont pas normalisées silencieusement.

Sans fuseau Companies, les composantes année/mois/jour/heure/minute sont
conservées, y compris pendant un changement d'heure. Aucun parsing implicite
en heure locale ni ajout de suffixe UTC. Avec `Z` ou offset explicite, l'instant
est converti vers UTC, avec gestion des changements de jour/année et suffixe
UTC. Le formateur Dashboard exige un fuseau explicite, sans en inventer un.

Les fractions sont masquées sans arrondi, uniquement pour construire le texte.
Les DTO bruts restent intacts, notamment les six décimales FastAPI. Les valeurs
de mesure et les âges API gardent leur précision numérique. Les dates de journées
du tableau de volume quotidien restent des dates seules, sans heure inventée ;
ce correctif cible les horodatages et les filtres temporels.

Les services API, la façade Dashboard, le modèle des filtres, les validateurs
temporels, les DTO Companies, le FormGroup Companies et la construction du PATCH
ne sont pas modifiés. PATCH différentiel, protection d'abandon, verrou de
soumission et notifications Nebular sont conservés et couverts par les suites.

## Limitation des contrôles natifs Dashboard

Les deux champs `datetime-local` gardent `step="0.001"`, leurs valeurs exactes,
leur validation et leur interprétation UTC déjà définie par le filtre. Leur
apparence dépend du navigateur et de sa langue. Retirer les fractions de leur
valeur ou modifier le pas risquerait de déplacer une borne ou de rendre une
valeur invalide. Le comportement natif est donc conservé.

Une lecture française sans fractions est ajoutée sous chaque contrôle, avec
« Début inclus » ou « Fin exclue ». Cette lecture ne remplace jamais la valeur
du contrôle. Les valeurs sélectionnées restent visibles et modifiables avec
leur précision native. Un intervalle de moins d'une seconde peut ainsi avoir
deux libellés identiques : les champs natifs conservent la distinction exacte.

Contrôle navigateur et journal HTTP simulé :

```text
start_time=2026-10-01T08:00:00.123Z
end_time=2026-10-08T08:00:00.124Z
```

Les aperçus affichent respectivement `01/10/2026 à 08:00:00 UTC` et
`08/10/2026 à 08:00:00 UTC`. La fin reste exclusive. Les tests existants de
validation (ordre des bornes, fin future, dates invalides, préréglage UTC)
restent valides.

## Fichiers modifiés et ajoutés

Chemins relatifs à `frontend/src/app/` pour les fichiers Angular.

| Groupe | Fichiers | Changement |
| --- | --- | --- |
| Utilitaire commun | `shared/utils/datetime-display.ts`, `datetime-display.spec.ts` | Deux fonctions pures, tests UTC/offset/sans fuseau/fractions/calendrier/valeurs absentes. |
| Dashboard | `features/dashboard/pages/dashboard/dashboard.component.ts`, `.html`, `.spec.ts` | Métadonnées françaises ; tests de précision API, requête et actualisation. |
| Filtres | `features/dashboard/components/dashboard-filters/dashboard-filters.component.ts`, `.html`, `.scss`, `.spec.ts` | Aperçus français, sans changement du contrôle natif ou de sa valeur. |
| Relevés | `features/dashboard/components/measurement-summary/measurement-summary.component.ts`, `.html`, `.spec.ts` | Instant du calcul et horodatage du relevé, secondes conservées. |
| Détail Companies | `features/companies/pages/company-detail/company-detail.component.ts`, `.html`, `.spec.ts` | Dates administratives formatées, DTO intact, réserve sur le fuseau précisée. |
| Formulaire Companies | `features/companies/pages/company-form/company-form-page.component.ts`, `.html`, `.scss`, `.spec.ts`, `company-edit-page.component.spec.ts` | Section de suivi en édition ; tests absence en création, lecture seule, aucun changement induit et aucun champ administratif dans PATCH. |
| Projection de suivi | `features/companies/components/company-form/company-form.component.html` | Emplacement de projection entre fieldset et boutons, sans ajout de contrôle ni changement de soumission. |
| Rapport | `docs/frontend-datetime-display.md` | Ce bilan. |

Au total : 19 fichiers suivis modifiés et trois fichiers ajoutés (utilitaire,
ses tests et ce rapport). Aucun changement backend/PostgreSQL, package, lockfile,
budget ou configuration Angular.

## Validations exécutées dans cette étape

Les tests et le build sont exécutés séquentiellement, sans build concurrent.
Les commandes Angular utilisent les permissions nécessaires hors du bac à sable
Windows, conformément à la limitation EPERM Vitest documentée en UI 3.7.1.

| Contrôle | Résultat actuel |
| --- | --- |
| Premier passage Angular | 375/375, 32 fichiers |
| Suite finale, après ajout des deux tests de conservation des données | 377/377, 32 fichiers |
| Build production final | Réussi |
| Tests du correctif Sass | 5/5 |
| Vérification Sass | Quatre expressions, huit breakpoints, thème unique conformes |
| Navigateur, build production avec API locale simulée | Huit contrôles à 1440 et 320 px : Dashboard, détail, édition, création ; aucun débordement horizontal global observé |
| Console du navigateur de prévisualisation | Aucune erreur ni warning relevé |
| `git diff --check` | Réussi |

Les tests ajoutés couvrent les conversions positives/négatives d'offset avec
changement de jour/année, dates sans fuseau en périodes de changement d'heure,
fractions sans arrondi, dates invalides/absentes et calendrier bissextile.
Ils vérifient également la conservation des DTO bruts et des bornes API lors
d'une actualisation, les millisecondes des contrôles natifs, l'absence de dates
dans le FormGroup/PATCH, l'absence de PATCH induit et l'absence du suivi en création.

Commandes depuis `frontend/` :

```powershell
node node_modules/@angular/cli/bin/ng.js test --watch=false
node node_modules/@angular/cli/bin/ng.js build --configuration=production --output-path=tmp/datetime/production
node --test scripts/apply-nebular-sass-fix.test.mjs
node scripts/verify-nebular-breakpoints.mjs
```

Journaux courants dans `frontend/tmp/datetime/` (ignoré par Git) : `tests.log`,
`tests-final.log`, `build.log`, `preview-requests.log`. Prévisualisation de
production sur 127.0.0.1:8099 avec réponses GET simulées et refus des écritures.
Aucun appel FastAPI réel ni accès PostgreSQL pour ces contrôles. Le serveur
temporaire a été arrêté après les vérifications.

Captures desktop/mobile et mesures DOM conservées dans le répertoire local
de visualisations de ce chat : `datetime-edit-1440.png`, `datetime-edit-320.png`,
`datetime-detail-320.png`, `datetime-dashboard-desktop.png`,
`datetime-dashboard-1440.png`, `datetime-dashboard-320.png` et
`datetime-responsive-checks.json`. Le redimensionnement CSS ne valide pas un
zoom navigateur réel ni un lecteur d'écran réel.

## Bundle et état de livraison

Initial : **600,89 ko**, soit exactement **600 894 octets**, inchangé.
Budget warning toujours 500 ko, dépassement connu 100,89 ko ; aucun seuil relevé.
Transfert initial estimé après finition UX : 153,18 ko, contre 153,15 ko à la référence.

Le formateur est partagé dans un chunk différé de 992 octets. Dashboard différé :
45,81 ko (référence 45,38) ; formulaire Companies : 17,17 ko (15,97) ; détail :
7,79 ko (7,77). L'ensemble JS/CSS initial et différé augmente de 2 642 octets
bruts, sans nouvelle dépendance. Les pages restent différées ; Shell et liste
Companies inchangés.

La comparaison utilise les artefacts de référence UI 3.7.1, dont les sources
frontend sont identiques à la base `537822c` (comparaison Git vérifiée), et le
build courant. Aucun nouveau build de référence n'est présenté comme exécuté.

Branche finale `fix/frontend-datetime-display`, HEAD `537822c` inchangé.
22 fichiers concernés, non commités. Le diff reste limité à l'affichage des
dates, sa section de suivi, ses tests et ce rapport. Validation utilisateur
attendue avant tout commit ; aucun push ou merge.

## Finition UX Companies après validation du formatage

Le formatage est validé par l'utilisateur et reste inchangé. La fiche détail
affiche désormais exactement « Dates affichées selon les informations horaires
du serveur. ». Le paragraphe technique de l'édition est supprimé. La section
« Informations de suivi » apparaît entre les champs et les boutons, dans l'ordre
du DOM, sans réordonnancement CSS du parcours de lecture. Les dates sont du texte
en lecture seule, sans contrôle FormGroup et sans champ PATCH.

Le test de placement est adapté et les contrôles de payload/absence de changement
induit sont conservés. Les tests existants de soumission, protection d'abandon,
erreurs et annonces accessibles restent actifs. Nouvelle suite complète :
377/377 tests, 32 fichiers, sans build concurrent (`tests-ux.log`).

Build production suivant réussi (`build-ux.log`), puis `git diff --check` réussi.
Initial inchangé à 600,89 ko ; warning existant de budget conservé, aucun seuil
modifié. Sur la prévisualisation du build avec API simulée en lecture seule,
fiche et édition sont vérifiées à 1440 et 320 px : ordre visuel champs/suivi/
boutons correct, zéro contrôle éditable dans le suivi, texte exact de la fiche,
aucun paragraphe technique dans le suivi et aucun débordement horizontal global.
Aucune erreur ni warning console relevé. Captures `datetime-ux-edit-1440.png`,
`datetime-ux-edit-320.png` et mesures `datetime-ux-checks.json` dans le répertoire
de visualisations local du chat. Serveur arrêté après les contrôles.

Cette reprise modifie uniquement six fichiers Companies (templates du détail,
du formulaire partagé et de la page d'édition, styles de suivi, tests détail et
édition) et ce rapport. Le formateur et les changements Dashboard précédemment
validés ne sont pas retouchés. Aucun backend, contrat, package ou budget modifié.
