# UI 4.4.2 - Identifiants métier Dashboard et Sites

Date : 16 octobre 2026. Branche `feature/frontend-sites`, HEAD `43f72f8`.
Implémentation terminée, en attente de validation utilisateur. Aucun commit,
push ou merge. UI 4.5 non commencée.

## Base et périmètre

Le dépôt contenait déjà les travaux non commités UI 4.4 et UI 4.4.1.
Ils sont conservés, notamment les fiches Companies/Sites sans champs techniques,
les dates, la navigation et les états de référence entreprise.
Voir le [rapport UI 4.4 et UI 4.4.1](ui-4.4-site-detail.md).

Cette intervention concerne les libellés du périmètre appliqué du Dashboard,
ses sélecteurs et, après confirmation utilisateur, les équipements des derniers
relevés. Elle harmonise aussi le sélecteur, le résumé et la pagination Sites.
Les identifiants restent dans les DTO, réponses HTTP, relations, routes et
paramètres numériques. Aucun champ de réponse n'est retiré ou réécrit.

## Libellés avant et après

| Zone | Avant | Après |
| --- | --- | --- |
| Dashboard, périmètre | Entreprise - identifiant : 7 | Entreprise : PETROSEN |
| Dashboard, périmètre | Site - identifiant : 1 | Site industriel : Usine de transformation 日本 - SITE-1 |
| Dashboard, périmètre | Équipement - identifiant : 12 | Équipement : Pompe de circulation - P-001 |
| Derniers relevés | Équipement - identifiant : 13 | Équipement : Moteur principal |
| Référence de périmètre en erreur | Identifiant numérique | Référence indisponible |
| Équipement de relevé en erreur | Identifiant numérique | Équipement indisponible |
| Option et résumé Sites | PETROSEN - PETROSEN (identifiant 7) | PETROSEN |
| Nom et code différents | Nom - Code (identifiant N) | Nom - Code |
| Légende du tableau Sites | Sites - page 1 - N au total - identifiants croissants | 1 site trouvé / 2 sites trouvés |
| Métadonnées de pagination | N site(s) - P page(s) | 1 site - 1 page / 2 sites - 2 pages |

Le petit utilitaire partagé businessReferenceLabel normalise les espaces de
présentation et évite de répéter un code identique au nom. Il ne modifie pas les
données sources. Nom et code absents : Référence indisponible. Les options nulles
Tous les sites et Tous les équipements sont conservées. Les états de lecture
affichent Chargement de la référence... avec des valeurs annoncées poliment.

## Contrats backend vérifiés

- [Sites](../backend/app/api/routes/sites.py) : GET paginé filtré par company_id,
  et GET `/api/v1/sites/{site_id}`.
- [Équipements](../backend/app/api/routes/equipment.py) : GET paginé filtré par
  site_id, et GET `/api/v1/equipments/{equipment_id}` ; 404 si absent.
- GET `/api/v1/companies/{id}` déjà disponible dans ReferenceDataApiService.
- Les deux lectures détail Site/Equipment sont ajoutées au service de références
  frontend existant. Aucun endpoint backend n'est ajouté.
- [Contrat Dashboard](../backend/app/schemas/dashboard.py) : les derniers relevés
  exposent equipment_id, sans nom/code équipement.
  Le [repository](../backend/app/repositories/dashboard_repository.py) produit
  une ligne par capteur du périmètre, y compris sans mesure au calcul.
  Aucun plafond de lignes ni endpoint de résolution par lot d'identifiants
  n'a été constaté. Les horodatages et agrégations restent inchangés.

## Snapshot appliqué et résolution des références

DashboardFacade conserve son snapshot figé des filtres, sa validation et ses
requêtes existantes sans modification. DashboardComponent transmet à la façade
les mêmes filtres. Uniquement si l'application est acceptée, il capture les
références déjà chargées dans les filtres, toutes pages accumulées comprises.

DashboardReferences est local à la page, comme la façade. Il copie immédiatement
les libellés et leurs identifiants, sans conserver une dépendance réactive aux
contrôles éditables. Les correspondances utilisent l'identifiant exact et, pour
les enfants, les relations Site.company_id et Equipment.site_id applicables.
Les identifiants du scope retourné doivent correspondre aux libellés capturés ;
une autre référence n'est jamais utilisée comme repli.

Si une référence sélectionnée manque aux pages chargées, une lecture détail
ciblée est utilisée. Il n'est pas nécessaire de parcourir tout le catalogue.
Les erreurs réseau/404/serveur, un identifiant retourné différent ou un parent
incohérent produisent un libellé indisponible, sans identifiant visible.
Les flux switchMap annulent les anciennes résolutions au changement de
périmètre. DestroyRef nettoie les abonnements à la destruction de la page.

Une modification de filtre non appliquée ne change aucun libellé des résultats.
Actualiser conserve les filtres et libellés appliqués. Une nouvelle application
crée un nouveau snapshot. Le format des dates, le mode simple/avancé, la période
initiale/recalée de 168 heures, le début inclus et la fin exclusive ne changent
pas. DashboardApiService et les calculs/KPI ne sont pas modifiés.

## Derniers relevés et coût des lectures

Les équipements déjà chargés sont copiés dans un cache local au périmètre
appliqué. Ce cache est partagé avec la référence équipement du périmètre.
Les derniers relevés réutilisent leurs identifiants internes sans modifier les
mesures, valeurs, unités, qualités, âges ou dates.

Les identifiants manquants sont dédupliqués avant toute lecture. Une résolution
déjà en cours est partagée par shareReplay ; succès et échecs restent en cache
pour ce snapshot, y compris lors d'Actualiser. Il n'y a ni lecture par ligne
de capteur, ni relance automatique, ni chargement du catalogue complet.
Au maximum quatre lectures ciblées s'exécutent simultanément.

Une nouvelle application annule les résolutions des anciens relevés et réinitialise
le cache. Les relevés rattachés à un ancien snapshot sont ignorés. Les lectures
ciblées vérifient l'identifiant exact et le site lorsqu'un site est appliqué.
Sans filtre Site, le périmètre des relevés reste celui validé par le backend
Dashboard ; cette présentation ne constitue pas une autorisation multi-entreprises.

Limite : en l'absence d'endpoint par lot, U équipements distincts non chargés
nécessitent U GET ciblés, et non un nombre constant de requêtes. La concurrence
est bornée, pas ce total. Cette solution évite les doublons par capteur ; elle
ne prétend pas éliminer tout coût proportionnel aux équipements inconnus.
Pour un très grand parc, enrichir ultérieurement le contrat Dashboard ou prévoir
une résolution par lot nécessiterait une décision backend hors de cette étape.
Aucun cache global, nouvelle dépendance ou architecture de catalogue n'est ajouté.

## Liste Sites

Seuls les libellés de présentation changent. Sélection, accumulation des pages
d'entreprises, focus, liens de détail, paramètres URL, recherche explicite,
annulation des requêtes et pagination serveur restent ceux de UI 4.3/UI 4.4.
Le tri backend reste fondé sur les identifiants croissants, sans être présenté
comme un contrôle de tri métier. Les totaux/pages absents ne sont pas inventés.
L'état Aucun résultat, son explication et son action Effacer la recherche sont
conservés ; la pagination reste masquée pour zéro site, conformément à UI 4.3.1.

## Fichiers de cette intervention

Les chemins frontend ci-dessous sont relatifs à `frontend/src/app/` :

- `shared/utils/business-reference-label.ts` et `.spec.ts` : libellé métier commun.
- `core/api/reference-data-api.service.ts` et `.spec.ts` : lectures détail ciblées.
- `features/dashboard/dashboard-references.ts` et `.spec.ts` : snapshots et cache.
- `features/dashboard/components/dashboard-filters/dashboard-filters.component.ts`
  et `.html` : exposition des références chargées et options sans répétition.
- `features/dashboard/pages/dashboard/dashboard.component.ts`, `.html` et
  `.spec.ts` : capture à l'application et affichage des références.
- `features/dashboard/components/measurement-summary/measurement-summary.component.ts`,
  `.html` et `.spec.ts` : noms d'équipements et messages indisponibles des relevés.
- `features/sites/pages/sites-list/sites-list.component.ts`, `.html` et `.spec.ts` :
  options, résumé et libellés singulier/pluriel.
- `docs/ui-4.4.2-business-identifiers.md` : présent rapport.

Soit 18 fichiers concernés, dont cinq nouveaux. Les fichiers des fiches détail,
les routes et le SCSS des étapes précédentes ne sont pas modifiés par UI 4.4.2.

## Tests et validations exécutés

Validation finale séquentielle, sans concurrence build/tests :

| Commande | Résultat de cette intervention |
| --- | --- |
| `node node_modules/@angular/cli/bin/ng.js test --watch=false` | 502 tests réussis, 39 fichiers, départ 19:20:06 UTC, durée 17,40 s |
| `node node_modules/@angular/cli/bin/ng.js build --configuration production --output-path tmp/ui-4.4.2/production` | Réussi à 19:20:54 UTC, durée 11,264 s ; avertissement de budget connu |
| `node --test scripts/apply-nebular-sass-fix.test.mjs` | 5 tests réussis, 0 échec |
| `node scripts/verify-nebular-breakpoints.mjs` | Dart Sass 1.97.3 ; quatre expressions, huit breakpoints, media queries et thème unique vérifiés |
| `npm ls --all` | Code de sortie 0, arbre valide |
| `npm audit --json` | Code de sortie 0, aucune vulnérabilité, toutes sévérités à zéro |
| `git diff --check` | Réussi |

Le premier accès audit depuis la sandbox a échoué sur DNS ENOTFOUND ; la
commande autorisée avec accès réseau a ensuite réussi. Aucun package n'est
installé ou modifié. Les journaux finaux sont dans `frontend/tmp/ui-4.4.2/`,
ignoré par Git. Les exécutions de développement précédentes ne sont pas attribuées
à cette validation finale.

Les 34 tests supplémentaires par rapport aux 468 de UI 4.4.1 couvrent notamment :
libellés identiques/différents/absents, références chargées et hors première page,
paramètres HTTP et millisecondes inchangés, périmètre appliqué face aux brouillons,
actualisation, erreur de scope, références 404/réseau/serveur, parents incohérents,
annulation et destruction, cache partagé, lectures dédupliquées et concurrence
limitée à quatre. Sites couvre le singulier/pluriel, l'absence de métadonnées,
le filtre numérique et l'URL conservés. Les contrôles existants de recherche,
pagination, retour détail, Companies, Dashboard, Shell et 404 restent valides.

## Contrôles navigateur et captures

Build production servi localement avec réponses HTTP simulées et journal GET.
Aucune connexion FastAPI réelle ni PostgreSQL, aucune écriture réelle.
Les deux pages sont contrôlées à 1440, 1024, 1023, 768, 390 et 320 px :
absence de débordement horizontal global, libellés lisibles, champs/valeurs
associés et absence de texte identifiant technique dans les résultats.
Les seuils du Shell et la Sidebar restent cohérents.

Parcours contrôlés : application au clavier, brouillon équipement non appliqué
sans changement du résultat, références équipements 50/51 puis 51/51 chargées,
relevés de deux capteurs partageant un équipement hors première page, recherche
Sites, page suivante, détail et retour au clavier avec company_id/page/page_size,
singulier 1 site/1 page, état vide sans pagination et erreur entreprise explicite.
Focus clavier visible vérifié sur Effacer la recherche. Chargement de référence
observé ; erreurs HTTP et annulations également couvertes en tests simulés.
Console navigateur sans erreur ni avertissement sur les parcours contrôlés.

Le journal contient un GET `/equipments/13` pour chacune de deux applications
distinctes sans cette référence chargée ; aucune lecture `/equipments/12` pour
l'équipement déjà chargé. Les deux relevés de l'équipement 13 partagent leur GET.
Aucun POST, PATCH ou DELETE.

Captures conservées hors dépôt dans le dossier de visualisation de cette tâche :

- `ui-4.4.2-dashboard-results-1440.jpg` : périmètre appliqué et synthèse.
- `ui-4.4.2-dashboard-{1024,1023,768,390,320}.jpg` : résultats responsive.
- `ui-4.4.2-readings-1440.jpg` et `ui-4.4.2-readings-320.jpg` : derniers relevés.
- `ui-4.4.2-sites-{1440,1024,1023,768,390,320}.jpg` : liste et pagination.
- `ui-4.4.2-sites-singular-1440.jpg`, `ui-4.4.2-sites-empty-320.jpg`
  et `ui-4.4.2-sites-error-320.jpg` : singulier, absence de résultat et erreur.

Les captures Dashboard cadrent les résultats et relevés dans la page ; aucune
image de maquette ne remplace le rendu du build. Le serveur temporaire est arrêté
et le viewport restauré. Lecteur d'écran réel, appareil physique et zoom réel
200/400 % ne sont pas revendiqués.

## Bundles et état Git final

Comparaison avec les artefacts locaux UI 4.4.1, sans nouveau build de référence :

| Mesure brute | UI 4.4.1 | UI 4.4.2 | Écart |
| --- | ---: | ---: | ---: |
| Initial | 601 281 octets | 601 509 octets | +228 octets |
| Dashboard différé | 49 388 octets | 52 700 octets | +3 312 octets |
| Liste Sites différée | 16 835 octets | 17 177 octets | +342 octets |
| Fiche Site différée | 8 005 octets | 8 005 octets | 0 |
| Fiche Company différée | 7 699 octets | 7 699 octets | 0 |
| Shell différé | 14 759 octets | 14 759 octets | 0 |
| Ensemble JS/CSS | 743 815 octets | 747 955 octets | +4 140 octets |

L'initial représente 601,51 ko, soit un dépassement de 101,51 ko du budget de
500 ko conservé. L'augmentation initiale est d'environ 0,038 %. Aucun budget,
dépendance, code backend, contrat HTTP ni calcul métier n'est modifié.
La sécurité multi-entreprises reste une limite backend existante.

Branche et HEAD inchangés. Aucun changement indexé. Le dépôt contient 22 fichiers
suivis modifiés et 10 fichiers nouveaux non suivis, travaux UI 4.4/4.4.1 compris.
Les 17 fichiers présents avant cette étape sont préservés. Validation utilisateur
attendue avant toute opération Git de livraison.
