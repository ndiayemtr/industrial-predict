# UI 4.2 - Modèles et intégration HTTP Sites

Date : 16 octobre 2026. Branche `feature/frontend-sites`, HEAD de référence
`1630ebc`, dépôt propre avant intervention. Statut : implémenté, en attente de
validation. Aucun commit, push ou merge ; UI 4.3 non commencée.

## Contrats backend utilisés

Relecture directe des [schémas Site](../backend/app/schemas/site.py),
[routes](../backend/app/api/routes/sites.py),
[service](../backend/app/services/site_service.py),
[repository](../backend/app/repositories/site_repository.py) et
[tests pagination/filtres](../tests/pagination_filters/test_routes.py), en
complément de la [conception validée](etape-ui-4.1-sites.md).

- GET `/api/v1/sites` retourne Page[SiteRead] ; page >= 1 (défaut 1), page_size
  entre 1 et 100 (défaut 20), company_id facultatif côté backend et >= 1,
  search facultatif de 1 à 100 caractères. Recherche nom/code via ILIKE,
  combinée au filtre entreprise, tri id croissant. Le service backend retire
  les espaces périphériques ; les jokers %/_ ne sont pas échappés.
- GET `/api/v1/sites/{id}` retourne SiteRead, ou 404 si absent.
- POST `/api/v1/sites` exige name, code et company_id ; description facultative
  nullable. Succès 201 avec SiteRead.
- PATCH `/api/v1/sites/{id}` applique les seuls champs fournis. Le backend
  autorise company_id, mais le DTO et le service MVP frontend l'excluent.
  Succès 200 avec SiteRead ; absence et null restent distincts.
- Le code est unique globalement. Un 409 peut provenir d'un doublon ou d'une
  entreprise inexistante ; aucune interprétation ou association à un champ
  n'est introduite dans le transport frontend.
- Les schémas PATCH acceptent name/code null, malgré les contraintes SQL NOT
  NULL. Les types conservent cette possibilité de transport pour les champs
  éditables ; les futurs formulaires devront empêcher ces entrées. La couche
  HTTP ne prétend pas corriger les validations backend.

Le filtre entreprise obligatoire dans SiteListQuery est une règle de sélection
du MVP, pas une autorisation multi-tenant. Les limites de sécurité, la cascade
DELETE et l'interdiction de transfert du MVP restent celles d'UI 4.1.
Aucun appel réel FastAPI et aucune écriture PostgreSQL pour cette étape.

## Modèles et méthodes implémentés

SiteRead est réutilisé depuis `core/models/reference-data.model.ts` après
comparaison de ses sept champs avec SiteRead Pydantic : id, name, code,
description nullable, company_id, created_at et updated_at. Les horodatages
restent des chaînes source ; aucune conversion, normalisation ou décoration.
Aucun nouveau modèle de lecture ni état UI anticipé.

| Élément | Contrat frontend |
| --- | --- |
| SiteCreate | name/code chaînes requises, company_id nombre requis, description facultative chaîne ou null |
| SiteUpdate | name/code/description facultatifs et nullables ; aucune propriété company_id |
| SiteListQuery | Réutilise ReferencePageQuery (page/page_size/search) et impose company_id |
| SitesApiService.list(query) | Délègue à ReferenceDataApiService.getSites(query.company_id, query) ; GET paginé, pas de route non paginée /sites/company/... |
| getById(id) | GET détail, aucun filtre ajouté ni transformation de réponse |
| create(body) | POST, corps transmis sans trim ou changement de casse/description |
| update(id, body) | PATCH des seuls name/code/description fournis ; whitelist explicite, pas de transfert ni de dates administratives envoyées |
| ReferenceDataApiService.getCompanyById(id) | GET /api/v1/companies/{id}, pour les futures références Sites sans dépendance sur la feature Companies |

La whitelist PATCH protège aussi contre les propriétés supplémentaires d'une
variable structurellement compatible en TypeScript, par exemple un SiteRead.
Le corps original n'est pas modifié. Null explicite et chaîne vide sont
conservés, un champ absent reste absent. Un PATCH vide est transporté comme
tel ; la détection des différences sera la responsabilité du futur formulaire.
Les services ne contiennent ni souscription interne, cache, retry automatique,
méthode DELETE, transfert d'entreprise, validation de formulaire ou mapping
d'erreur métier. Les réponses et les corps d'erreur HTTP restent inchangés.

La pagination n'est pas recalée silencieusement ; le service transmet aussi
les limites invalides pour laisser FastAPI produire son 422. Les futurs
contrôles UI appliqueront leurs validations avant appel. Search vide est omis
comme dans les références et Companies ; search non vide est transmis intact.

## Fichiers concernés

Créés sous `frontend/src/app/features/sites/` :

- `models/site-write.model.ts`.
- `models/site-list-query.model.ts`.
- `data-access/sites-api.service.ts`.
- `data-access/sites-api.service.spec.ts`.

Modifiés : `frontend/src/app/core/api/reference-data-api.service.ts` et son
fichier `.spec.ts`, uniquement pour la lecture de référence entreprise par id.
Aucun fichier Companies, Dashboard, route ou composant modifié.

Documentation : ce rapport, README_AI.md, project-status.md, roadmap.md et
deux précisions dans la conception UI 4.1 (signature list(query) et DTO PATCH
MVP limité aux trois champs). Aucun changement de périmètre fonctionnel validé.

## Tests et validations exécutés

Exécutions séquentielles depuis `frontend`, sans build concurrent aux tests :

| Commande | Résultat de cette exécution |
| --- | --- |
| `node node_modules/@angular/cli/bin/ng.js test --watch=false` | 418 tests réussis, 33 fichiers ; Vitest démarré à 17:03:52 UTC, durée 25,32 s |
| `node node_modules/@angular/cli/bin/ng.js build --configuration=production --output-path=tmp/ui-4.2/production` | Réussi, terminé à 17:04:56 UTC ; avertissement de budget initial conservé |
| `node --test scripts/apply-nebular-sass-fix.test.mjs` | 5 tests réussis, 0 échec |
| `node scripts/verify-nebular-breakpoints.mjs` | Dart Sass 1.97.3 : quatre expressions, huit breakpoints, media queries et thème unique vérifiés |
| `npm ls --all` | Code de sortie 0, arbre de dépendances valide |
| `npm audit --json` | Code de sortie 0, 0 vulnérabilité dans toutes les sévérités |
| `git diff --check` | Réussi |

Les 32 nouveaux tests correspondent à 28 cas Sites et quatre cas de référence
entreprise. HttpTestingController intercepte exclusivement les requêtes simulées :
méthodes/URL, params, limites acceptées et refus 422 simulé, types requis et
exclusion company_id, corps JSON POST/PATCH, omission/null/vide, Unicode et
espaces, réponse paginée/détail, dates sans fuseau et avec offset/fractions,
absence de DELETE et de retry, 404/409/422/500 et réseau. Les deux causes connues
de 409 et un conflit non précisé sont propagés sans transformation.
Les suites Companies, Dashboard, routing, Shell et Sidebar restent dans les
418 tests ; aucun test n'est supprimé ou contourné.

Le premier audit a échoué sur la résolution DNS du registre dans le bac à
sable ; la relance avec accès réseau a réussi. Les commandes Angular ont utilisé
les permissions nécessaires au cache Vitest/aux processus de build Windows.
Ni dépendance installée, ni lockfile, ni budget modifié.

## Bundles et limites

- Initial : **600 894 octets (600,89 ko)**, identique au bilan précédent.
  Budget d'avertissement 500 ko, dépassement connu 100,89 ko, seuils inchangés.
- Dashboard différé : **49,39 ko** ; liste Companies **12,57 ko**, détail
  **7,79 ko**, formulaire **17,17 ko**, Shell **14,76 ko**.
- Total JS/CSS initial et différé : **717 645 octets**, contre 717 583 octets
  dans le bilan précédent, soit **+62 octets**, dans le chunk partagé de références.
- SitesApiService n'est encore consommé par aucune page ; il n'ajoute pas de
  chunk de page Sites. Aucun gain de taille future n'est garanti.

Les journaux sont conservés dans `frontend/tmp/ui-4.2/` (ignoré par Git) :
tests.log, build.log, sass-tests.log, sass-check.log, npm-ls.log et npm-audit.json.
Le bilan de référence précédent est historique, pas un nouveau build de base.
Pas de validation visuelle nécessaire à cette étape sans écran. Les preuves
sur les écritures réelles et l'accessibilité restent à établir lors des étapes
ultérieures ; aucun résultat simulé n'est présenté comme une preuve PostgreSQL.

La prochaine action est la validation d'UI 4.2. Aucun commit, push ou merge
effectué ; aucune implémentation UI 4.3 commencée.
