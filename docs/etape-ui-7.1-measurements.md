# UI 7.1 - Audit et conception Measurements

21 octobre 2026. **MES-01 à MES-12 sont validées par l’utilisateur pour le MVP en lecture seule.**
Branche vérifiée : feature/frontend-measurements. HEAD : 20293a4. Dépôt propre
au départ ; aucun changement de branche, fetch, commit, push ou merge.
Seul ce rapport est ajouté. UI 7.2 non commencée.

Actualisation de validation métier : branche et HEAD reconfirmés ; le rapport
était déjà non suivi au début de cette actualisation. Les douze décisions sont
approuvées, sans autorisation de commencer UI 7.2. Aucun test relancé ; les
résultats ci-dessous restent ceux de l’audit initial.

## 1. Méthode et sources

Audit des sources versionnées, contrôles Python purs en mémoire, aucune requête
HTTP réelle, connexion ou écriture PostgreSQL, requête SQL, opération Docker ou
modification applicative. Aucun package ajouté. Les contraintes SQL ci-dessous
proviennent des modèles et migrations, pas d'une inspection de la base active.
Le statut de branche dans project-status.md est celui de la livraison Sensors
précédente ; il n'est pas modifié dans cette mission limitée au rapport.

Sources principales :

- [ORM Measurement](../backend/app/models/measurement.py), [schémas](../backend/app/schemas/measurement.py), [repository](../backend/app/repositories/measurement_repository.py), [service](../backend/app/services/measurement_service.py), [routes](../backend/app/api/routes/measurements.py).
- [Migration Measurements](../backend/migrations/versions/570ce155aaf8_create_measurements_table.py), [enums](../backend/app/core/enums.py), [validation timezone](../backend/app/core/datetime_utils.py), [Page](../backend/app/schemas/pagination.py), [pagination](../backend/app/core/pagination.py), [montage API](../backend/app/main.py).
- [Sensor](../backend/app/models/sensor.py), [Equipment](../backend/app/models/equipment.py), [Site](../backend/app/models/site.py), [Company](../backend/app/models/company.py), [PredictionRecord](../backend/app/models/prediction_record.py), [migration des prédictions](../backend/migrations/versions/d6ec01cf13b6_add_prediction_records.py).
- [Tests schémas](../tests/business_validation/test_schemas.py), [tests pagination/filtres](../tests/pagination_filters/test_routes.py), [limites SQLite/PostgreSQL](../tests/pagination_filters/README.md), [fixture SQL](../tests/dashboard/support.py), [tests extracteur](../tests/data_pipeline/test_extractor.py), [tests nettoyage](../tests/data_cleaning/test_cleaning.py).
- [Extracteur interne](../backend/app/data_pipeline/extractor.py), [qualité du nettoyage](../backend/app/data_pipeline/quality_rules.py), [détecteur de doublons](../backend/app/data_pipeline/duplicate_detector.py).
- [Architecture frontend](frontend-architecture.md), [conception Sensors](etape-ui-6.1-sensors.md), [livraison Sensors](ui-6.8-sensors-delivery.md), services et composants liés en section 6.

### Preuves réellement obtenues

Avec backend/.venv/Scripts/python.exe -B et chemins backend/tests ajoutés au
processus : **33 tests business_validation.test_schemas réussis**. Ils concernent
plusieurs entités, ce n'est pas une suite CRUD Measurements. Le processus vérifie
que app.core.database n'est pas importé. Aucun fichier de test modifié.

Sondes Pydantic en mémoire :

- Timestamp naïf refusé ; offset +05:30 et six décimales conservés par le schéma ;
  neuf décimales tronquées à six ; timestamp numérique 0 accepté comme instant
  1970-01-01T00:00:00Z ; date future 2099 acceptée.
- Valeur négative, chaîne numérique et booléen True acceptés (True devient 1.0).
  NaN/Infinity sous forme de chaînes acceptés en float ; un MeasurementRead avec
  NaN donne value:null via model_dump_json(). Pas de test de ce chemin HTTP.
- sensor_id 0/-1 accepté au schéma ; qualité missing avec valeur numérique acceptée ;
  champ inconnu unit ignoré. PATCH vide -> {}, null explicites conservés pour
  timestamp/value/quality ; sensor_id en PATCH ignoré.
- Méthode get_by_sensor_and_period extraite par AST et exécutée seule avec
  références factices, sans import du service/base : deux bornes naïves ou égales
  atteignent le repository factice ; mélange naïf/aware -> TypeError. Ce contrôle
  établit un chemin Python, pas un statut HTTP observé ni une exécution SQL.

Tests routes/pipeline lus, **non exécutés** : la fixture utilise potentiellement
DASHBOARD_TEST_DATABASE_URL et crée tables/schémas. Aucun test SQL lancé.
Les 1 179 tests Angular, build et 605,24 kB de Sensors restent historiques,
sans relance ni preuve de validation du futur module Measurements.

## 2. Contrats backend exacts

### 2.1 Champs et DTO

MeasurementRead contient **cinq champs**, sans objet parent imbriqué :

| Champ | Création API | PATCH API | SQLAlchemy / migration |
| --- | --- | --- | --- |
| id | Non déclaré | Non déclaré | Integer, PK et index ; lecture seule |
| sensor_id | int requis sans ge=1 | Absent du contrat | FK NOT NULL vers sensors.id, ON DELETE CASCADE, index non unique |
| timestamp | datetime requis avec timezone | datetime ou null facultatif, timezone exigée si non null | DateTime(timezone=True), NOT NULL, index non unique |
| value | float requis | float ou null facultatif | Float, NOT NULL, aucune borne physique ni précision décimale métier |
| quality | MeasurementQuality, défaut good | MeasurementQuality ou null facultatif | VARCHAR(30), NOT NULL, défaut ORM good, aucun CHECK enum |

MeasurementBase porte timestamp/value/quality et valide le fuseau.
MeasurementCreate ajoute sensor_id. MeasurementUpdate est distinct et limité à
timestamp/value/quality. MeasurementRead active from_attributes et ajoute id/sensor_id.
Aucun created_at/updated_at, code, description, unité, auteur, provenance,
calibration ou version de mesure. Ne pas inventer ces métadonnées.

Schémas non stricts : coercitions numériques/datetime et extra ignoré par défaut.
unit/company_id/site_id/equipment_id n'ont pas de rôle dans ces DTO. Sensor_id n'est
pas transférable par PATCH. Omission PATCH conserve la valeur via exclude_unset ;
**null explicite est affecté à une colonne NOT NULL**, ce n'est pas une omission.
Le défaut good est Pydantic/ORM, sans server_default dans la migration.
Aucun UNIQUE (sensor_id,timestamp), CHECK physique, contrôle de fréquence ou date
future. Les migrations ultérieures examinées ne renforcent pas cette table.

### 2.2 Sept endpoints

Préfixe /api/v1 constaté dans main.py. Statuts établis par lecture des routes,
sans recette HTTP dans cet audit. Chemins sans slash terminal.

| Méthode et chemin | Succès | Erreurs et particularités |
| --- | --- | --- |
| GET /api/v1/measurements | 200 Page[MeasurementRead] | 422 query invalide, 400 ValueError fuseau/ordre ; sensor_id absent de la base -> page vide, pas 404 |
| GET /api/v1/measurements/sensor/{sensor_id} | 200 liste complète | Vérifie Sensor ; absent -> 409 Sensor not found ; non paginé, sans filtre qualité/période |
| GET /api/v1/measurements/sensor/{sensor_id}/period | 200 liste complète | start_time/end_time requis ; 422 parsing/absence ; 409 Sensor absent ou début > fin ; risque timezone décrit en section 3 |
| GET /api/v1/measurements/{measurement_id} | 200 MeasurementRead | 404 Measurement not found, 422 id non convertible en int |
| POST /api/v1/measurements | 201 MeasurementRead | 422 schéma ; 409 Sensor not found et rollback sur ValueError ; aucune déduplication |
| PATCH /api/v1/measurements/{measurement_id} | 200 MeasurementRead | 404 absent, 422 schéma ; rollback/409 seulement pour ValueError ; erreurs d'intégrité non traduites |
| DELETE /api/v1/measurements/{measurement_id} | 204 sans corps | 404 absent ; suppression définitive sans garde de conservation métier |

Les ids de chemin sont int sans borne positive : un entier négatif ne donne pas
422 automatiquement (détail absent -> 404, Sensor absent -> 409). Aucun PUT,
import/export, bulk, upsert, agrégat ou recherche de mesure dans ce routeur.
get_all existe en service/repository, mais le GET public utilise get_paginated.

### 2.3 Pagination, filtres et tri

| Query | Contrat réel |
| --- | --- |
| page | Entier >=1, défaut 1, aucune borne haute métier |
| page_size | Entier 1..100, défaut 20 |
| sensor_id | Entier >=1 facultatif ; omission = liste globale backend |
| quality | Une seule valeur good/suspect/bad/missing/estimated, facultative |
| start_time | datetime facultatif, offset validé au service, borne incluse |
| end_time | datetime facultatif, offset validé au service, borne exclue |

Filtres combinés par AND, sans join parent. Le GET paginé ne vérifie pas
l'existence du Sensor. Deux bornes exigent début < fin ; une borne seule permise.
Aucun maximum de période, ni fin <= maintenant. Aucun filtre company/site/equipment,
status Sensor, unité, min/max value, search ou tri configurable. Ne pas copier
ReferencePageQuery avec search ni afficher une recherche que le serveur ignore.
Les paramètres non déclarés ne constituent pas des filtres.

Tri fixe **timestamp DESC, id DESC**, départage inclus à timestamp égal.
Offset=(page-1)*page_size, SELECT limité et COUNT séparé avec les mêmes filtres.
Réponse {items,total,page,page_size,pages}, pages=ceil(total/page_size), ou 0 si
aucune ligne. Hors plage : items vide avec total/pages conservés, sans correction
ou 404 automatique. Pas de curseur ni snapshot explicite des pages/items/total.
Les insertions concurrentes peuvent déplacer les pages malgré le tri déterministe.

## 3. Horodatages et fuseaux

| Chemin | Validation | Bornes | Ordre |
| --- | --- | --- | --- |
| GET paginé | validate_timezone pour chaque borne ; naïf -> 400, début >= fin -> 400 | [début, fin), bornes facultatives séparées | timestamp DESC, id DESC |
| GET sensor simple | Aucune borne | Historique complet | timestamp DESC seulement |
| GET sensor/period | Parent puis comparaison directe ; pas de validate_timezone | [début, fin], égalité autorisée | timestamp ASC seulement |
| POST / PATCH | Pydantic exige offset sur timestamp non null ; null PATCH accepté | Pas de borne métier, futur autorisé | Sans objet |

La route period ne valide ni ne normalise les fuseaux : deux dates naïves peuvent
atteindre SQL, avec résultat dépendant du dialecte/contexte de session. Un mélange
naïf/aware lève TypeError, non capturé par except ValueError : chemin susceptible
de 500. Deux aware sont comparées comme instants ; pas de conversion UTC explicite
par MeasurementService. **Ne pas substituer period au GET paginé.**

La migration déclare DateTime(timezone=True), contrairement aux dates
administratives Sensor sans timezone. MeasurementRead exige aussi un offset : une
réhydratation naïve viole le contrat de réponse. Les tests SQLite gardent des objets
aware dans l'identity map, ce qui ne prouve pas l'hydratation native PostgreSQL.
Aucun contrôle de données historiques, de fuseau de session ou de base active ici.
Le DTO ne contient pas de zone IANA ou de champ séparé garantissant le fuseau
d'acquisition ; ne pas promettre sa reconstruction. L’affichage UTC retenu est
un choix UI validé, pas une preuve que toutes les chaînes serveur terminent par Z.

Précision Python constatée : microsecondes, six décimales. Le formateur UTC
frontend affiche les secondes sans fraction ; JavaScript Date/toISOString ne
préserve pas la précision au-delà des millisecondes. Le filtre Dashboard n'accepte
que 1..3 décimales et interdit la fin future, contrairement à Measurements.
Il ne peut pas être recopié sans adaptation et décision explicites.

Décision validée : UTC explicitement libellé, borne fin exclusive, chaîne ISO source
conservée et affichage des fractions significatives jusqu'à six décimales. Jamais
d'aller-retour silencieux Date/toISOString sur une date reçue ou un filtre précis,
ni ajout de Z à une donnée naïve. Une date naïve est une anomalie, pas une heure
locale à deviner. Saisie UTC clairement libellée, conversion d'offset éventuelle
explicite/testée, pas d'arrondi ni de fin à 23:59:59.999. URL temporelle invalide :
blocage, sans suppression du filtre pour lancer une requête élargie.

## 4. Qualité, valeurs, unités et règles d'écriture

| Qualité API | Libellé retenu | Limite sémantique |
| --- | --- | --- |
| good | Bonne | Qualité déclarée, pas une certification physique |
| suspect | Suspecte | Ligne conservée, sans exclusion silencieuse |
| bad | Mauvaise | Valeur fournie affichée avec indicateur |
| missing | Manquante | Statut accepté malgré value NOT NULL ; pas une ligne absente |
| estimated | Estimée | Aucun calcul d'estimation côté UI |

Enums exactes et sensibles à la casse, sans trim. SQL conserve une chaîne sans
CHECK enum : une qualité historique inconnue peut invalider la réponse entière.
Le pipeline classe good valide, suspect/estimated avertissement, bad/missing
invalide, normalise et teste isfinite. **MeasurementService n'appelle pas ce
nettoyage** : ne pas attribuer ses protections au CRUD ou exclure des lignes de
l'historique administratif selon ces règles.

Value est un float sans Decimal, échelle ou chiffres significatifs métier.
Négatifs et zéro permis, sans règle universelle value>=0. Coercitions bool/chaînes
et non-finis acceptés au schéma. La sonde NaN -> null concerne model_dump_json,
pas un échange HTTP réellement testé. Le futur transport devra vérifier
Number.isFinite et le type réel : null/booléen ne deviennent jamais des zéros.
Affichage fidèle au nombre reçu, sans toFixed métier arbitraire, seuil physique
ou conversion d'unité. Notation scientifique possible, format français et valeur
source consultable en détail. La précision lexicale initiale déjà perdue en float
n'est pas reconstructible par Angular. Réponse invalide signalée explicitement.

Unité issue du **Sensor actuel**, jamais de Measurement : charger Sensor par id,
libeller Unité actuelle du capteur, aucun snapshot historique garanti. Les décisions
Sensors verrouillent unité/type/parent dans l'UI, mais son PATCH backend reste
plus permissif. Une mutation directe peut réinterpréter tout l'historique affiché.
Unité inconnue : mention indisponible, jamais déduite du type ou de l'URL.

Aucun contrôle de doublon create ni UNIQUE sensor_id/timestamp : mêmes capteur et
instant peuvent avoir plusieurs ids. Aucun 409 de doublon garanti. Le départage
id du paginé ne donne pas une priorité métier. Le détecteur du pipeline ne fait
pas respecter une contrainte SQL ; pas de fusion/suppression client de ces lignes.

Create vérifie l'existence du Sensor, sans statut active imposé, validation de ses
parents, date future, doublon ou cohérence physique. Repository : add/flush/refresh ;
service : commit/refresh. Update applique exclude_unset, flush/refresh puis
commit/refresh ; PATCH vide non refusé. DELETE : delete/flush puis commit.
Contrairement à Sensors, ce repository ne fait pas lui-même commit. Néanmoins
IntegrityError de flush/commit n'est pas traduit : null NOT NULL ou course FK
peuvent échapper au 409 métier. Aucun auteur, journal de correction, motif,
version, verrou optimiste ou idempotence dans ce contrat.

Une modification peut influencer les features futures sans invalider les
prédictions persistées antérieures : risque inféré de l'absence de mécanisme dans
ce service, pas d'une expérimentation sur les données. Le CRUD disponible ne
suffit pas à autoriser une correction d'historique industriel.

## 5. Relations, suppressions et sécurité

Measurement.sensor_id est NOT NULL, Sensor.measurements a cascade all,delete-orphan.
FK ON DELETE CASCADE vers Sensor, lui-même descendant Equipment/Site/Company avec
cascades. Supprimer un ancêtre peut donc supprimer les relevés, sans archivage,
soft delete ou prévisualisation d'impact dans ce routeur.
PredictionRecord.measurement_id est nullable mais **ON DELETE CASCADE**, confirmé
par modèle/migration : les prédictions directement liées peuvent être supprimées,
pas simplement mises à null. Celles sans cette FK ne sont pas automatiquement
supprimées par le DELETE de mesure. Pas de garantie de reconstruction/invalidation
complète des données dérivées. Aucun DELETE proposé en frontend.

Contrôles : Sensor existe en création et lectures spécialisées ; Measurement
existe en détail/PATCH/DELETE. Aucun contrôle de la chaîne industrielle ou du droit
d'un utilisateur. GET paginé global possible ; FK signifie existence, pas autorisation.
Aucune dépendance auth/RBAC/tenant dans ce routeur ou son montage. Les jointures
de l'extracteur interne ne sécurisent pas ces endpoints CRUD. La sélection Angular
proposée garantit la cohérence UX, pas l'isolation multi-tenant. Aucun accès à la
base historique dans cet audit.

## 6. Audit frontend et réutilisation

| Élément existant | Réutilisation envisagée, sans changement ici |
| --- | --- |
| [ReferenceDataApiService](../frontend/src/app/core/api/reference-data-api.service.ts) | Companies paginées, Sites par entreprise, Equipments par site, détails par id |
| [CompaniesApiService](../frontend/src/app/features/companies/data-access/companies-api.service.ts), [SitesApiService](../frontend/src/app/features/sites/data-access/sites-api.service.ts) | Séparation DTO/transport/pages, contexte URL et erreurs, sans imposer un CRUD Measurements |
| [EquipmentsApiService](../frontend/src/app/features/equipments/data-access/equipments-api.service.ts) | Frontières de transport et whitelists défensives |
| [SensorsApiService](../frontend/src/app/features/sensors/data-access/sensors-api.service.ts) | Catalogue Sensor paginé par equipment_id et détail Sensor/unité ; aucun nouveau service core nécessaire |
| [SensorsListFacade](../frontend/src/app/features/sensors/sensors-list.facade.ts) | État local, vérification des parents, switchMap et rejet des données d'un autre périmètre |
| [SensorDetail](../frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.ts) | Erreurs parent distinctes, données conservées, retour indépendant du rattachement |
| [Page](../frontend/src/app/core/models/page.model.ts) | Page générique ; futur MeasurementPageQuery distinct, sans search |
| [Formateurs de dates](../frontend/src/app/shared/utils/datetime-display.ts), [filtres Dashboard](../frontend/src/app/features/dashboard/components/dashboard-filters/dashboard-filters.component.ts) | UTC explicite, à adapter ultérieurement pour microsecondes/bornes facultatives ; pas de copie aveugle |
| [Navigation](../frontend/src/app/layout/navigation/navigation.config.ts), [routes](../frontend/src/app/app.routes.ts), [placeholder](../frontend/src/app/shared/pages/feature-placeholder/feature-placeholder.component.html) | /measurements existe sous Mesures, lazy FeaturePlaceholderComponent, aucune donnée ni requête métier |

PageHeader, LoadingState, EmptyState, ErrorState, businessReferenceLabel, styles
_actions.scss/_buttons.scss et focus Shell restent les conventions. Une future
feature measurements autonome aurait modèles, transport GET, façade locale,
list/detail et routes lazy ; aucun store global, cache ou package requis par cette
conception. Les formulaires Create/Edit existants ne sont pas à reproduire par défaut.

## 7. Décisions métier validées

**MES-01 à MES-12 approuvées par l’utilisateur pour le MVP Measurements en lecture seule.**

| Référence | Décision validée | Conséquence | Statut |
| --- | --- | --- | --- |
| MES-01 | Consultation par capteur choisi explicitement après Entreprise -> Site -> Équipement -> Capteur | Aucun GET global ni présélection ; capteurs actifs et inactifs consultables | Validée |
| MES-02 | Utiliser uniquement le GET paginé, bornes UTC [début,fin) facultatives | Évite period divergent ; aucune période par défaut inventée ou interdiction du futur copiée du Dashboard | Validée |
| MES-03 | Préserver jusqu'à six décimales temporelles et la chaîne source, refuser un fuseau inconnu | Adaptation des utilitaires au futur développement, pas de perte silencieuse | Validée |
| MES-04 | Afficher les cinq qualités déclarées, Toutes par défaut | Aucun score qualité calculé ou exclusion automatique ; missing reste une qualité de ligne | Validée |
| MES-05 | Nombres finis sans arrondi métier ni borne physique inventée | Zéro/négatifs valides, anomalie sur null/booléen/non-fini, jamais convertis en zéro | Validée |
| MES-06 | Afficher l'unité actuelle du Sensor avec réserve de snapshot absent | Pas d'unité dans DTO mesure, pas de conversion ni déduction par type | Validée |
| MES-07 | Pas de création manuelle dans le premier MVP | POST existe mais validation numérique, provenance, doublons et gouvernance insuffisants ; option ultérieure distincte | Validée |
| MES-08 | Historique en lecture seule, pas de formulaire PATCH au MVP | Pas d'audit/version des corrections ; sensor_id est déjà absent du PATCH backend | Validée |
| MES-09 | Aucun DELETE, transfert ou nettoyage automatique de doublons en frontend | Préserver historique/prédictions ; rétention et correction à définir séparément | Validée |
| MES-10 | Sensor <-> Measurements via parents réels et contextes séparés | Lien vers historique et retour borné, pas de returnUrl libre ni filtre Sensor recyclé en qualité/période | Validée |
| MES-11 | Aucun polling, temps réel, graphique, prédiction ou indicateur fictif | Historique uniquement des données effectivement reçues | Validée |
| MES-12 | Pagination serveur 20 par défaut, choix 20/50/100, tri fixe et filtres explicites | Pas de recherche de mesure, tri local ou chargement intégral d'historique | Validée |

### Contrat de lecture MVP confirmé

La liste utilise exclusivement **GET /api/v1/measurements**, contrat paginé
Page[MeasurementRead], avec sensor_id vérifié et seulement quality/start_time/
end_time/page/page_size en complément. Les lectures spécialisées
/measurements/sensor/{sensor_id} et /measurements/sensor/{sensor_id}/period ne
sont pas interchangeables avec ce contrat : réponses non paginées, bornes,
tris et erreurs différents. Elles sont exclues du service Angular MVP.
GET /api/v1/measurements/{measurement_id} reste dédié à la fiche détail.

Dates traitées en **UTC**, intervalle **[début, fin)** : début inclus, fin exclue.
Aucune perte supplémentaire de précision des horodatages par Angular : conserver
la chaîne ISO reçue et ses fractions jusqu’aux six décimales du contrat audité,
y compris dans les filtres et l’URL. Une conversion d’offset en UTC préserve
l’instant et sa précision ; aucune troncature aux millisecondes/secondes, aucun
fuseau inventé. La réduction à six décimales déjà constatée côté Pydantic sur
une entrée plus précise reste une limite backend, pas une précision à reconstituer.

Les cinq qualités restent exactement **good, suspect, bad, missing, estimated** ;
les libellés français servent uniquement à l’affichage. Les règles numériques
sont maintenues : type number réellement reçu et fini, zéro/négatifs admis,
null/booléen/non-fini signalés sans coercition en zéro, sans arrondi métier ni
borne physique inventée. La qualité missing ne rend pas value nullable.

Le futur service Angular MVP expose uniquement les lectures retenues :
**aucune méthode ni requête POST, PATCH ou DELETE**, aucun transfert et aucun DTO
d’écriture nécessaire au MVP. Les capacités d’écriture backend restent auditées,
sans être exposées par l’UI. Les anomalies B-MES-01 à B-MES-07, F-MES-01 et les
réserves B-SEN-02/03 restent distinctes et non corrigées par cette validation.

Les décisions d'écriture sont métier, pas déduites du CRUD disponible. Si une
création/édition est autorisée plus tard, prévoir DTO distincts et whitelist,
pas de sensor_id au PATCH ni unité/parents UI transmis. Ne jamais préremplir une
heure comme acquisition réelle ni inventer une valeur pour rendre missing saisissable.
Les corrections backend nécessaires resteraient séparément autorisées.

## 8. Parcours et écrans retenus pour le MVP

### 8.1 Liste et historique /measurements

Au départ, seul le catalogue Companies est chargé. Les quatre choix sont
explicites ; chacun invalide descendants/résultats et annule les lectures obsolètes.
Catalogues par pages de 50 avec Charger la suite, options dédupliquées par id ;
absence de la première page ne signifie pas référence inexistante. Catalogue Sensor
via SensorsApiService.list({equipment_id,page,page_size:50}), sans filtre active.
La recherche éventuelle d'un capteur relève de ce catalogue, pas des mesures.

Résoudre Sensor -> Equipment -> Site -> Company par GET ciblés, vérifier chaque
id/FK (Sensor.equipment_id, Equipment.site_id, Site.company_id) avant GET Measurements.
Sensor_id seul en URL est un choix explicite : compléter les parents réels.
Equipment seul attend Sensor ; Site seul attend Equipment/Sensor ; Company seule
attend ses descendants. Chaîne fournie contradictoire : blocage sans remplacement
silencieux. ID de périmètre invalide : notice, aucune liste globale de secours.

Après validation, seules query sensor_id/quality/start_time/end_time/page/page_size
partent à l'API. Vérifier sensor_id sur chaque ligne reçue ; rejeter une réponse
d'un autre capteur. Deux champs temporels facultatifs, UTC et borne fin exclusive
explicités ; application des filtres par action, page 1. Qualité/taille changée :
page 1. Changement de parent : vider descendants, résultats et période, conserver
qualité/taille valides, page 1. Ne pas calculer la période depuis une seule page.

Colonnes : Horodatage UTC, Valeur, Unité actuelle, Qualité, lien de consultation.
Id en détail utile pour distinguer deux relevés au même instant, sans nom/code
fictif de mesure. Pas de recherche nom/code, de cellule éditable ou d'agrégat client.

États distincts : sélection attendue, chargement catalogue, aucun descendant,
chargement mesures, aucune mesure du capteur, aucun résultat filtré, page hors
plage avec total positif, erreur de requête, référence ou donnée invalide. Aucun
faux zéro avant succès. Total=0 : pas de pagination ; hors plage : retour manuel
à une page disponible, pas de boucle automatique. Pas de chargement de toutes les
pages pour compter/chercher. COUNT/offset et pages mouvantes restent des limites.

### 8.2 Détail /measurements/:measurementId

GET détail réel disponible. Afficher id, timestamp UTC précis et ISO source,
valeur, qualité, Sensor nom/code/type et unité actuelle, Equipment/Site/Company réels.
Aucun created_at/updated_at, auteur ou provenance inventé. ID invalide sans HTTP,
404 distincte du réseau, mesure conservée quand un parent échoue. Unité indisponible
signalée sans déduction. Lien vers le capteur seulement après lecture de la référence
réelle. Accès direct par id possible ; contexte de retour ne remplace pas les parents.

Pas de routes new/edit retenues au MVP ni boutons d'écriture inactifs annonçant
une fonctionnalité livrée. Si ces routes étaient approuvées ultérieurement,
prévoir leur ordre avant la route dynamique. Aucun DELETE.

### 8.3 URL et navigation

Snapshot Measurements : company_id/site_id/equipment_id/sensor_id/quality/
start_time/end_time/page/page_size. IDs entiers positifs sûrs, qualité enum exacte,
page >=1 et taille 1..100. Choix UI 20/50/100, taille valide d'URL conservée.
Pagination invalide normalisée avec notice ; périmètre ou date invalide ne sont
pas supprimés pour lancer une requête élargie. Encoder + des offsets via
HttpParams/Router, pas par concaténation brute.

Sensor -> Voir les mesures : attendre la chaîne Sensor/Equipment/Site/Company,
utiliser les quatre ids réels, page=1/page_size=20, sans période ni qualité implicite.
Aucun search/status de Sensor transféré aux filtres Measurements. Conserver le
snapshot de retour Sensors sous paramètres distincts return_sensor_* bornés et
whitelistés (company_id/site_id/equipment_id/search/status/page/page_size).
Ce snapshot ne sélectionne pas les parents de Measurements.

Liste -> détail : préserver le snapshot appliqué, pas le brouillon. Détail -> Sensor :
id réel et contexte Sensors distinct valide, sinon parents réels/page 1/taille 20.
Parents indisponibles : ne pas fabriquer le contexte. Retour liste Measurements :
conserver le snapshot d'origine même différent des parents réels, avec notice.
Aucun returnUrl externe ou mutation de rattachement depuis une navigation.

### 8.4 Erreurs et accessibilité

400 paginé : période à corriger, sans retry automatique. 422 : query/id invalide,
mapper les champs reconnus, jamais du HTML serveur. 404 : mesure/référence absente
selon la requête, jamais un zéro. 409 des endpoints spécialisés documenté mais ces
endpoints sont exclus du transport MVP. 401/403 traité défensivement,
sans déclarer une authentification livrée. Réseau/5xx en lecture : relance manuelle.
switchMap/takeUntilDestroyed empêchent les anciennes réponses de rétablir un périmètre.
Aucune notification d'écriture dans ces pages de lecture.

PageHeader et actions harmonisés, tableau défilable sans débordement global,
aide seulement lorsque nécessaire, qualité non exprimée par couleur seule,
labels français, focus/clavier et erreurs accessibles. Contrôles ultérieurs aux
1440/1024/1023/768/390/320 px, aucune capture ou recette visuelle revendiquée ici.

## 9. Correctifs et évolutions séparés, aucun implémenté

| Référence | Besoin | Priorité et effet sur le MVP |
| --- | --- | --- |
| B-MES-01 | Harmoniser timezone, bornes et erreurs des lectures spécialisées avec le paginé | Anomalie démontrée par source/sonde ; nécessaire avant usage de period, évitée par le seul paginé |
| B-MES-02 | Refuser non-finis, arbitrer bool/chaînes/coercitions, garantir la réponse numérique | Bloquant pour création manuelle sûre ; lecture doit détecter les anomalies sans correction client |
| B-MES-03 | Distinguer omission/null, refuser null des champs SQL obligatoires, préciser ids positifs | Bloquant pour édition fiable, pas résolu par whitelist UI |
| B-MES-04 | Traduire IntegrityError/rollback, définir doublons/idempotence et corrections auditables | Prérequis d'écritures futures ; ne pas inventer UNIQUE sensor/timestamp sans décision métier |
| B-MES-05 | Authentification, autorisation de ressource et isolation multi-tenant | Bloquant avant exposition SaaS ; sélection UI insuffisante |
| B-MES-06 | Mesurer COUNT/offset, envisager index composite capteur/temps/id, curseur/limite de période | Besoin potentiel à mesurer, pas de migration justifiée par cet audit seul |
| B-MES-07 | Politique d'unité historique et mutations Sensor hors UI | Risque de réinterprétation, snapshot/version à arbitrer séparément |
| F-MES-01 | Adapter les dates frontend pour six décimales et filtres facultatifs sans pertes | Prérequis de l'affichage précis futur ; aucun changement Dashboard/Sensors maintenant |

**Aucune méthode repository manquante détectée sur les chemins Measurements.**
Aucun blocage analogue à B-SEN-01 établi pour une liste/détail par capteur en
lecture seule avec données valides. Sans recette PostgreSQL ni connaissance de la
qualité réelle des réponses, ne pas annoncer une intégration garantie.
B-MES-01/02/03 sont les anomalies techniques prioritaires ; MES-07/08/09 validées
excluent les écritures risquées du premier MVP. B-SEN-02 et B-SEN-03
restent ouverts ; cet audit ne les corrige pas.

## 10. Risques, acceptation et état Git

Risques majeurs : heure locale prise pour UTC, perte de microsecondes, bornes
différentes selon endpoint, unité actuelle prise pour historique, missing pris
pour un trou de série ou zéro, non-fini/null présenté comme valeur fiable,
doublons confondus avec pagination mouvante, surcharge non paginée, disparition
de prédictions liées et correction d'historique non auditée.

Critères de clôture UI 7.1 :

- Branche/HEAD/dépôt initial contrôlés, seul rapport ajouté, liens contrôlés,
  français sans tiret cadratin et git diff --check réussi.
- Sept endpoints, cinq champs, DTO/SQL distincts, enums, contraintes, bornes,
  tris, cascades et limites de sécurité décrits avec sources.
- Tests de schémas purs distingués du HTTP/SQL non exécuté et des références
  Angular historiques ; aucune connexion de base ou modification applicative.
- MES-01 à MES-12 explicitement validées par l’utilisateur ; correctifs séparés de
  l'implémentation. Aucun démarrage UI 7.2.

Critères d'une future implémentation après accord :

- HttpTestingController : GET liste paginée/détail uniquement, query whitelist,
  cinq qualités, bornes facultatives/exclusives et + encodé, page hors plage,
  400/404/422/réseau, aucun search/parent UI vers Measurements.
- Quatre sélections explicites, catalogues multipages/référence hors première
  page, parent absent/incohérent/inaccessible, Sensor inactif consultable,
  aucun GET avant chaîne complète, rejet d'items d'un autre Sensor.
- Dates aware/naïves, offsets/UTC, bornes égales/inversées, six décimales
  conservées en URL/affichage, changements de jour/heure, indépendance du fuseau
  navigateur. Aucune restriction futur sans décision métier.
- Valeurs zéro/négatives/grandes/petites, détection bool/null/non-fini, missing
  sans substitution, unité indisponible, deux ids de même instant non dédupliqués.
- Navigation et retour distinct, URL contradictoire, réponse tardive et détail
  avec parent indisponible. Aucun POST/PATCH/DELETE, compteur, polling ou graphique
  dans le MVP en lecture seule validé.
- Tests Angular ciblés/complets et build si sources exécutables modifiées,
  responsive et bundle signalés sans relever les budgets. Recette SQL séparément
  autorisée ; isolation des fixtures garantie avant tout test SQL.

État final : HEAD 20293a4 inchangé, index vide, seul
`docs/etape-ui-7.1-measurements.md` ajouté non suivi. Aucun commit/push/merge,
changement SQL/Docker/package ou écriture PostgreSQL. **MES-01 à MES-12 validées.
Attendre validation de cette actualisation documentaire et une autorisation
distincte avant tout développement ; UI 7.2 non commencée.**
