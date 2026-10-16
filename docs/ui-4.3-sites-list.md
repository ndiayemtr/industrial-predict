# UI 4.3 - Liste et recherche des sites industriels

Livraison : UI 4.3 et UI 4.3.1 commitées dans `43f72f8`. Les résultats et états
Git de ce document sont historiques ; le détail est traité dans le
[bilan UI 4.4](ui-4.4-site-detail.md).

Suivi : les finitions UX UI 4.3.1 et leurs validations plus récentes sont
consignées dans la dernière section de ce rapport.

Date : 16 octobre 2026. Branche `feature/frontend-sites`, HEAD `cd2389d`, dépôt
propre au départ. UI 4.2 validée et commitée. UI 4.3 implémentée, en attente de
validation ; aucun commit, push ou merge. UI 4.4 non commencée.

## Périmètre livré dans le répertoire de travail

- Route `/sites` différée dans le Shell, remplaçant son placeholder. Seule la
  liste existe : aucun lien de détail, création, modification ou suppression.
  Une future URL `/sites/3` reste sur la 404 globale.
- Sélection explicite d'entreprise, sans sélection automatique même si une seule
  option existe. Sans sélection valide : invitation initiale et aucun GET Sites.
- Catalogue d'entreprises paginé via ReferenceDataApiService.getCompanies,
  chargement manuel des pages suivantes, déduplication et conservation des
  options déjà chargées si une page ultérieure échoue. La relance reprend cette
  page, sans réinitialiser la sélection. Erreur du catalogue distincte des erreurs
  de résultat Sites.
- Entreprise de l'URL vérifiée par getCompanyById, même si elle est hors de la
  première page du catalogue. Son option est ajoutée si nécessaire. Une 404
  entreprise est une erreur, pas un vide Sites. La référence est vérifiée à
  chaque chargement de Sites, y compris pagination/recherche ; ce choix produit
  une lecture supplémentaire par chargement, sans cache ni requête par ligne.
- Tableau Nom/Code/Description, description absente signalée. L'entreprise est
  identifiée au-dessus du tableau par nom, code et identifiant. Tous les sites
  affichés proviennent du filtre company_id serveur. Le tri fixe id croissant
  est annoncé ; aucun tri dynamique proposé.
- Recherche serveur explicite (bouton ou Entrée), nom/code, maximum 100
  caractères ; recherche vide omise, jokers %/_ signalés, pas de requête à la
  frappe ni de filtrage limité à la page affichée.
- Pagination Précédent/Suivant, taille de page (20/50/100, et toute valeur valide
  venant de l'URL), total et nombre de pages serveur. Changement d'entreprise :
  page 1 et recherche effacée. Recherche, effacement et taille : retour page 1.
- États idle/loading/empty/error/success ; total=0 distinct de items vide avec
  total positif, qui propose un rattrapage manuel vers une page disponible.
  Aucune boucle de recalage ou relance automatique.

## URL, concurrence, navigation et accessibilité

L'URL appliquée est la source de company_id/page/page_size/search. Identifiants
et pages doivent être des entiers positifs sûrs, page_size entre 1 et 100,
search trimée et bornée. Les paramètres invalides sont normalisés avec notice
et replaceUrl avant la requête ; une entreprise invalide est retirée, sans en
choisir une autre. Les paramètres de contexte complémentaires et le fragment
sont préservés. Le retour navigateur depuis Companies restaure les filtres Sites.

SitesListFacade locale expose des signals en lecture seule et un snapshot
immutable. switchMap annule la vérification du parent et le GET Sites obsolètes,
y compris lors d'une désélection ; destruction nettoyée par takeUntilDestroyed.
La liste utilise SitesApiService sans modifier ses méthodes d'écriture. Les
erreurs de lecture réseau/5xx sont relançables manuellement avec le snapshot ;
422 et accès refusé ne sont pas assimilés à un vide. Aucun accès au backend réel,
aucune écriture réelle et aucun appel POST/PATCH/DELETE par la page.

PageHeader et composants LoadingState/EmptyState/ErrorState existants,
labels/aides, erreurs associées, focus visible, aria-busy, annonces de résultats
role=status, tableau avec caption et scope. Un seul h1. Les filtres internes
conservent le focus ; l'arrivée sur une page conserve la gestion du focus main
du Shell. Entrée déclenche la recherche et le menu mobile conserve Échap,
confinement/restauration du focus. Aucun changement de code Shell ou Sidebar.

Le filtre ergonomique et la vérification d'existence du parent ne constituent
pas une autorisation multi-entreprises. Cette limite backend reste ouverte.
Aucun indicateur, champ de localisation, compteur d'équipements ou date n'est
inventé. Les horodatages ne sont pas affichés dans cette liste et restent bruts
dans les DTO. Aucun changement fonctionnel Companies ou Dashboard.

## Fichiers modifiés ou créés

Sous `frontend/src/app/features/sites/` :

- `models/sites-state.model.ts` : requête appliquée et union d'états.
- `sites-list.facade.ts`, `.spec.ts` : parent vérifié, liste, erreurs, annulations.
- `sites.routes.ts`, `.spec.ts` : liste différée, Shell/focus/404, aucune future route.
- `pages/sites-list/sites-list.component.ts`, `.html`, `.scss`, `.spec.ts` :
  catalogue d'entreprises, URL, recherche, pagination, rendu et tests de page.

Fichiers existants : `frontend/src/app/app.routes.ts`, `.spec.ts` et
`frontend/src/app/layout/sidebar/sidebar.component.spec.ts`. Les assertions
Sidebar/routing sont adaptées au remplacement effectif du placeholder, sans
réduire les neuf liens attendus ou les contrôles des autres placeholders.

Documentation : ce rapport, README_AI.md, project-status.md, roadmap.md et une
note de livraison historique dans ui-4.2-sites-data-access.md. Aucun fichier
backend, PostgreSQL, dépendance, lockfile ou budget modifié.

## Validations techniques exécutées séquentiellement

| Contrôle | Résultat |
| --- | --- |
| Premier passage Angular | 439 réussis, 2 échecs : anciens tests Sidebar attendent encore le titre/placeholder Sites |
| Suite complète après adaptation | **444 tests réussis, 36 fichiers**, démarrée à 17:59:20 UTC ; durée 24,80 s |
| Build production suivant | **Réussi**, terminé à 18:00:16 UTC |
| Tests du correctif Sass | **5/5** |
| Vérification Sass | Quatre expressions, huit breakpoints, media queries et thème unique conformes |
| npm ls --all | Code 0 |
| npm audit --json | Code 0, **0 vulnérabilité**, toutes sévérités |
| git diff --check | Réussi |

Commandes Angular : `node node_modules/@angular/cli/bin/ng.js test --watch=false`,
puis `node node_modules/@angular/cli/bin/ng.js build --configuration=production --output-path=tmp/ui-4.3/production`.
Puis `node --test scripts/apply-nebular-sass-fix.test.mjs`,
`node scripts/verify-nebular-breakpoints.mjs`, `npm ls --all`, `npm audit --json`.
Aucun build concurrent aux tests. Les 26 nouveaux tests couvrent page, façade
et routing ; les suites Companies/Dashboard/Shell/404 restent exécutées.
Les HTTP sont simulés, et les tests de la page/façade vérifient l'absence
de toute requête autre que GET.

Cas couverts : démarrage sans entreprise, sélection et référence hors catalogue,
pagination du catalogue et reprise après erreur, recherche explicite et limites,
pages/taille/contexte URL, normalisation, vides, page hors plage, parent disparu,
erreurs réseau/403/422/500, annulation des réponses obsolètes/désélection/destruction,
labels/focus, routes différées, titres et sélection Sidebar, absence d'actions
non disponibles. Les tests anciens ne sont ni ignorés ni relancés automatiquement.

## Contrôle navigateur et responsive

Build de production servi sur 127.0.0.1:8099 avec fixtures locales, serveur
strictement GET et refus des écritures. Ce contrôle n'est pas une validation
d'intégration FastAPI réelle. Catalogue de 52 entreprises, sites avec Unicode,
description absente et mots longs pour le repli responsive.

Vérification visuelle et DOM à **1440, 1024, 1023, 768, 390 et 320 px**, hauteur
900 px : un h1, aucun débordement horizontal global ou des contrôles/tableau.
Shell latéral à 1024 px, panneau mobile à 1023 px. Les sélecteurs natifs peuvent
tronquer le nom de leur option à 320 px ; le nom complet de l'entreprise reste
lisible dans les résultats au-dessus du tableau.

Parcours navigateur : aucune sélection initiale ; chargement du catalogue
50/52 puis 52/52 ; sélection entreprise 7 ; recherche Station par Entrée avec
focus maintenu ; effacement ; entreprise 8 sans sites ; pagination page_size=1,
page 2 ; recherche Usine avec retour page 1 ; navigation Companies puis retour
navigateur avec contexte identique. Menu mobile ouvert au clavier, fermeture
Échap et focus rendu au bouton. Console sans erreur ni warning relevé.
Journal de prévisualisation : uniquement GET, aucune écriture.

Captures `sites-list-1440.png`, `sites-list-1024.png`, `sites-list-1023.png`,
`sites-list-768.png`, `sites-list-390.png`, `sites-list-320.png` et mesures
`sites-responsive-checks.json` conservées dans le dossier de visualisations local
du chat. Aucun lecteur d'écran réel, appareil mobile physique ou zoom navigateur
réel 200/400 % validé dans cette étape ; le redimensionnement CSS ne les remplace pas.

## Bundles et limites

- Initial : **601 281 octets (601,28 ko)**, contre 600 894 octets en UI 4.2,
  soit **+387 octets**. Budget 500 ko inchangé, dépassement **101,28 ko**.
- Page Sites différée : **16,74 ko**, routes également différées.
- Dashboard différé : **49,39 ko** ; Companies liste **12,57 ko**, détail
  **7,79 ko**, formulaire **17,17 ko** ; Shell **14,76 ko**.
- Ensemble JS/CSS : **735 023 octets**, contre 717 645 octets au bilan UI 4.2,
  soit **+17 378 octets**. Comparaison au bilan historique, sans nouveau build de base.

La hausse initiale limitée accompagne l'ajout de la route différée et des
imports partagés ; aucun relèvement de budget. Pas d'optimisation globale
Nebular ou refonte de composants hors périmètre. Les journaux de validation
et le serveur de prévisualisation sont dans `frontend/tmp/ui-4.3/`, ignoré par Git.

Le détail, la création, la modification, la suppression et le transfert de Site
ne sont pas disponibles dans cette page. L'étape suivante reste UI 4.4, uniquement
après validation et demande dédiée. Aucun commit, push ou merge effectué.

## UI 4.3.1 - Finitions UX de la liste

Intervention du 16 octobre 2026 sur `feature/frontend-sites`, HEAD `cd2389d`.
Les modifications UI 4.3 étaient encore non commitées et sont conservées.
Cette reprise touche uniquement le template `sites-list.component.html`,
ses tests `sites-list.component.spec.ts` et le présent rapport.

- Sans entreprise sélectionnée, l'aide affiche exactement « Sélectionnez une
  entreprise pour afficher ses sites. ». Elle disparaît après sélection et
  revient après désélection. aria-describedby ne référence l'aide que lorsqu'elle
  existe. Le compteur, le chargement et la pagination du catalogue d'entreprises
  restent disponibles.
- Pour un total de zéro site, la pagination Précédent/Suivant et les métadonnées
  de pages disparaissent. L'annonce « 0 site(s) », l'état vide, son explication
  et l'action Effacer la recherche active restent présents. Le sélecteur de
  taille de page dans les filtres est conservé.
- Dès que des sites existent, pagination et totaux retrouvent leur affichage
  antérieur. Une page hors plage avec total positif conserve sa pagination et
  son action de récupération. Aucun changement de paramètres URL ou HTTP,
  service, façade, annulation des requêtes, filtre ou sérialisation.

Tests : un cas supplémentaire de désélection, assertions adaptées pour l'aide,
ses références ARIA et les vides avec/sans recherche ; vérification de l'action
d'effacement, du retour de pagination et de la page hors plage. Les contrôles
fonctionnels précédents sont conservés.

Validations successives, sans build concurrent aux tests :

- Suite Angular complète : **445 tests réussis, 36 fichiers**, démarrée à
  18:17:10 UTC, durée 27,32 s (`tmp/ui-4.3.1/tests.log`).
- Build production : **réussi**, terminé à 18:18:11 UTC
  (`tmp/ui-4.3.1/build.log`, sortie `tmp/ui-4.3.1/production`).
- Contrôle visuel du build à **1440 et 320 px** avec API locale simulée en
  lecture seule : avant sélection, après sélection, recherche Absent sans site,
  effacement et retour des résultats, désélection. Aucune pagination dans le vide,
  retour de pagination avec les résultats, compteur d'entreprises conservé,
  aucun débordement horizontal observé ni erreur/warning console relevé.
- `git diff --check` réussi. Aucun contrôle Sass/npm supplémentaire relancé
  pour ces modifications de template ; leurs résultats UI 4.3 ci-dessus restent
  historiques. Aucun changement backend, PostgreSQL, dépendance ou budget.

Bundle initial **601 281 octets (601,28 ko)**, inchangé par rapport à UI 4.3 ;
warning connu **101,28 ko** au-dessus du budget de 500 ko, sans relèvement.
Chunk Sites différé **16,98 ko** contre 16,74 ko ; total JS/CSS **735 263 octets**
contre 735 023, soit **+240 octets**. Les deux jeux d'artefacts locaux ont été
mesurés sans relancer de build de référence.

Captures locales : `sites-ux-initial-1440.png`, `sites-ux-selected-1440.png`,
`sites-ux-empty-1440.png` et leurs équivalents `320.png`, dans le dossier de
visualisations du chat. Le serveur temporaire est arrêté après contrôle.
Ces contrôles ne constituent pas une nouvelle validation FastAPI réelle ou
une validation de lecteur d'écran réel. Aucun commit, push ou merge ; UI 4.4
non commencée. En attente de validation utilisateur.
