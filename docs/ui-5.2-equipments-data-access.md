# UI 5.2 - Modèles et intégration API Équipements

19 octobre 2026, branche `feature/frontend-equipments`. Référence de départ
`667fe5b` ; [conception UI 5.1](etape-ui-5.1-equipments.md) approuvée, EQ-01 à EQ-07 inclus.
Le seul commit effectué pendant cette intervention est **`f797c54`** :
`docs(frontend): design Equipments module MVP`, un document, 456 lignes.
Son staging et `git diff --cached --check` ont été contrôlés ; dépôt propre
confirmé avant UI 5.2. Aucun commit UI 5.2, push ou merge.

## Périmètre et fichiers

Nouveaux fichiers :

- [EquipmentPageQuery core](../frontend/src/app/core/models/equipment-page-query.model.ts).
- [EquipmentCreate et EquipmentUpdate](../frontend/src/app/features/equipments/models/equipment-write.model.ts).
- [EquipmentListQuery](../frontend/src/app/features/equipments/models/equipment-list-query.model.ts).
- [EquipmentsApiService](../frontend/src/app/features/equipments/data-access/equipments-api.service.ts).
- [Tests du service](../frontend/src/app/features/equipments/data-access/equipments-api.service.spec.ts).
- Le présent rapport.

Fichiers modifiés : [ReferenceDataApiService](../frontend/src/app/core/api/reference-data-api.service.ts)
et [ses tests](../frontend/src/app/core/api/reference-data-api.service.spec.ts).
Les DTO core EquipmentRead/EquipmentStatus/EquipmentCriticality sont réutilisés,
sans duplication. Aucun écran, route, composant de formulaire ou catalogue de types.
Aucun fichier Companies/Sites/Dashboard, backend, dépendance, budget ou configuration
suivie modifié. UI 5.3 non commencée.

## Contrat de données et sécurité du transport

- EquipmentCreate exige site_id/name/code/equipment_type. Description facultative
  string/null ; status et criticality facultatifs, typés avec les enums core.
  Leur omission laisse FastAPI appliquer operational/medium ; le service n'injecte
  pas ces valeurs. Les défauts visibles du futur formulaire restent ceux d'EQ-06.
- EquipmentUpdate contient uniquement name/code/equipment_type/description/status/
  criticality, tous facultatifs. Seule description accepte null. Aucun site_id,
  company_id, identifiant, horodatage ou descendant dans les DTO d'écriture.
- Les limites SQL 150/100/100 et l'unicité globale du code sont documentées dans
  le contrat. Le type est un texte libre. Validation complète des formulaires,
  dont longueurs/non-blancs, prévue en UI 5.5 ; aucune normalisation de casse,
  espaces ou Unicode dans le transport.
- POST et PATCH construisent de nouveaux objets à partir d'une whitelist. Les
  propriétés inconnues sont exclues même pour une variable structurellement
  compatible comme EquipmentRead. Aucune mutation de l'objet fourni.
- Un champ éditable non nullable SQL fourni avec null via un cast non sûr produit
  une **TypeError locale dans l'Observable**, avant toute requête HTTP. Un champ
  requis absent/null en création, site_id compris, est également refusé. Ce garde-fou
  n'est pas présenté comme une nouvelle réponse backend 422 ou une validation
  exhaustive du contrat à l'exécution.
- Champs facultatifs undefined omis ; description absente, chaîne vide et null
  restent distincts. Aucun changement de site permis dans PATCH. Le transport
  accepte un PATCH vide : le calcul des différences et le blocage d'une soumission
  inchangée appartiennent à UI 5.6.
- Les requêtes restent froides ; aucune souscription interne, retry, suppression,
  calcul ML, transition de statut imposée ou transformation des réponses/erreurs.

| Fonction | Requête et réutilisation |
| --- | --- |
| list | GET `/api/v1/equipments`, délégué à getEquipments ; site_id requis, search/status/criticality/page/page_size facultatifs |
| getById | GET `/api/v1/equipments/{id}`, délégué à getEquipmentById déjà présent dans core |
| create | POST `/api/v1/equipments`, payload whitelisté, réponse EquipmentRead |
| update | PATCH `/api/v1/equipments/{id}`, six champs éditables whitelistés, aucun déplacement |

Le transport core ajoute explicitement status/criticality aux HttpParams s'ils
sont fournis, sans envoyer company_id, equipment_type comme filtre, ou d'autres
propriétés inconnues. Page/page_size/search conservent leur comportement existant.
getEquipments(siteId) et les appels Dashboard utilisant ReferencePageQuery restent
compatibles. Les paramètres invalides de pagination ne sont pas recalés : la
validation backend et les futures validations UI gardent leurs responsabilités.

## Tests et validations

Tous les HTTP de ces tests passent par HttpTestingController. Aucun appel API
réel, aucune connexion SQL, opération Docker, migration, seed ou écriture métier.
Les validations sont séquentielles, sans build concurrent avec Vitest.
Configuration temporaire ignorée `frontend/tmp/ui-5.2/vitest.config.mjs` : deux
workers comme la référence Sites, sans changer délais, assertions ou exclusions.

- Premier essai ciblé : compilation refusée par deux TS2345 dans les nouvelles
  assertions JSON, serializeBody ayant un type union. Typage corrigé dans les tests ;
  aucun test exécuté par cet essai, aucun défaut applicatif attribué à cet incident.
- Suite ciblée finale Equipment/core/Dashboard : **196 tests réussis, 12 fichiers**,
  durée Vitest 56,85 s ; compilation 19,378 s. Journal `targeted-tests-final.log`.
- Suite Angular complète : **637 tests réussis dans 43 fichiers**, durée 33,64 s,
  compilation 19,979 s, démarrage Vitest 16:14:03 UTC. Soit **54 tests ajoutés** :
  45 dans le nouveau service Equipment et neuf dans le transport partagé.
- Build production réussi en **22,443 s**, terminé à 16:15:18 UTC. Avertissement
  initial existant : **601,51 ko / budget 500 ko**, dépassement 101,51 ko ; aucun
  seuil relevé. Journaux `angular-tests.log` et `production-build.log`.

Comparaison aux artefacts UI 4.7.5 conservés, sans reconstruire la référence :
initial **601 509 octets inchangés** ; ensemble des 31 fichiers JS/CSS
**786 034 octets**, contre 785 921, soit **+113 octets**. Les actifs initiaux
sont identifiés dans index.html (scripts, styles et modulepreload). Synthèse
`technical-results.json` conservée dans le dossier ignoré. Aucun contrôle Sass
ou npm audit relancé pour cette modification de transport sans style/dépendance.

Couverture ajoutée : contrats TypeScript, filtres indépendants/combinés et enums,
pagination et omissions, company_id absent, réutilisation des GET core, réponse
paginée/détail inchangée, POST exact et défauts laissés au backend, limites de
longueur du payload accepté sans transformation, descriptions omises/vides/null,
PATCH partiel/vide, whitelists POST/PATCH, non-mutation des objets, casts null non
sûrs, champs requis absents, erreurs 403/404/409 des deux causes connues et conflit
non précisé/422/500/réseau sans retry, aucune méthode ni requête DELETE.

Le core vérifie aussi les trois statuts et quatre criticités indépendants, leurs
combinaisons, l'ancien appel Dashboard sans options et l'absence de fuite de ces
filtres dans Companies/Sites. Le périmètre ciblé comprend les suites Dashboard
existantes, sans modifier leurs assertions. Les mocks ne prouvent aucune création,
transition, cascade ou persistance réelle Equipment dans PostgreSQL.

## Limites et état Git

Pas de contrôle d'unicité définitif côté client, autorisation multi-tenant,
transfert, suppression ou correction des limites Pydantic/SQL. Les validations
de formulaires, protections d'abandon, notifications et calcul du PATCH différentiel
restent aux étapes d'écran. Les dettes de secrets historiques et de budget
préexistantes ne sont pas modifiées.

Contrôles finaux : `git diff --check`, espaces et tirets ASCII conformes ; liens
locaux du rapport vérifiés. Périmètre limité aux huit fichiers UI 5.2 décrits ;
aucun secret historique connu ni signature de clé détecté dans ces candidats.

HEAD final : `f797c54`, index vide. Les deux fichiers core
modifiés, cinq nouveaux fichiers TypeScript et ce rapport restent non commités.
Le document UI 5.1 commité n'est plus modifié par UI 5.2. Les logs, la configuration
Vitest temporaire et les builds restent ignorés dans `frontend/tmp/ui-5.2/`.

**Validation attendue avant le commit UI 5.2. Aucun début d'UI 5.3.**
