# UI 8.2 - Modèles et accès API Maintenance

23 octobre 2026. Branche feature/frontend-maintenance, HEAD initial et final
74a24e4, dépôt propre au départ. Couche de données uniquement, selon
[MAIN-01 à MAIN-16 validées](etape-ui-8.1-maintenance.md). Aucun écran, route,
navigation, façade anticipée, état UI ou écriture. UI 8.3 non commencée.

## Fichiers et contrat

Cinq fichiers nouveaux, aucun fichier existant modifié :

- [maintenance.model.ts](../frontend/src/app/features/maintenance/models/maintenance.model.ts) :
  MaintenanceRead, les trois unions strictes et MaintenancePage = Page<MaintenanceRead>.
- [maintenance-page-query.model.ts](../frontend/src/app/features/maintenance/models/maintenance-page-query.model.ts) :
  query propre à Maintenance, equipment_id obligatoire côté Angular.
- [maintenance-api.service.ts](../frontend/src/app/features/maintenance/data-access/maintenance-api.service.ts) :
  uniquement list et getById, Observable froids et validation défensive.
- [maintenance-api.service.spec.ts](../frontend/src/app/features/maintenance/data-access/maintenance-api.service.spec.ts) :
  tests de types, transport, données et erreurs avec HttpTestingController.
- Le présent rapport.

Lecture ciblée des [schémas](../backend/app/schemas/maintenance.py),
[enums](../backend/app/core/enums.py), [routes](../backend/app/api/routes/maintenance.py),
[Page](../backend/app/schemas/pagination.py) et [construction paginée](../backend/app/core/pagination.py),
plus modèles/services/tests Measurements et conventions Equipment : aucune
contradiction constatée avec UI 8.1. Aucun nouvel audit complet du backend.

Les **18 champs** sont id, equipment_id, maintenance_type, status, priority,
title, description, failure_code, root_cause, action_taken, technician, planned_at,
started_at, completed_at, downtime_minutes, cost, created_at et updated_at.
Les cinq textes facultatifs, trois dates métier, minutes et coût sont nullable ;
aucun champ optionnel manquant n'est remplacé par null ou une valeur par défaut.

Unions exactes : preventive/corrective/predictive, planned/in_progress/completed/
cancelled, low/medium/high/critical. Dates en chaînes ISO sources, sans Date,
devise, code d'intervention ou durée calculée inventés. Aucun DTO Create/Update.

| Méthode | HTTP | Paramètres |
| --- | --- | --- |
| list(query) | GET /api/v1/maintenance | equipment_id requis ; page, page_size, maintenance_type, status, priority, search, start_time, end_time facultatifs |
| getById(id) | GET /api/v1/maintenance/{id} | Aucun filtre ou contexte de retour |

Whitelist reconstruite explicitement, alias HTTP **status**, jamais
maintenance_status. Aucun company_id/site_id, champ de planning, tri, devise ou
filtre supplémentaire transmis. Pas de liste globale, GET non paginé par
Equipment, POST, PATCH, PUT, DELETE ou transition de statut.

## Validation et conservation des données

- Identifiants entiers positifs sûrs, page >=1 et page_size 1..100. Enum exacte,
  sans trim/coercition ; search de 1..100 points de code Unicode, contenu brut
  conservé, y compris espaces et jokers. Le nettoyage de recherche reste au serveur.
- undefined omet les filtres ; null explicite les refuse. Pagination absente :
  aucun paramètre fabriqué, défauts backend conservés. Query non mutée et
  equipment_id capturé à la souscription pour contrôler la réponse.
- Bornes avec offset, jusqu'à six décimales, validation calendaire et comparaison
  entière à la microseconde ; début strictement avant fin. Bornes unilatérales et
  futures autorisées. Aucune borne invalide supprimée pour élargir une requête.
  Chaînes/offsets envoyés inchangés et encodés par HttpParams. Ces filtres portent
  sur created_at, selon le backend, avec intervalle [début, fin).
- Réutilisation directe des fonctions pures measurementInstant et
  validateMeasurementPeriod de l'[utilitaire existant](../frontend/src/app/features/measurements/utils/measurement-time.ts),
  sans modifier Measurements ni dépendre de son API ou de sa façade. Couplage
  technique limité à cet utilitaire ; une extraction commune éventuelle reste
  une évolution séparée, aucune refonte transversale dans cette étape.
- Page : items tableau, métadonnées entières sûres, total/pages >=0,
  page >=1, page_size 1..100, pages conforme à ceil(total/page_size), nombre
  d'items au plus page_size. Pas de recalcul correctif, tri ou déduplication.
  Une page hors plage vide conserve son total ; COUNT/items concurrents ne sont
  pas présentés comme un snapshot transactionnel garanti.
- Chaque ligne vérifie les 18 champs, les enums et les ids ; un autre
  equipment_id dans la liste ou un autre id dans le détail est refusé.
  Coût réellement numérique, fini et >=0 ou null ; minutes entières sûres et
  >=0 ou null. Aucune devise, conversion monétaire ou durée dérivée.
- Dates métier : offset obligatoire si non null ; started_at <= completed_at
  quand les deux existent, égalité permise, comme MaintenanceRead. Aucune règle
  de date obligatoire selon le statut ni ordre imposé à planned_at.
- Dates administratives : format/calendrier validés avec ou sans offset.
  Une chaîne naïve est conservée exactement, fraction comprise, sans ajout de Z,
  hypothèse UTC, comparaison d'instant ou nouveau champ DTO. L'absence d'offset
  reste identifiable dans la source et signalable par les futures pages.

Les défauts/contraintes de formulaire non présents dans Read ne sont pas
inventés : par exemple un titre vide reste une chaîne reçue. Les données valides
sont retournées intactes. Erreurs locales/de réponse : TypeError dans l'Observable,
sans requête pour une entrée invalide ni valeur zéro/page vide de secours.
Erreurs HttpErrorResponse propagées avec statut et corps, sans retry, cache,
toast ou souscription interne ; désinscription annulant la lecture.
L'existence Equipment/Site/Company n'est pas résolue par cette couche : cela
appartiendra à UI 8.3/8.4, pas à une validation d'appartenance multi-tenant.

## Vérifications exécutées

Fixtures HttpTestingController uniquement, aucune API ou base réelle.
Le premier ciblage a échoué à la compilation sur unknown passé à flush pour une
fixture volontairement invalide. Le cast de test est corrigé ; aucun changement
du contrat applicatif. Le ciblage suivant passe sur les sources stabilisées.
La suite complète et le build sont ensuite exécutés **une seule fois chacun**.

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-8.2/vitest.config.mjs --include=src/app/features/maintenance/data-access/maintenance-api.service.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-8.2/vitest.config.mjs
npm.cmd run build -- --configuration production --stats-json
```

| Contrôle final | Résultat |
| --- | --- |
| Tests ciblés | 235 réussis, un fichier |
| Suite Angular complète | 1 717 réussis, 67 fichiers, contre 1 482 de référence |
| Build production | Réussi |
| Initial avant/après | 605 652 octets, soit 605,65 kB ; différence 0 |
| Ensemble JS/CSS avant/après | 1 038 094 octets ; différence 0 |
| Budget initial | Avertissement existant à 500 kB, dépassement 105,65 kB ; budgets inchangés |

Le service n'est référencé par aucune route/page de production : éliminé par
l'optimisation, il ne crée pas encore de chunk Maintenance. Cela ne préjuge pas
du poids lors de l'intégration des futurs écrans. Aucune validation responsive
ou navigation DEV à revendiquer pour cette étape sans UI.

Les tests couvrent URLs, absence de méthodes d'écriture, whitelist/alias, filtres,
ids/pagination invalides, enums, périodes/offsets/microsecondes, Page/hors plage,
18 champs et nullables, non-finis/coercitions, calendrier administratif naïf,
chronologie, identité/périmètre, erreurs HTTP/réseau, annulation et non-mutation.
Les 18 noms de champs ont aussi été comparés statiquement aux schémas backend.
Runner et journaux sont locaux sous frontend/tmp/ui-8.2, ignorés par Git.

## Réserves et état Git

Toutes les anomalies B-MAIN-01 à B-MAIN-09 de UI 8.1 restent ouvertes. Les gardes
de lecture ne corrigent ni les écritures backend, ni les défauts timezone des
dates administratives, ni les erreurs d'intégrité/concurrence. Authentification
et isolation multi-tenant absentes ; cohérence equipment_id ne vaut pas
autorisation. Coût sans devise, précision float et limites SQL restent celles
du contrat. Minutes Read validées comme entier sûr, sans ajouter une contrainte
de formulaire SQL int32 à cette lecture. Couverture PostgreSQL non établie ici,
seed et données historiques non consultés ou modifiés. MAIN-08/09 n'autorisent
aucune écriture ou transition. Les futures pages devront signaler les dates
administratives naïves sans supposer UTC.

HEAD 74a24e4 inchangé, branche feature/frontend-maintenance, index vide,
uniquement les cinq fichiers nouveaux listés. Aucun fichier exécutable existant,
backend, SQL, PostgreSQL, migration, Docker, package, budget ou rapport antérieur
modifié. Contrôles des liens locaux, du périmètre, des espaces et
git diff --check réussis. Aucun secret ou artefact de test dans le périmètre Git.
Aucun commit, push, merge ou rebase. UI 8.3 non commencée.
Validation attendue avant commit.
