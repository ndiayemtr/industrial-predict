# UI 8.7 - Livraison Maintenance MVP de consultation

24 octobre 2026. Branche `feature/frontend-maintenance`, HEAD `d71774c`.
Dépôt propre avant cette étape exclusivement documentaire. Aucun test, build,
appel DEV, accès PostgreSQL ou opération Docker exécuté en UI 8.7.

## Périmètre livré

MAIN-01 à MAIN-16 approuvées pour la lecture seule dans la
[conception UI 8.1](etape-ui-8.1-maintenance.md). MAIN-08/09 n'autorisent aucune
écriture ou transition ; création, modification et workflow nécessitent un chantier
séparé après arbitrage métier et sécurisation backend.

- Routes lazy `/maintenance` et `/maintenance/:maintenanceId` sous le Shell.
- Sélection explicite Company -> Site -> Equipment, catalogues paginés avec suite,
  aucune sélection automatique. Vérification Equipment -> Site -> Company réelle,
  contradiction bloquante sans remplacement d'identité ni requête élargie.
- GET liste uniquement après validation complète du contexte. Filtres
  maintenance_type, status, priority, search ; recherche explicite et distinction
  brouillon/filtres appliqués. Pagination serveur, tri fixe created_at DESC/id DESC.
- Période de création sur **created_at**, intervalle **[début, fin)** ; ne filtre
  ni planned_at, ni started_at, ni completed_at. Bornes avec offset, calendrier,
  heure UTC et fractions ; microsecondes et offsets préservés sans Date.
- Six colonnes sans ID ni Actions ; titre réel cliquable vers le détail,
  badges textuels statut/priorité, vides/erreurs/page hors plage distingués.
- Détail de **18 champs réels** : id, equipment_id, maintenance_type, status,
  priority, title, description, failure_code, root_cause, action_taken, technician,
  planned_at, started_at, completed_at, downtime_minutes, cost, created_at, updated_at.
  Null et zéro distingués, aucune valeur de remplacement inventée. Coût sans
  devise garantie ; indisponibilité déclarée distincte d'une durée calculée.
- Dates métier avec offset ; dates administratives potentiellement naïves
  conservées et signalées sans ajout de Z ni supposition UTC. ISO source accessible.
- Maintenance -> Equipment par equipment_id réellement résolu, parents connus
  seulement ; erreur de référence séparée, dossier conservé si un parent échoue.
- Equipment -> Maintenance après chaîne complète vérifiée, ids réels,
  page=1/page_size=20, aucun statut/criticité/recherche Equipment transféré.
- Retour local explicite à la liste, même en accès direct, contexte industriel,
  filtres appliqués, pagination, fractions, offsets, paramètres répétés et fragment
  préservés ; aucune URL externe de retour suivie.
- Actions de 44 px harmonisées, focus clavier visible, responsive et défilement
  local du tableau. Aucun formulaire ni POST, PATCH, DELETE ou transition frontend.
  Le type déclaré **predictive n'est pas une preuve de prédiction IA**.

## Architecture et périmètre transversal

Réutilisation de Page<T>, ReferenceDataApiService, HttpClient, composants
PageHeader/LoadingState/EmptyState/ErrorState, services de référence et Shell.
MaintenanceListFacade locale avec signals/switchMap et annulation des lectures
obsolètes ; états locaux pour le détail. MaintenanceApiService expose seulement
list et getById, deux GET /api/v1/maintenance et /api/v1/maintenance/{id}.
Whitelist reconstruite : equipment_id, page, page_size, maintenance_type, status,
priority, search, start_time, end_time. Alias HTTP status, aucun company_id/site_id.
Réponses et appartenance validées défensivement sans page vide ni zéro synthétiques.
Utilitaires temporels précis de Measurements réutilisés, sans changement de contrat.
Backend existant FastAPI -> services -> repositories -> PostgreSQL inchangé.

Examen du diff transversal main...HEAD :

- `_buttons.scss` : ajout de maintenance-back et equipment-maintenance aux
  interactions et au mouvement réduit ; aucun changement du contrat des composants shared.
- `_actions.scss` : inchangé, mixin navigation-action réutilisée par détail et lien
  Equipment ; SCSS Equipment regroupe la nouvelle action avec Voir les capteurs.
- Equipment Detail : industrialQuery partagé entre Sensors et Maintenance,
  références déjà résolues, aucun appel supplémentaire sur la fiche ; ordre des
  actions existantes conservé. Tests de navigation dédiés ajoutés.
- Routes racines et tests Sidebar : chargement lazy Maintenance et non-régression.
- Finition Measurements `161bf88` incluse intentionnellement : HTML/SCSS et test de
  disposition des actions temporelles sous six champs, aucune logique métier modifiée.
- Aucun changement backend, schéma SQL, migration, Docker, package ou budget.

## Preuves historiques, sans nouvelle exécution

| Catégorie | Preuve validée | Limite |
| --- | --- | --- |
| Tests Angular UI 8.5 | **741 tests ciblés réussis**, **1 899 tests complets réussis** | HTTP simulé, pas une recette SQL |
| Build UI 8.5 | **Production réussi**, initial **606,00 kB**, Equipment Detail **14,79 kB** | Budget initial historique dépassé ; budgets inchangés |
| Visuel utilisateur UI 8.5 | **9 contrôles sur 9** | Déclaration utilisateur, distincte des captures et mesures de l'agent |
| Contrôles HTTP UI 8.5 | Cinq GET HTTP 200 indépendants | Aucune capture XHR brute ; pas de bilan SQL global à cette étape |
| HTTP UI 8.6 | **36 GET HTTP de contrôle**, tous 200, dont **27 cas de liste comparés à SQL**, trois détails et six références | Requêtes indépendantes des XHR du navigateur |
| Angular UI 8.6 | **30 états Angular** relevés | Pages/DOM, pas des traces réseau |
| Comparaisons UI 8.6 | **Trois interventions et leurs 18 champs** API/SQL/DOM concordants | Jeu DEV limité, pas de données synthétiques ajoutées |
| Intégrité SQL UI 8.6 | **40 lignes avant/après**, empreintes des **huit tables et par ligne identiques**, aucune ligne ajoutée/supprimée/modifiée | Instantanés en lecture seule, pas une garantie de production |

Sources conservées : [UI 8.2](ui-8.2-maintenance-data-access.md),
[UI 8.3 et finitions](ui-8.3-maintenance-list.md),
[UI 8.4 et UI 8.4.1](ui-8.4-maintenance-detail.md),
[UI 8.5](ui-8.5-maintenance-navigation.md),
[UI 8.6](ui-8.6-maintenance-integration.md). Tous ces rapports et UI 8.1 restent
inchangés. Les artefacts locaux ignorés mentionnés dans les rapports historiques
ne font pas partie du livrable Git. Aucune preuve historique n'est présentée
comme réexécutée pendant UI 8.7.

Responsive historique : 1440, 1024, 1023, 768 et 320 px exacts ; cible 390 px
vérifiée à **389/391 px**. Aucun débordement global relevé, tableau défilable
localement. Focus et clavier contrôlés selon les rapports ; revue lecteur d'écran
non exhaustive, certaines captures tablette/mobile indisponibles côté agent.
CSS après UI 8.4.1 : détail 1 767 octets et liste 3 952 octets, mesure locale
compilée/minifiée avec saut de ligne, distincte du chunk encapsulé. Référence chunk
détail UI 8.4.1 : 16,40 kB. Aucun nouveau warning SCSS signalé au build UI 8.5.
Budgets historiques : initial warning 500 kB/erreur 1 MB ; composant 4/8 kB.
Initial 606,00 kB : dépassement de 106,00 kB du seuil d'avertissement.

## Limites et dettes ouvertes

| Réserve | Conséquence conservée |
| --- | --- |
| B-MAIN-01 | PATCH backend sans revalidation du dossier fusionné, chronologie et réponse Read potentiellement incohérentes |
| B-MAIN-02 | Divergences Pydantic/SQL : null, NOT NULL, longueurs, non-blanc et ids |
| B-MAIN-03 | Non-finis, coercitions numériques, limites SQL des minutes et précision monétaire |
| B-MAIN-04 | Transitions et dates exigées, réouverture/verrouillage non arbitrés |
| B-MAIN-05 | Erreurs transactionnelles/rollback, concurrence, idempotence et réponse après commit insuffisamment maîtrisées |
| B-MAIN-06 | Dates administratives potentiellement naïves, absence de garantie UTC en base |
| B-MAIN-07 | Authentification, autorisation par ressource et isolation multi-tenant absentes |
| B-MAIN-08 | COUNT/offset, indexation et cohérence des pages à évaluer aux volumes réels |
| B-MAIN-09 | Coût sans devise garantie, précision, audit/version et conservation à définir |

Aucune anomalie B-MAIN-01 à B-MAIN-09 résolue par ce MVP de consultation.
Les contrôles Angular ne sécurisent pas le backend.

- Aucun XHR brut : blocage réseau avant parents/période invalide couvert par tests
  simulés, pas revendiqué comme observation réseau réelle.
- Pagination/tri multiligne non représentés : une intervention par équipement.
  Page hors plage et récupération réelle contrôlées, pas d'historique volumineux.
- Fractions temporelles stockées non nulles et dates administratives naïves
  Maintenance absentes du jeu DEV disponible. Bornes de requête à six décimales
  testées ; ces preuves ne se substituent pas à des réponses historiques précises.
- Certaines valeurs enum et cas zéro/non-finis/textes vides seulement simulés ou
  absents ; aucune donnée DEV modifiée pour les fabriquer. Couverture PostgreSQL
  spécifique incomplète, pas de test réel de charge ou de concurrence.
- Seed strict historiquement non conforme sur Sensor ID 1, description
  `Capteur fictif`, updated_at `2026-10-20T22:11:55.315993` conservés. Seed et
  contrôle inchangés ; aucun succès du seed check strict revendiqué.
- Dialogue natif d'abandon des modules d'écriture concernés non vérifié/revalidé
  manuellement. Maintenance ne propose aucun formulaire métier d'écriture.
- Budget initial dépassé et réserve responsive 390 px conservés.
- Secrets historiques déjà signalés dans les rapports projet : externalisation
  et renouvellement à traiter séparément ; aucune nouvelle valeur sensible incluse.

Ces réserves permettent une livraison du MVP de consultation en DEV dans le
périmètre validé, **pas une déclaration de SaaS multi-entreprise prêt en production**.
Aucune nouvelle écriture, nouvelle recette ou correction de données en UI 8.7.

## Comparaison Git locale et commits exacts

Références lues le 24 octobre 2026, sans fetch :

| Référence | HEAD | Comparaison |
| --- | --- | --- |
| feature/frontend-maintenance | d71774c | Six commits devant main, aucun retard |
| main | 74a24e4 | UI 8.1 déjà intégrée ; un commit devant origin/main |
| origin/main (référence locale) | 15c956b | Ne représente pas une interrogation récente du serveur distant |

`feature/frontend-maintenance..main` est vide. `main..feature/frontend-maintenance`
contient exactement, du plus ancien au plus récent :

```text
740a947 feat(frontend): add Maintenance data models and API integration
d74a3e6 feat(frontend): implement Maintenance list and filters
161bf88 style(frontend): align Measurements period actions
c66e7f3 feat(frontend): implement Maintenance detail and navigation
b51d20e feat(frontend): complete Equipment to Maintenance navigation
d71774c docs(frontend): validate Maintenance DEV integration
```

`origin/main..feature/frontend-maintenance` contient ces six commits plus
`74a24e4 docs(frontend): design Maintenance read-only MVP`, déjà dans main local.
Le commit UI 8.1 est donc compté une seule fois : sept commits depuis origin/main,
six depuis main. `feature/frontend-maintenance..origin/main` est vide.
main est ancêtre de HEAD : fast-forward possible sur ces références locales.
Le futur commit documentaire UI 8.7 n'existe pas encore et n'est pas inclus dans
ces nombres de commits.

## Inventaire exact des fichiers à intégrer

Diff engagé `main...HEAD` : **34 fichiers**, 3 107 insertions, 10 suppressions.
Diff engagé `origin/main...HEAD` : **35 fichiers**, le fichier supplémentaire
étant docs/etape-ui-8.1-maintenance.md déjà intégré dans main local.

UI 8.7 modifie exactement six documents existants et crée ce rapport :

- `README_AI.md`
- `frontend/README.md`
- `docs/project-status.md`
- `docs/roadmap.md`
- `docs/architecture.md`
- `docs/frontend-architecture.md`
- `docs/ui-8.7-maintenance-delivery.md`

Périmètre cumulé préparé pour main, après un futur commit UI 8.7 autorisé :
**41 fichiers distincts**, dont 13 documents et 28 fichiers frontend, tests inclus.
Le diff par rapport à origin/main porterait sur **42 fichiers**, UI 8.1 comprise.
Les nombres incluent la finition Measurements et évitent de recompter UI 8.1.
Liste exhaustive des 41 chemins :

```text
README_AI.md
docs/architecture.md
docs/frontend-architecture.md
docs/project-status.md
docs/roadmap.md
docs/ui-8.2-maintenance-data-access.md
docs/ui-8.3-maintenance-list.md
docs/ui-8.4-maintenance-detail.md
docs/ui-8.5-maintenance-navigation.md
docs/ui-8.6-maintenance-integration.md
docs/ui-8.7-maintenance-delivery.md
docs/ux-measurements-period-actions.md
frontend/README.md
frontend/src/app/app.routes.spec.ts
frontend/src/app/app.routes.ts
frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.html
frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.scss
frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts
frontend/src/app/features/equipments/pages/equipment-detail/equipment-maintenance-navigation.spec.ts
frontend/src/app/features/maintenance/data-access/maintenance-api.service.spec.ts
frontend/src/app/features/maintenance/data-access/maintenance-api.service.ts
frontend/src/app/features/maintenance/maintenance-list.facade.spec.ts
frontend/src/app/features/maintenance/maintenance-list.facade.ts
frontend/src/app/features/maintenance/maintenance.routes.spec.ts
frontend/src/app/features/maintenance/maintenance.routes.ts
frontend/src/app/features/maintenance/models/maintenance-page-query.model.ts
frontend/src/app/features/maintenance/models/maintenance-state.model.ts
frontend/src/app/features/maintenance/models/maintenance.model.ts
frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.html
frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.scss
frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.spec.ts
frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.ts
frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.html
frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.scss
frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.spec.ts
frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.ts
frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.html
frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.scss
frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts
frontend/src/app/layout/sidebar/sidebar.component.spec.ts
frontend/src/styles/_buttons.scss
```

## Checklist de fusion fast-forward, à exécuter seulement après autorisation

- [x] Branche/HEAD/dépôt propre initial vérifiés ; références main et origin/main lues localement.
- [x] Rapports UI 8.1 à UI 8.6 préservés, preuves et réserves reportées sans nouvelle recette.
- [x] Diff transversal de styles/actions, Equipment et finition Measurements examiné.
- [x] Périmètre Git contrôlé : aucun backend, SQL, Docker, package, capture, dump ou artefact temporaire ajouté.
- [x] Liens documentaires locaux et git diff --check contrôlés en UI 8.7.
- [ ] Valider ce dossier, puis autoriser séparément le commit documentaire des sept fichiers.
- [ ] Ajouter explicitement ces sept documents ; inspecter diff --cached --stat et --check avant commit.
- [ ] Vérifier dépôt propre et HEAD réel après commit ; recalculer les écarts si une référence a évolué.
- [ ] Vérifier l'état distant avant livraison sur autorisation, sans supposer origin/main à jour.
- [ ] Obtenir l'autorisation distincte de fusion ; vérifier main ancêtre du HEAD final.
- [ ] Sur main propre, exécuter uniquement la fusion autorisée avec --ff-only de feature/frontend-maintenance ; arrêter en cas de divergence.
- [ ] Vérifier log, status et inclusion des commits, sans nouveau commit de merge.
- [ ] Publication éventuelle séparément autorisée ; aucun push prévu dans UI 8.7.

Cette liste ne déclenche aucune commande de mutation Git. Pas de rebase ni
résolution automatique de divergence. UI 9 non commencée.

## État Git de livraison documentaire

Branche feature/frontend-maintenance, HEAD **d71774c inchangé**, index vide.
Six documents de suivi modifiés et un rapport nouveau, exactement sept fichiers
documentaires. git diff --check réussi ; aucun fichier exécutable modifié dans
cette étape. Références et cibles locales des liens contrôlées sans accès réseau.
Aucun test, build, accès PostgreSQL ou Docker, commit, push, merge ou rebase.
En attente de validation avant le commit documentaire final.
