# UI 4.4 - Fiche détail d'un site industriel

Suivi : UI 4.4 et ses finitions UI 4.4.1 à UI 4.4.3 sont commitées dans
`491cb24`. Les résultats et états Git ci-dessous décrivent les séances historiques.
La création fait l'objet du [rapport UI 4.5](ui-4.5-site-create.md).

Date : 16 octobre 2026. Branche `feature/frontend-sites`, HEAD de référence
`43f72f8`, dépôt propre avant intervention. Statut : implémenté, en attente de
validation. Aucun commit, push ou merge. UI 4.5 non commencée.

## Contrats vérifiés et périmètre

Relecture de la [conception UI 4.1](etape-ui-4.1-sites.md), du
[transport UI 4.2](ui-4.2-sites-data-access.md), de la
[liste UI 4.3 et de ses finitions](ui-4.3-sites-list.md), de la fiche Companies,
du Shell et de l'utilitaire de dates partagé.

Le [schéma Pydantic SiteRead](../backend/app/schemas/site.py) expose id, name,
code, description nullable, company_id, created_at et updated_at. Les
[routes FastAPI](../backend/app/api/routes/sites.py) fournissent GET
`/api/v1/sites/{site_id}` avec 404 si absent. La référence entreprise utilise
GET `/api/v1/companies/{id}`, via ReferenceDataApiService.getCompanyById.
SiteRead et SitesApiService existants sont réutilisés sans modification.

La fiche, après finition UI 4.4.1, affiche nom, code, description intégrale et
entreprise de rattachement. Description absente : « Non renseignée ». Les dates
de création et de modification sont affichées lorsqu'elles sont présentes.
Identifiants, dates et descriptions ne sont jamais envoyés à une écriture :
la page ne comporte aucun formulaire, bouton Modifier ou Supprimer.

## Navigation et contexte

La route différée `/sites/:siteId` est ajoutée après la route statique de liste
à correspondance complète. Aucun itinéraire new/edit n'est créé pour anticiper
les étapes suivantes. Les segments simples utilisés comme identifiants invalides,
par exemple `/sites/0` ou `/sites/abc`, produisent une erreur locale explicite
avant tout HTTP. Les routes imbriquées inconnues, par exemple
`/sites/1/unknown`, restent sur la 404 globale.

Dans la liste, le nom du site devient un vrai RouterLink vers le détail. Les
quatre paramètres appliqués company_id/search/page/page_size sont conservés.
« Retour à la liste des sites » est un vrai lien, avec les mêmes paramètres
validés : entiers positifs sûrs, page_size entre 1 et 100, recherche trimée de
100 caractères maximum. Aucun returnUrl libre ni redirection externe.

En accès direct sans contexte, retour vers la liste page 1, taille 20, avec
l'entreprise réelle du site une fois celui-ci chargé. En erreur Site sans
contexte connu, retour à la liste sans entreprise inventée. Si le contexte de
retour indique une autre entreprise, il reste conservé pour le retour, tandis
que le détail affiche le parent réel et signale la différence. Ce comportement
ergonomique ne constitue pas une autorisation d'accès.

Titres Router et Header : « Détail du site ». Sidebar Sites active, neuf liens
de navigation conservés. Le focus main à l'arrivée est géré par le Shell
existant ; le lien de retour possède son focus visible et fonctionne avec Entrée.
Aucun changement applicatif du Shell ou de la Sidebar.

## Lectures, états et horodatages

SiteDetailComponent conserve ses états locaux, avec signals et flux RxJS :
loading, succès ou erreur Site ; puis loading, succès ou erreur de référence
entreprise au sein du succès Site. Le Site est visible pendant la lecture du
parent. Ce parent est toujours demandé avec le company_id de SiteRead, jamais
celui du contexte URL.

404 Site : « Site introuvable (404) », sans formulaire vide ou recréation.
Réseau/5xx : erreur et relance manuelle. Entreprise 404 ou indisponible :
conserver les champs métier Site et l'identifiant de rattachement en mémoire, afficher une erreur
explicite, sans inventer de nom/code. La relance réseau/5xx de la référence ne
recharge que l'entreprise. 400/422 et accès refusé ne sont pas assimilés à des vides.
Aucune relance automatique.

Les changements de siteId annulent les lectures Site et entreprise obsolètes,
y compris si le nouvel identifiant est invalide. toSignal assure le nettoyage
à la destruction ; les erreurs de référence restent distinctes des erreurs Site.
Aucun POST/PATCH/DELETE, cache global, store, polling ou mise à jour optimiste.

[formatAdministrativeDateTime](../frontend/src/app/shared/utils/datetime-display.ts)
est réutilisé sans modification : `JJ/MM/AAAA à HH:mm`, composantes conservées
sans fuseau, conversion correcte en UTC avec suffixe si Z/offset explicite,
fractions masquées uniquement à l'affichage. Valeur présente invalide :
« Non disponible » ; date absente : champ non affiché. Les chaînes DTO restent
intactes. Exemples vérifiés :

| Source | Affichage |
| --- | --- |
| 2026-08-31T14:58:20.179290 | 31/08/2026 à 14:58 |
| 2026-10-16T13:51:15.910577+02:00 | 16/10/2026 à 11:51 UTC |
| 2026-10-16T11:51:15.910577Z | 16/10/2026 à 11:51 UTC |

## Fichiers créés et modifiés

Créés :

- `frontend/src/app/features/sites/pages/site-detail/site-detail.component.ts`.
- `frontend/src/app/features/sites/pages/site-detail/site-detail.component.html`.
- `frontend/src/app/features/sites/pages/site-detail/site-detail.component.scss`.
- `frontend/src/app/features/sites/pages/site-detail/site-detail.component.spec.ts`.
- Le présent rapport.

Modifiés :

- `frontend/src/app/features/sites/sites.routes.ts` et `.spec.ts` : route détail,
  chargement différé, titres/focus/Sidebar et 404 globale toujours vérifiée.
- `frontend/src/app/features/sites/pages/sites-list/sites-list.component.ts`,
  `.html`, `.scss`, `.spec.ts` : RouterLink du nom, focus visible et contrôle du lien.
- README_AI.md, project-status.md, roadmap.md et note de livraison historique
  dans ui-4.3-sites-list.md.

Aucun changement backend, PostgreSQL, contrats API, modèles partagés, utilitaire
de dates, services HTTP, dépendances, lockfile ou budget Angular. Aucun changement
fonctionnel Companies ou Dashboard. Pas d'import d'un composant/style interne
Companies dans Sites ; les mêmes tokens et composants shared sont utilisés.

## Validations techniques exécutées

Exécutions séquentielles, sans build concurrent aux tests :

| Contrôle | Résultat |
| --- | --- |
| Angular complet | **468 tests réussis, 37 fichiers** ; démarré à 18:36:13 UTC, durée 15,60 s |
| Build production suivant | **Réussi**, terminé à 18:37:34 UTC |
| Tests correctif Sass | **5/5**, aucun échec |
| Vérification Sass | Dart Sass 1.97.3 : quatre expressions, huit breakpoints, media queries et thème unique conformes |
| git diff --check | Réussi |

Commandes depuis frontend :

```text
node node_modules/@angular/cli/bin/ng.js test --watch=false
node node_modules/@angular/cli/bin/ng.js build --configuration=production --output-path=tmp/ui-4.4/production
node --test scripts/apply-nebular-sass-fix.test.mjs
node scripts/verify-nebular-breakpoints.mjs
```

Les 23 nouveaux cas couvrent chargements Site/entreprise, référence encore
en cours, dates sans fuseau/Z/offset/fractions/calendrier invalide, absence de
description/dates, 404/422/réseau/5xx, relances manuelles distinctes, ids invalides,
annulation Site/référence/passage à un id invalide/destruction, lien de retour,
contexte liste/détail/liste et intégration Shell. Les tests HTTP utilisent
HttpTestingController et vérifient l'absence de toute requête non GET. Les
assertions existantes sont adaptées à la route désormais disponible, sans
supprimer la couverture des routes inconnues. Companies, Dashboard et 404
restent dans la suite complète.

## Contrôles visuels et limites

Build servi sur 127.0.0.1:8099 avec API locale simulée, serveur strictement GET.
Vérification visuelle et DOM à **1440, 1024, 1023, 768, 390 et 320 px**, hauteur
900 px : un h1, données en dl/dt/dd, description avec sauts de ligne et mot long,
retour repliable, aucun débordement horizontal constaté. Shell desktop à 1024,
mobile à 1023. Captures `site-detail-<largeur>.png` et mesures
`site-detail-responsive.json` dans le dossier local de visualisations du chat.

Parcours clavier/navigateur : liste filtrée Usine/page 1/taille 1, lien nom par
Entrée, lecture des dates et du parent, retour par Entrée avec contexte identique ;
effacement de recherche, page 2, détail Station avec description absente et UTC
explicite ; référence entreprise 777 introuvable avec Site conservé ; Site 999
en 404 ; erreur serveur simulée 503, relance manuelle ; id 0 sans appel API ;
route imbriquée inconnue sur la 404 globale. Les deux requêtes Site 503 du journal
correspondent à la lecture initiale et au clic explicite Réessayer.

Captures supplémentaires : `site-detail-company-unavailable-320.png` et
`site-detail-not-found-320.png`. Console sans erreur/warning sur les parcours
réussis ; les requêtes 404/500 des scénarios d'erreur sont attendues. Journal :
aucune écriture. Les captures ont été réalisées séparément après mise en page
pour éviter les échecs transitoires de capture lors des changements de viewport.

Aucun accès FastAPI réel ni PostgreSQL dans cette validation ; aucune écriture
réelle, validation de charge, lecteur d'écran réel, appareil mobile physique
ou zoom navigateur réel 200/400 % revendiqué. La vérification du parent et les
filtres frontend ne corrigent pas l'absence d'autorisation multi-entreprises du
backend. Aucune déclaration de préparation à la production SaaS multi-tenant.

## Bundles et état final

- Initial : **601 281 octets (601,28 ko)**, inchangé depuis UI 4.3.1.
  Budget 500 ko inchangé, avertissement de **101,28 ko** conservé.
- Fiche Site différée : **8,12 ko** ; liste Sites différée : **16,84 ko**.
- Ensemble JS/CSS : **744 020 octets**, contre 735 263 en UI 4.3.1,
  soit **+8 757 octets**. Mesure des artefacts locaux, sans nouveau build de base.
- Companies et Dashboard restent différés : liste Companies 12,57 ko, détail
  7,79 ko, formulaire 17,17 ko, Dashboard 49,39 ko ; Shell 14,76 ko.

Journaux et prévisualisation dans `frontend/tmp/ui-4.4/`, ignoré par Git.
Le serveur temporaire est arrêté après contrôle. Branche et HEAD inchangés,
modifications non commitées. Aucun commit, push ou merge ; validation utilisateur
attendue avant toute autre étape. UI 4.5 non commencée.

## UI 4.4.1 - Présentation métier des fiches

Finition du 16 octobre 2026 sur la même branche et le même HEAD `43f72f8`.
Les modifications UI 4.4 étaient déjà présentes et non commitées au démarrage.
Les résultats des sections précédentes correspondent à la validation UI 4.4 ;
les résultats ci-dessous proviennent d'une nouvelle exécution UI 4.4.1.

- Companies : retrait du champ visible Identifiant. Nom, code, description,
  dates et liens de retour/modification conservés.
- Sites : retrait du champ Identifiant du site et de la ligne numérique
  company_id. Le rattachement affiche uniquement le nom et le code métier de
  l'entreprise disponible. Loading, erreur et relance manuelle restent présents,
  sans identifiant de repli visible. La référence occupe une ligne entière sur
  desktop ; la grille mobile reste sur une colonne.
- Aucun changement de modèles, services, contrats HTTP, routes ou formatage des
  dates pour cette finition. Les identifiants restent dans les réponses, les
  états internes, les URLs et la résolution de la relation entreprise.

Fichiers ajustés pour cette finition : les templates CompanyDetail et SiteDetail,
leurs deux fichiers spec, le SCSS SiteDetail et le présent rapport.
Les tests vérifient la liste exacte des champs métier, l'absence des identifiants
visibles, le DTO intact, les liens internes par identifiant et les erreurs parent.
Les contrôles de navigation, annulation, dates et lecture seule sont conservés.

Validations exécutées séquentiellement, sans build concurrent :

- Tests Angular complets : **468/468, 37 fichiers**, départ 18:57:27 UTC,
  durée 18,51 s. Companies, Sites, Dashboard, Shell et routing inclus.
- Build production : réussi à 18:58:04 UTC, durée 9,283 s.
- Bundle initial : **601 281 octets (601,28 ko)**, inchangé par rapport aux
  artefacts UI 4.4 locaux. Budget 500 ko inchangé ; avertissement +101,28 ko.
- Détail Site : **8,01 ko** ; détail Company : **7,70 ko**.
  Ensemble JS/CSS : **743 815 octets**, soit **205 octets de moins** qu'UI 4.4.
- Contrôles navigateur à **1440 et 320 px** pour les deux fiches : libellés,
  dates, codes métier, absence de champs techniques et absence de débordement
  horizontal. Référence entreprise introuvable vérifiée à 320 px : données Site
  conservées, alerte explicite et aucun identifiant numérique affiché.
- Captures : `business-company-detail-1440.png`,
  `business-company-detail-320.png`, `business-site-detail-1440.png`,
  `business-site-detail-320.png`, `business-site-company-unavailable-320.png`.
  Elles utilisent le build production et des réponses HTTP simulées locales,
  exclusivement GET. Aucun accès réel FastAPI ou PostgreSQL.
- `git diff --check` : réussi ; aucun tiret cadratin ajouté.

Journaux et prévisualisation ignorés dans `frontend/tmp/ui-4.4.1/`. Serveur
temporaire arrêté après contrôle. Aucun commit, push ou merge ; validation
utilisateur attendue. Les limites d'accessibilité réelle de la section UI 4.4
restent applicables. UI 4.5 non commencée.

## UI 4.4.3 - Libellé entreprise sans répétition

Finition du 16 octobre 2026 sur `feature/frontend-sites`, HEAD `43f72f8`.
Les travaux UI 4.4 à UI 4.4.2 non commités sont conservés.
La fiche Site réutilise businessReferenceLabel, introduit en UI 4.4.2 :
PETROSEN / PETROSEN devient PETROSEN ; PETROSEN / PTR-001 devient
PETROSEN - PTR-001. Aucun nouveau formateur ni changement de contrat.
Les branches loading/error et les relances manuelles de référence entreprise,
les identifiants internes, le contexte de retour et les dates sont conservés.

Fichiers de cette finition : SiteDetailComponent `.ts`, `.html`, `.spec.ts`
et le présent rapport. Deux tests paramétrés sont ajoutés pour les libellés
identiques/différents, avec vérification des données internes et du RouterLink.

Validation séquentielle de cette version : 504 tests Angular réussis dans
39 fichiers, départ 19:37:05 UTC, durée 24,17 s ; puis build production réussi
à 19:38:07 UTC, durée 13,571 s ; puis `git diff --check` réussi.
Bundle initial inchangé : 601 509 octets (601,51 ko), budget 500 ko inchangé,
avertissement +101,51 ko. Détail Site : 8 016 octets, contre 8 005 en UI 4.4.2,
soit +11 octets ; ensemble JS/CSS : 747 966 octets, également +11 octets.

Les deux libellés sont vérifiés visuellement à 1440 et 320 px, sans débordement
horizontal. Entreprise introuvable vérifiée à 320 px : alerte explicite,
aucun libellé inventé, données Site conservées. Captures :
`ui-4.4.3-site-identical-{1440,320}.jpg`,
`ui-4.4.3-site-distinct-{1440,320}.jpg`,
`ui-4.4.3-site-unavailable-320.jpg` dans le dossier de visualisation de la tâche.
Le build est servi localement avec HTTP simulé, exclusivement GET ; aucun accès
FastAPI réel ou PostgreSQL. Journaux dans `frontend/tmp/ui-4.4.3/`, ignoré par Git.
Serveur arrêté et viewport restauré après contrôle.

État Git : branche et HEAD inchangés, index vide ; les modifications précédentes
et cette finition restent non commitées. Aucun commit, push ou merge.
Validation utilisateur attendue ; UI 4.5 non commencée.
