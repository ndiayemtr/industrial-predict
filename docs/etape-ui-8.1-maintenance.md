# UI 8.1 - Analyse fonctionnelle et conception Maintenance

23 octobre 2026. Mission documentaire, sans implémentation UI 8.2.
Les décisions **MAIN-01 à MAIN-16 sont validées par l'utilisateur comme référence
de conception du MVP de consultation uniquement**. Cette validation n'autorise
aucune écriture, transition de statut ou implémentation UI 8.2.

Finalisation documentaire du 23 octobre 2026 : UI 8.5 est consacrée à la navigation
et aux finitions UX. Création, modification et transitions sont reportées dans
un chantier séparé, après arbitrage métier et sécurisation du backend.
Aucun test applicatif ni sonde Pydantic n'est relancé pour cette actualisation.

## 1. Objectif métier, état Git et méthode

Permettre de retrouver les interventions d'un équipement industriel, lire leur
qualification, leurs dates et les informations déclarées, puis revenir à leur
contexte. Distinguer dossier d'intervention, statut de l'équipement, mesure et
recommandation prédictive : ce sont des objets différents.

État initial vérifié : branche main, HEAD main et référence locale origin/main
à 15c956b, dépôt propre. Création de la branche demandée
**docs/ui-8-maintenance-design**, au même HEAD. Aucun changement de main,
fetch, commit, push ou merge. La référence distante est lue localement ; aucune
nouvelle interrogation du serveur Git distant n'est revendiquée.

Seul ce document est créé. Le statut courant des suivis décrit encore la
livraison UI 7.6 : il est conservé, conformément au périmètre demandé.
Les rapports UI 5, UI 6 et UI 7 restent historiques et inchangés.

Audit des sources et de tests existants, sans importer les modèles ORM, lancer
l'API, consulter PostgreSQL, lire de configuration privée ou exécuter de SQL.
Douze sondes Pydantic et deux contrôles de lecture sont exécutés en mémoire avec
le Python du backend, option -B et blocage explicite de l'import app.core.database.
Aucun moteur SQL ni requête HTTP, aucune création de fichier exécutable.
Les suites backend/Angular et le build ne sont pas relancés.

### Sources de vérité

| Source | Éléments examinés |
| --- | --- |
| [Modèle MaintenanceRecord](../backend/app/models/maintenance_record.py) | 18 colonnes, types SQL, défauts ORM, relation Equipment |
| [Schémas Maintenance](../backend/app/schemas/maintenance.py) | MaintenanceBase/Create/Update/Read, validations et omission/null |
| [Enums](../backend/app/core/enums.py) | MaintenanceType, MaintenanceStatus, MaintenancePriority |
| [Routes Maintenance](../backend/app/api/routes/maintenance.py) et [montage](../backend/app/main.py) | Six endpoints sous /api/v1/maintenance, statuts et erreurs |
| [Service](../backend/app/services/maintenance_service.py) | Validation de période, existence Equipment, mutations et commit |
| [Repository](../backend/app/repositories/maintenance_repository.py) | Filtres, recherche, tri, COUNT/offset, flush/refresh |
| [Migration 783e16aa6ce3](../backend/migrations/versions/783e16aa6ce3_create_maintenance_records_table.py) | Table, longueurs, index, FK, absence de CHECK et de server_default |
| [Page](../backend/app/schemas/pagination.py), [construction](../backend/app/core/pagination.py), [timezone](../backend/app/core/datetime_utils.py) | Structure paginée et bornes aware |
| [Equipment](../backend/app/models/equipment.py), [Site](../backend/app/models/site.py), [Company](../backend/app/models/company.py) | Chaîne industrielle et cascades |
| [MaintenanceRecommendation](../backend/app/models/maintenance_recommendation.py) | Objet distinct, rattaché à Equipment, sans FK vers MaintenanceRecord |
| [Tests métier](../tests/business_validation/test_schemas.py) | Enums, défauts, fuseaux, chronologie, coûts et minutes |
| [Tests pagination](../tests/pagination_filters/test_routes.py) et [fixture](../tests/dashboard/support.py) | Routes GET et SQL isolé prévu par les tests, limites PostgreSQL |
| [Jeu DEV versionné](../infra/development/demo-data.json) et [rapport du seed](ui-4.7.3-development-data.md) | Exemples fictifs documentés, non lus en base et non réappliqués |

Les migrations ultérieures examinées ne renforcent pas les colonnes de
maintenance_records. Cette constatation porte sur le dépôt, pas sur un schéma
actif inspecté aujourd'hui.

## 2. Contrat de données exact

MaintenanceRead expose **18 champs**, sans objet Equipment imbriqué. Dans les
tableaux, « nullable » désigne SQL/lecture ; PATCH peut accepter davantage de null
que SQL. L'ordre JSON n'est pas un contrat fonctionnel.

| Champ | Type SQL, nullabilité et index | Pydantic Create et Read | Défaut à la création |
| --- | --- | --- | --- |
| id | Integer, PK NOT NULL, index non unique supplémentaire | int, Read seulement | Identité SQL ; non fourni par Create |
| equipment_id | Integer NOT NULL, FK equipments.id ON DELETE CASCADE, index | int requis en Create et Read, sans ge=1 | Aucun |
| maintenance_type | VARCHAR(30) NOT NULL, index | MaintenanceType requis | Aucun |
| status | VARCHAR(30) NOT NULL, index | MaintenanceStatus | planned, Pydantic et ORM |
| priority | VARCHAR(20) NOT NULL | MaintenancePriority | medium, Pydantic et ORM |
| title | VARCHAR(255) NOT NULL | str requis, aucun min/max_length ou trim | Aucun |
| description | Text nullable | str ou null | null |
| failure_code | VARCHAR(50) nullable, index non unique | str ou null, aucune limite Pydantic | null |
| root_cause | Text nullable | str ou null | null |
| action_taken | Text nullable | str ou null | null |
| technician | VARCHAR(150) nullable | str ou null, aucune limite Pydantic | null |
| planned_at | DateTime(timezone=True) nullable, index | datetime ou null, offset exigé si renseigné | null |
| started_at | DateTime(timezone=True) nullable | datetime ou null, offset exigé si renseigné | null |
| completed_at | DateTime(timezone=True) nullable | datetime ou null, offset exigé si renseigné | null |
| downtime_minutes | Integer nullable | int ou null, ge=0 | null |
| cost | Float nullable | float ou null, ge=0 | null |
| created_at | DateTime(timezone=True) NOT NULL | datetime, Read seulement, pas de validateur de fuseau spécifique | datetime.utcnow, côté ORM uniquement |
| updated_at | DateTime(timezone=True) NOT NULL | datetime, Read seulement, pas de validateur de fuseau spécifique | datetime.utcnow et onupdate ORM |

Aucun défaut serveur n'est déclaré dans cette migration, y compris pour status,
priority ou les dates administratives. Les valeurs nulles facultatives ne sont
pas des server_default. La relation ORM equipment ne rajoute pas de champ DTO.

Il n'existe ni code d'intervention unique, ni devise, montant Decimal, durée
calculée, échéance de fin, pièces, fournisseur, auteur, version, historique de
statuts, motif d'annulation, archivage, document joint ou identifiant de prédiction.
Le préfixe UI47-MAINT présent dans les titres du seed n'est pas un champ code.
failure_code n'est pas une clé unique. Aucun UNIQUE métier sur titre, équipement
ou dates ; deux interventions identiques peuvent avoir des ids distincts.

### Enums exactes et libellés proposés

| Enum backend | Valeurs exactes | Libellés UI proposés |
| --- | --- | --- |
| MaintenanceType | preventive, corrective, predictive | Préventive, Corrective, Prédictive |
| MaintenanceStatus | planned, in_progress, completed, cancelled | Planifiée, En cours, Terminée, Annulée |
| MaintenancePriority | low, medium, high, critical | Basse, Moyenne, Haute, Critique |

Les chaînes sont sensibles à la casse, sans nettoyage implicite des enums.
Les colonnes SQL sont des chaînes sans CHECK enum. Une ancienne valeur inconnue
peut donc exister en SQL et invalider une réponse Pydantic ; ne pas l'afficher
comme un statut connu par défaut. predictive est une catégorie déclarée, pas
une preuve de calcul IA, de recommandation ou de génération automatique.

### DTO de création et de modification

MaintenanceBase contient 14 champs métier, du type au coût.
MaintenanceCreate ajoute equipment_id : **15 champs**, dont equipment_id,
maintenance_type et title requis. MaintenanceRead ajoute id, equipment_id,
created_at, updated_at à la base et active from_attributes=True.

MaintenanceUpdate est un schéma distinct de **14 champs optionnels** :
maintenance_type, status, priority, title, description, failure_code, root_cause,
action_taken, technician, planned_at, started_at, completed_at, downtime_minutes,
cost. Chacun est annoté nullable avec défaut None ; les quatre premiers sont
pourtant SQL NOT NULL. Aucun equipment_id, id, created_at ou updated_at en PATCH.
Les champs inconnus sont ignorés par les schémas, pas rejetés comme erreur 422.
Schémas non stricts : certaines coercitions de nombres et datetime sont permises.

model_dump(exclude_unset=True) distingue omission et null. PATCH vide est accepté
et n'est pas rejeté par la route. Un champ omis reste inchangé ; une chaîne vide
est affectée telle quelle ; null explicite efface un champ nullable, mais peut
violer SQL pour title/type/status/priority. Aucun trim ni normalisation du contenu.
La date updated_at ne doit pas être présumée changée pour un PATCH sans mutation
effective : onupdate dépend de l'émission d'un UPDATE par l'ORM.

## 3. Endpoints et erreurs HTTP

Préfixe exact **/api/v1/maintenance**, singulier, sans slash terminal.
Statuts ci-dessous établis par lecture des routes, pas par une recette HTTP UI 8.1.

| Méthode et chemin | Réponse normale | Erreurs et limites |
| --- | --- | --- |
| GET /api/v1/maintenance | 200 Page[MaintenanceRead] | 422 query invalide ; 400 ValueError période ; équipement absent -> page vide, pas 404 |
| GET /api/v1/maintenance/equipment/{equipment_id} | 200 liste complète | Vérifie Equipment ; absent -> 409 avec Equipment not found ; non paginé, sans filtre |
| GET /api/v1/maintenance/{maintenance_id} | 200 MaintenanceRead | 404 avec Maintenance record not found ; 422 id non convertible en int |
| POST /api/v1/maintenance | 201 MaintenanceRead | 422 validation du body ; 409 ValueError et rollback ; existence Equipment vérifiée |
| PATCH /api/v1/maintenance/{maintenance_id} | 200 MaintenanceRead | 404 si absent ; 422 body/id invalide ; 409 ValueError et rollback ; pas de validation de l'état fusionné |
| DELETE /api/v1/maintenance/{maintenance_id} | 204, sans corps | 404 si absent ; suppression définitive, sans politique de rétention |

Aucun PUT, endpoint de transition start/complete/cancel/reopen, agenda, calendrier
serveur, import/export, pièce jointe ou endpoint de période spécialisé Maintenance.
get_all existe en service/repository, mais le GET public racine utilise le paginé.
La lecture /equipment/{id} n'est pas interchangeable avec le GET paginé.

Les ids de chemin et equipment_id du body sont des int sans borne positive.
Un chemin négatif est convertible : détail absent -> 404, lecture par Equipment
absent -> 409 ; ne pas promettre 422 dans ces cas. Query equipment_id, elle, a ge=1.

Les HTTPException explicites utilisent le format {detail: chaîne}. Exemples
exacts : Equipment not found, Maintenance record not found,
start_time must be before end_time, start_time must include timezone information
ou son équivalent end_time. La validation FastAPI/Pydantic 422 utilise
{detail: liste d'erreurs}, avec loc, msg, type et éventuellement input/ctx.
loc peut viser query/status, body/title ou body pour un validateur de modèle.
Ne pas interpréter ces messages comme HTML ni supposer un format métier 409 enrichi.

Les routes ne traduisent pas IntegrityError, DataError, erreur de sérialisation
ou validation de réponse en conflit métier. Des 5xx sont donc possibles, avec
corps non contractuel ; aucun 409 d'unicité ou de concurrence garanti.

## 4. Liste : filtres, pagination, recherche et temps

| Paramètre API | Contrat réel |
| --- | --- |
| page | int >=1, défaut 1, pas de maximum métier |
| page_size | int 1..100, défaut 20 |
| equipment_id | int >=1 facultatif ; omission = liste globale backend |
| maintenance_type | Une des trois valeurs exactes, facultative |
| status | Une des quatre valeurs exactes ; nom interne maintenance_status, alias HTTP status |
| priority | Une des quatre valeurs exactes, facultative |
| start_time | datetime facultatif avec timezone au service ; created_at >= start_time |
| end_time | datetime facultatif avec timezone au service ; created_at < end_time |
| search | str facultative, longueur brute 1..100 à la route |

Tous les filtres se combinent par AND ; les six champs de recherche sont combinés
par OR : title, description, failure_code, root_cause, action_taken, technician.
Le service trim search ; une chaîne composée d'espaces devient absence de filtre.
Une chaîne vide transmise explicitement échoue au min_length de la route.
Recherche ILIKE avec motif %texte%, insensible à la casse selon SQL/dialecte,
sans garantie sur les accents ; % et _ restent des jokers non échappés.
Aucun titre/code équipement, nom de société/site, statut Equipment, min/max coût,
filtre de retard, dates de démarrage/fin/planification, ni tri configurable.

**Les bornes portent exclusivement sur created_at**, jamais planned_at,
started_at ou completed_at. Libellé proposé : « Période de création du dossier
(UTC) », et non « période d'intervention ». L'index planned_at ne change pas ce
contrat. Les agrégats Dashboard filtrent parfois completed_at : ils ne sont pas
des substituts à cette liste.

Bornes facultatives séparément ; timezone obligatoire, naïf -> ValueError -> 400.
Si les deux existent, début < fin strictement ; égalité/inversion -> 400.
Intervalle [début, fin), sans maximum de période ou interdiction de date future.
Le service répète deux fois le même contrôle d'ordre : redondance de code,
sans deuxième règle métier à inventer. Pas de conversion UTC explicite dans le
service : comparaison d'instants aware puis paramètres SQL.

Tri fixe **created_at DESC, id DESC** sur le paginé. COUNT séparé avec les mêmes
filtres ; offset=(page-1)*page_size. Page = {items,total,page,page_size,pages},
pages=ceil(total/page_size), ou 0 pour total=0. Hors plage : items vide avec
total/pages conservés, pas de 404 ou de correction automatique. Pas de curseur
ni snapshot cohérent garanti entre COUNT et items en concurrence.
La lecture non paginée par équipement trie created_at DESC seulement, sans
départage id ni filtres. Aucun chargement global ne sera proposé au MVP Angular.

## 5. Dates, coûts, durée et statuts : portée des validations

### Horodatages

Les cinq colonnes de dates Maintenance sont DateTime(timezone=True), contrairement
aux dates administratives Equipment/Sensor sans timezone. Les dates métier
planned_at/started_at/completed_at renseignées doivent porter un offset dans
Create, Update et Read. Le seul ordre vérifié est started_at <= completed_at
lorsque ces deux valeurs sont présentes dans le même DTO. Égalité autorisée,
comparaison des instants avec offsets différents. Aucun ordre imposé par rapport
à planned_at ; une date de fin sans début est acceptée.

Les dates sont facultatives et aucune règle n'impose planned_at pour planned,
started_at pour in_progress ou completed_at pour completed. Un dossier completed
sans dates passe le schéma. Aucune interdiction des dates futures ou dérivation
automatique d'une heure à partir du statut.

Les défauts created_at/updated_at utilisent datetime.utcnow(), qui produit un
datetime naïf malgré les colonnes avec timezone. MaintenanceRead n'impose pas
d'offset pour ces deux champs. L'interprétation à la persistance dépend du
driver et du fuseau de session PostgreSQL ; UTC n'est pas garanti par ce défaut
seul. Aucun défaut ni fuseau de la session active n'a été vérifié ici.

Proposition : chaînes ISO conservées, affichage UTC explicite seulement si
offset présent ; source ISO complète en détail, microsecondes jusqu'à six
chiffres et offsets intacts. Date naïve administrative : signaler « fuseau non
fourni », ne pas ajouter Z ni l'utiliser silencieusement comme borne UTC.
**Sans offset ou preuve de conversion fiable, ne jamais supposer UTC ni ajouter Z
aux dates administratives naïves.** Aucune conversion automatique n'est approuvée.
Date métier naïve : anomalie de contrat à signaler. Aucun passage silencieux
Date/toISOString pour les timestamps précis ; adapter la logique Measurements,
sans lui attribuer les garanties absentes des dates administratives Maintenance.

### Coût et indisponibilité

cost est Float nullable, sans devise, échelle décimale comptable, conversion ou
total métier dans ce routeur. Ne pas afficher EUR, XOF ou un symbole monétaire
supposé ; proposer « Coût déclaré, devise non renseignée par l'API ».
Absence = « Non renseigné », pas zéro. Nombre fini reçu sans arrondi métier
arbitraire ; la précision float/JSON déjà perdue n'est pas reconstituable.

downtime_minutes est un entier de minutes nullable, ge=0 au schéma, sans maximum
Pydantic. PostgreSQL Integer est borné sur 32 bits signés, contrairement à cet int
Python. Aucune validation de dépassement au schéma. Ne pas confondre les minutes
déclarées avec completed_at-started_at : durée écoulée et indisponibilité sont
distinctes, aucun calcul ou remplissage automatique n'est effectué par le backend.

Les schémas acceptent certaines chaînes numériques/booléens par coercition.
ge=0 refuse les négatifs et NaN dans la sonde, mais accepte +Infinity pour cost.
SQL ne contient aucun CHECK coût/minutes >=0, de finitude, enum ou chronologie.
Une ligne ancienne SQL peut donc violer le contrat Read et faire échouer une
page entière. L'UI devra refuser non-finis, booléens et fausses valeurs zéro,
sans prétendre réparer ces divergences serveur.

### Transitions et effets métier absents

Le service affecte les champs autorisés, sans machine à états. Il n'empêche pas
completed -> planned, cancelled -> in_progress ou changement de type/priorité.
Aucune restriction selon le statut courant, aucun verrou historique ni journal
de correction. Ces opérations ne doivent pas être présentées comme transitions
approuvées industriellement. Aucune synchronisation d'Equipment.status,
décrément de disponibilité, création de mesure, prédiction ou recommandation.
Pas de conversion MaintenanceRecommendation -> MaintenanceRecord.

### Rattachement, transactions et suppressions

Create et GET non paginé vérifient seulement l'existence d'Equipment. Le GET
paginé ne la vérifie pas ; GET détail/PATCH/DELETE vérifient le dossier. Aucun
contrôle Company/Site, d'utilisateur, de rôle ou de tenant dans ce routeur.
equipment_id absent du DTO Update, donc transfert ignoré si fourni comme extra.

Repository create/update : add si création, flush, refresh. Service : commit
puis refresh. Les routes POST/PATCH rollback uniquement dans except ValueError ;
les erreurs SQL ne sont pas traduites. La validation HTTP de réponse intervient
après le traitement service : un 5xx ne prouve pas l'absence de commit.
Pas de version, ETag/If-Match, verrou optimiste ou clé d'idempotence. Deux
éditions concurrentes peuvent s'écraser ; création rejouée peut dupliquer.

PATCH applique uniquement les champs transmis, **sans revalider le dossier
fusionné**. Exemple documentaire : completed_at existant 10:00Z, PATCH contenant
seulement started_at=12:00Z passe Update. Le service peut l'affecter et committer ;
la lecture Read fusionnée refuse ensuite l'ordre inverse. C'est un chemin de
risque établi par source et validation en mémoire, pas un 5xx HTTP ou un défaut
SQL réellement provoqué. Une garde Angular ne protège pas les autres clients.

Equipment.maintenance_records est en cascade all, delete-orphan et la FK est
ON DELETE CASCADE. Suppression Equipment/Site/Company peut supprimer les dossiers.
DELETE Maintenance supprime définitivement ce dossier. Aucun modèle/migration
examiné ne référence maintenance_records.id par FK ; les mesures/recommandations
ne sont pas des enfants de l'intervention. Des analyses dérivées peuvent rester
obsolètes ; aucune invalidation/reconstruction automatique n'est promise.
Ne pas confondre cette absence de FK avec une absence d'impact métier.

## 6. Preuves disponibles et niveau de confiance

| Niveau | Capacités | Limite de preuve |
| --- | --- | --- |
| Implémentées, couvertes par des tests existants lus | Enums Create/Update, défauts planned/medium, PATCH vide ; fuseaux et dates nulles, ordre début/fin, coût/minutes non négatifs | Tests de schémas, pas de transaction ou HTTP d'écriture ; non relancés ici |
| Implémentées, tests de route existants lus | GET paginé : équipement/type/statut/priorité, six champs de recherche, AND/trim, page/total, tri avec égalité, bornes et erreurs 400/422 | TestClient et fixture SQL ; suites non exécutées ici |
| Implémentées mais validation insuffisante identifiée | GET détail/non paginé, POST/PATCH/DELETE MaintenanceService, dates générées, contraintes natives et réponse après commit | Aucun test CRUD dédié MaintenanceService trouvé dans la recherche ciblée ; pas de recette réelle UI 8 |
| Absentes | Workflow de transition, devise, audit/version, unité de coût historique, ordre planning, déduplication, sécurité de ressource | Évolutions séparées, pas des fonctionnalités livrées |

Le [README métier](../tests/business_validation/README.md) décrit des échecs du
22 septembre, dont les validateurs de timezone Update aujourd'hui présents.
Ce bilan historique ne remplace pas le code actuel et n'est pas réécrit.
Le [README pagination](../tests/pagination_filters/README.md) annonce historiquement
91 succès et un test PostgreSQL ignoré sur plusieurs entités, pas une suite CRUD
Maintenance validée aujourd'hui. La fixture peut utiliser
DASHBOARD_TEST_DATABASE_URL, créer un schéma et des tables : **aucun test SQL lancé**.
SQLite conserve des objets aware dans l'identity map ; cela ne valide pas la
réhydratation timestamptz PostgreSQL. Les tests Dashboard concernent des agrégats,
pas le workflow d'intervention. Le fichier tests/recommendations/test_maintenance_service.py
teste MaintenanceRecommendationService, pas MaintenanceService.

Sondes mémoire actuelles, sans base : titre vide et titre de 300 caractères
acceptés ; equipment_id négatif accepté au schéma ; completed sans dates accepté ;
cost=Infinity accepté, cost=NaN refusé ; cost=True converti en 1.0 et minutes
« 30 » en 30 ; minutes=2^40 accepté ; null sur type/status/priority/title accepté
en Update ; equipment_id ignoré en Update ; PATCH d'une seule date accepté ;
fraction de neuf chiffres réduite à six. Contrôles complémentaires : dates
administratives naïves acceptées par Read ; chronologie inverse fusionnée refusée
par Read. **Aucun statut HTTP ou résultat PostgreSQL déduit comme observé**.

Les [exemples versionnés](../infra/development/demo-data.json) montrent trois
interventions fictives : preventive/completed, corrective/in_progress et
corrective/planned, dont une avec cost=125.0 et downtime_minutes=45.
Ils ne couvrent ni predictive ni cancelled ni tous les cas invalides ; ce ne
sont pas des modèles de payload complets garantis. La dernière recette
[UI 7.5](ui-7.5-measurements-integration.md) avait 40 lignes métier, dont trois
maintenances, et un seed strict divergent sur Sensor 1. Valeurs historiques
seulement : aucun compteur, id d'exemple ou état DEV n'est revérifié ici.
Les **1 482 tests Angular, build réussi et initial 605,65 kB** de UI 7.5.2
restent des références Measurements, pas une validation du futur module UI 8.

## 7. Audit frontend et architecture réutilisable

| Existant | Réutilisation envisagée, sans modification maintenant |
| --- | --- |
| [Routes application](../frontend/src/app/app.routes.ts) et [navigation](../frontend/src/app/layout/navigation/navigation.config.ts) | /maintenance existe sous le Shell en placeholder ; future feature lazy avec titre Maintenance et sélection de section |
| [ReferenceDataApiService](../frontend/src/app/core/api/reference-data-api.service.ts), [références](../frontend/src/app/core/models/reference-data.model.ts), [Page](../frontend/src/app/core/models/page.model.ts) | Companies, Sites et Equipments paginés, détails par id et labels métier ; pas de nouveau service core |
| [EquipmentsListFacade](../frontend/src/app/features/equipments/equipments-list.facade.ts) et [MeasurementsListFacade](../frontend/src/app/features/measurements/measurements-list.facade.ts) | Provider local, signals, snapshot URL, switchMap, nettoyage des souscriptions, validation des parents |
| [Equipment Detail](../frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts), [Sensor Detail](../frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.ts), [Measurement Detail](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.ts) | Identifiants sûrs, références réelles indépendantes du retour URL, erreurs parent distinctes, liens conditionnels |
| [EquipmentsApiService](../frontend/src/app/features/equipments/data-access/equipments-api.service.ts), [SensorsApiService](../frontend/src/app/features/sensors/data-access/sensors-api.service.ts), [MeasurementsApiService](../frontend/src/app/features/measurements/data-access/measurements-api.service.ts) | Observable froid, HttpClient, whitelist explicite, validation défensive de réponse ; ne pas copier les méthodes d'écriture par défaut |
| [Equipment Edit](../frontend/src/app/features/equipments/pages/equipment-edit/equipment-edit.component.ts), [Sensor Edit](../frontend/src/app/features/sensors/pages/sensor-edit/sensor-edit.component.ts), [Sensor Form](../frontend/src/app/features/sensors/components/sensor-form/sensor-form.component.ts) | Si écritures autorisées plus tard : forme typée partagée, différentiel, null/omission, saving, erreurs, garde de sortie et récupération |
| [Temps Measurements](../frontend/src/app/features/measurements/utils/measurement-time.ts), [brouillon](../frontend/src/app/features/measurements/utils/measurement-period-draft.ts), [dates administratives](../frontend/src/app/shared/utils/datetime-display.ts) | Composantes UTC et comparaison microseconde, source ISO préservée ; le formateur administratif actuel ne préserve pas les fractions, pas de copie aveugle |
| [PageHeader](../frontend/src/app/shared/components/page-header/page-header.component.ts), LoadingState/EmptyState/ErrorState, [actions](../frontend/src/styles/_actions.scss), [boutons](../frontend/src/styles/_buttons.scss) | Présentation, flex-wrap, hauteur 44 px, secondaire/primaire, hover/actif/focus/disabled/mouvement réduit |
| [Test de navigation Sensor](../frontend/src/app/features/sensors/pages/sensor-detail/sensor-measurements-navigation.spec.ts), [test détail Measurement](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.spec.ts) | RouterTestingHarness, HttpTestingController, contexte contradictoire, erreurs de référence et appels différés |

L'[architecture existante](frontend-architecture.md) confirme des composants
standalone OnPush, routes lazy et gestion du focus dans le Shell après changement
de page. Pas de breadcrumb global livré : proposer un contexte industriel textuel
avec liens réels utiles, sans inventer un composant Breadcrumb ni reconstruire
une identité depuis les query params. Filtres appliqués dans l'URL, brouillon
distinct, pagination serveur, vides et erreurs séparés.

NbToastrService est déjà configuré pour les succès d'écriture. Pas de toast de
création/modification dans un MVP de lecture ; message accessible de chargement
ou d'erreur suffit. Les gardes CanDeactivate et beforeunload appartiendraient aux
formulaires conditionnels, sans promettre qu'une navigation annule un commit.
Le dialogue natif reste une réserve historique des modules d'écriture.

Architecture retenue pour la conception de consultation, **aucun de ces fichiers créé ici** :

```text
features/maintenance/
  models/maintenance.model.ts, maintenance-page-query.model.ts,
         maintenance-state.model.ts
  data-access/maintenance-api.service.ts
  maintenance-list.facade.ts
  maintenance.routes.ts
  pages/maintenance-list/, pages/maintenance-detail/
  utils/ pour libellés et adaptation temporelle si nécessaire
```

MaintenanceRead strict à 18 champs, unions des trois enums, Page réutilisée et
query distincte imposant equipment_id. Service initial : list et getById
uniquement. Whitelist query page/page_size/equipment_id/maintenance_type/status/
priority/start_time/end_time/search. Aucun company_id/site_id vers l'API.
Valider nombres, ids et dates ; aucun sensor_id/measurement_id ne fait partie
du contrat. Refuser un item d'un autre équipement et une réponse détail d'un autre id. Les chaînes
API restent intactes ; les nullable ne sont pas des valeurs par défaut calculées.

Pas de store global, cache partagé, polling ou package nouveau. Réutiliser les
conventions des façades sans les copier intégralement. Une éventuelle extraction
transversale de l'utilitaire temporel sera minimale et testée dans une étape
explicitement autorisée, jamais une refonte Dashboard/Measurements incidente.

## 8. Périmètre MVP et parcours validés pour la consultation

### MVP validé : liste, détail, navigation et finitions UX en lecture seule

Le périmètre de consultation est approuvé. Il permet d'exposer les lectures
existantes sans prétendre résoudre les risques d'écriture. La validation de
conception ne constitue pas une autorisation de commencer UI 8.2.
L'absence de recette Maintenance réelle impose encore une validation DEV future.
Un éventuel contrat Read invalide restera une erreur, jamais un résultat vide.

Liste /maintenance :

1. Entreprise -> Site -> Équipement explicites, sans option choisie automatiquement.
   Catalogues paginés de 50 avec suite ; un choix hors première page se résout
   par id. Changement de parent annule les lectures et vide les descendants.
2. Vérifier Equipment.site_id puis Site.company_id et chaque identité reçue.
   equipment_id seul en URL constitue un choix explicite, complété par les
   parents réels ; des parents contradictoires bloquent sans remplacement caché.
3. Aucun GET liste Maintenance avant Equipment/Site/Company vérifiés. Tous les
   items doivent appartenir à cet équipement. Aucun défaut d'entreprise ou
   liste globale de secours. L'état Equipment n'est pas une autorisation.
4. Filtres type, statut, priorité, recherche explicite et période de création
   UTC [début, fin). Toutes omet l'enum ; pas de défaut de statut cachant les
   interventions terminées. Pas de recherche à chaque frappe.
5. Calendrier/heure/fraction et bouton Appliquer pour la période, sans utiliser
   le brouillon non appliqué. Période invalide : aucune requête élargie ; UI
   explique qu'elle filtre la création du dossier, pas son exécution.
6. Pagination serveur page 1/taille 20, choix 20/50/100 et conservation des tailles
   d'URL valides 1..100. Filtre appliqué -> page 1 ; changement d'équipement ->
   période/recherche effacées et page 1, enums/taille valides conservés.
7. Colonnes proposées : Référence #id, Titre, Type, Statut, Priorité, Planifiée
   le et Création. Pas de code fictif ni compteur ML ; détail pour les textes
   longs, coût et minutes. Format de tableau responsive sans masquer l'accès
   aux champs principaux. La recherche couvre les six champs serveur, y compris
   ceux non affichés comme colonnes ; aide explicite.
8. États catalogue/chargement, sélection attendue, aucun équipement disponible,
   aucune intervention, aucun résultat filtré, page hors plage et erreur séparés.
   Actualiser relit les filtres appliqués ; reprise réseau/5xx manuelle. Page
   hors plage : action manuelle vers une page disponible, sans boucle automatique.

Détail /maintenance/:maintenanceId :

- Tous les champs réels, regroupés en Intervention (id/titre/type/statut/priorité),
  Description et diagnostic (description/failure_code/root_cause/action_taken),
  Technicien, Dates métier, Coût et indisponibilité déclarés, Informations de
  suivi (created_at/updated_at) et Rattachement réel. Texte échappé, null distinct
  de zéro, chaîne vide rendue comme absence de texte sans modifier le transport.
- GET détail puis Equipment -> Site -> Company réels ; données d'intervention
  conservées même si un parent échoue. Erreur parent séparée, aucune identité
  fabriquée depuis le retour URL. Aucun KPI de disponibilité ou retard calculé.
- Id invalide sans HTTP, 404 métier distincte de réseau, réponses obsolètes
  annulées. Source ISO complète et unité « minutes », coût sans devise inventée.
- Retour à la liste secondaire avec snapshot appliqué et pagination préservés.
  Lien Equipment dès GET Equipment réel réussi ; query parent seulement pour
  les références effectivement résolues. Aucun bouton Modifier tant que le lot
  d'écriture n'est pas autorisé et livré, aucun DELETE.

### Navigation industrielle et contextes

Equipment Detail -> « Voir les interventions », secondaire à côté des actions
existantes, seulement si Equipment/Site/Company réellement résolus. Cible :
/maintenance?company_id=...&site_id=...&equipment_id=...&page=1&page_size=20.
N'utiliser aucun filtre status/criticality/search Equipment comme filtre
Maintenance : même nom status, enums et sens différents. Pas de période ni type
Maintenance implicites. Conserver les actions actuelles et leur ordre relatif.

La liste garde company_id/site_id/equipment_id/maintenance_type/status/priority/
search/start_time/end_time/page/page_size dans l'URL, mais company_id/site_id
restent UX seulement. Liste -> détail -> retour conserve le snapshot appliqué,
fractions/offsets, paramètres répétés et fragment, sans suivre un returnUrl externe.
Le détail revalide ses parents réels indépendamment de ce snapshot.

Maintenance -> Equipment utilise l'id réel ; si un contexte de retour Equipment
distinct est prévu, le whitelister sous return_equipment_* avec ses propres
bornes/enums. Sans snapshot valide, utiliser les parents réellement résolus et
page 1/taille 20 ; ne jamais recycler un statut ou type Maintenance dans Equipment.
Le lien entrant minimal Equipment -> Maintenance n'est pas promis comme une
conservation automatique de tous les filtres Equipment. MAIN-11 valide le retour Equipment minimal et la séparation des contextes ;
un snapshot Equipment complet demeure optionnel et nécessite une demande
spécifique. Le retour liste Maintenance doit être intégral.

### Création, modification et transitions : étude hors MVP, chantier séparé

**Aucune création, modification ou transition de statut n'est autorisée par
MAIN-08/MAIN-09, ni planifiée dans UI 8.5.** Les pistes ci-dessous sont conservées
comme étude d'un chantier séparé, sans autorisation d'implémentation. Il exigera
un arbitrage métier, une sécurisation du backend et un accord distinct.

POST/PATCH sont disponibles mais **pas suffisamment sûrs pour autoriser un lot
d'écriture sans arbitrage et corrections séparées**. Une interface prudente
réduit les entrées invalides, mais ne supprime ni les courses SQL, ni le PATCH
fusionné invalide, ni l'incertitude après commit. Ne pas présenter 409/422 comme
une couverture de toutes ces erreurs.

Si ce chantier séparé est expressément autorisé après arbitrage et sécurisation :

- MaintenanceCreate porterait equipment_id vérifié, maintenance_type, title et
  les champs métier facultatifs ; id/dates administratives/parents Company/Site
  exclus. Parent sélectionné explicitement avant le formulaire, immuable après
  création. Pas de choix de la première option ni d'heure « maintenant » simulant
  une acquisition ou intervention réelle.
- Formulaire typé partagé, pages Create/Edit séparées, groupes Identification,
  Diagnostic, Dates, Coût/Indisponibilité ; titre non blanc, maximum 255 caractères,
  failure_code <=50 et technician <=150, limites cohérentes avec SQL en points
  de code Unicode. Aucune unicité inventée du titre/failure_code. Textes longs
  sans limite arbitraire nouvelle ; casse et contenu significatifs conservés.
- Coût facultatif fini >=0, sans devise devinée ; minutes facultatives entières
  >=0 et <=2 147 483 647 pour une écriture SQL Integer. Null reste une absence,
  pas 0 ; règles de saisie décimale française explicitement testées, pas parseFloat
  tolérant une entrée partiellement invalide. Aucun calcul de coût ou de durée.
- Dates métier UTC avec offset et précision conservée. En édition, comparaison
  sur l'ensemble original + modifications, pas sur les deux contrôles seulement.
  Ne pas transformer une date intacte en minuit, fin de journée ou heure locale.
- PATCH whitelist des 14 champs, uniquement différences effectives ; restaurer
  la valeur initiale retire le champ. Aucun PATCH vide, equipment_id, id ou dates
  administratives envoyés. Champs requis non null ; nullable inchangé omis,
  texte effacé volontairement vide et retrait explicite null distingués.
- Type/statut/priorité modifiables seulement selon les règles métier validées,
  pas de bouton Démarrer/Terminer/Annuler prétendant appeler un endpoint absent.
  Éventuelles obligations de dates et interdiction de réouverture à définir en
  MAIN-08, pas imposées rétroactivement aux lectures d'anciennes lignes.
- Saving bloque doubles clics et sorties ; saisies conservées après erreur,
  aucune relance automatique en écriture. Réseau/5xx = issue incertaine, lien de
  vérification puis reprise utilisateur, jamais nouvelle création présumée sûre.
  404 ne recrée rien ; 409 générique ; 422 affecte seulement les champs reconnus.
- Après 201/200, fiche réelle et GET de contrôle ; confirmation et toast uniques
  après navigation réussie. Si navigation échoue, succès verrouillé et lien de
  récupération, sans nouvelle écriture. Garde de sortie et beforeunload selon
  les conventions existantes, dialogue natif à vérifier manuellement.

Ces pistes de formulaire restent à arbitrer hors MVP. Elles ne constituent ni
un nouveau contrat API, ni une correction backend, ni une autorisation donnée
par la validation des décisions MAIN. Dans le MVP de consultation validé, ne
créer aucun DTO ou méthode d'écriture, formulaire, bouton d'ajout même désactivé,
route new/edit ou commande de transition de statut.

### Responsive et accessibilité envisagés

Contrôles à prévoir aux six cibles 1440, 1024, 1023, 768, 390 et 320 px, incluant
la bascule Sidebar 1023/1024. PageHeader et flex-wrap existants, actions de 44 px,
contraste/texte des badges, focus visible, liens clavier, labels et erreurs reliés
aux contrôles. Tableau dans une région nommée défilable localement, aide seulement
quand nécessaire ; aucune barre horizontale globale ni action inaccessible.

Utiliser dl/dt/dd en détail, titres de régions, time avec ISO source, aria-busy
pendant chargement et messages d'erreur/statut accessibles. Pas de statut exprimé
uniquement par couleur. Calendrier natif utilisable au clavier, fraction explicitée.
Captures desktop/mobile et valeurs CSS réellement mesurées ; si 390 exact reste
impossible avec le navigateur, conserver la réserve 389/391, pas un faux succès.
Aucune capture ou recette visuelle Maintenance exécutée dans cette conception.

## 9. Décisions MAIN validées pour le MVP de consultation

**MAIN-01 à MAIN-16 sont validées pour la lecture seule.** L'approbation de
MAIN-08 et MAIN-09 n'autorise aucune implémentation d'écriture, aucun formulaire
ni aucune transition de statut. Leurs mentions de règles ou protections futures
restent des réserves d'un chantier séparé, après arbitrage métier et sécurisation
du backend. Aucune décision ne change MES-01 à MES-12, SEN-01 à SEN-10 ou EQ-01
à EQ-07. Aucune autorisation de commencer UI 8.2 n'est déduite.

| Référence | Décision de conception | Justification et limites | Statut |
| --- | --- | --- | --- |
| MAIN-01 | MVP de consultation : liste/historique, détail, navigation et finitions UX ; écritures exclues | Périmètre approuvé, risques POST/PATCH non résolus ; création/modification/transitions dans un chantier séparé | Validée, consultation uniquement |
| MAIN-02 | Sources backend versionnées comme contrat, DTO Read de 18 champs, pas de métadonnée inventée | Table/DTO réels ; anomalies historiques signalées, pas normalisées silencieusement | Validée, consultation uniquement |
| MAIN-03 | Liste exclusivement GET paginé avec equipment_id obligatoire dans Angular | Backend accepte une liste globale et un GET non paginé, tous deux exclus ; pas d'autorisation tenant induite | Validée, consultation uniquement |
| MAIN-04 | Trois sélections explicites et validation Equipment -> Site -> Company avant GET liste | Parent absent/incohérent bloque ; le détail conserve l'intervention si référence indisponible | Validée, consultation uniquement |
| MAIN-05 | Filtres type/statut/priorité/recherche/période de création, pagination 20/50/100 et tri backend fixe | Query whitelist exacte ; bornes sur created_at, pas planning/exécution ; limites offset/COUNT conservées | Validée, consultation uniquement |
| MAIN-06 | Dates comme ISO, UTC explicite si offset, précision jusqu'aux microsecondes ; période [début, fin) | Réutilisation de la méthode Measurements, sans Date ; dates administratives naïves non réinterprétées | Validée, consultation uniquement |
| MAIN-07 | Coût déclaré sans devise supposée et minutes déclarées, null distinct de 0 | Float non comptable, finitude contrôlée côté lecture ; aucune durée ou agrégation calculée | Validée, consultation uniquement |
| MAIN-08 | Statuts et types uniquement consultés selon les enums exactes ; aucune implémentation d'écriture ni transition autorisée | Règles de workflow à arbitrer dans un chantier séparé ; pas d'automatisme de dates ni preuve IA pour predictive | Validée, consultation uniquement |
| MAIN-09 | Aucun POST/PATCH ni formulaire ou commande de transition dans le MVP ; pistes d'écriture hors périmètre | Aucune autorisation d'implémenter des écritures ; chantier séparé après arbitrage métier, sécurisation B-MAIN et tests | Validée, consultation uniquement |
| MAIN-10 | Aucun DELETE, transfert, nettoyage de doublons ou cascade déclenchés par l'UI | Historique industriel non archivé ; politique de rétention hors périmètre | Validée, consultation uniquement |
| MAIN-11 | Equipment <-> Maintenance par références réelles, contextes séparés, retour liste Maintenance intégral | Page 1/taille 20 à l'entrée ; pas de filtres Equipment recyclés ; snapshot Equipment complet optionnel à arbitrer | Validée, consultation uniquement |
| MAIN-12 | Erreurs distinctes référence/lecture/donnée invalide, relance manuelle en lecture seulement | Pas de fausse page vide ou valeur zéro ; en écriture future, issue incertaine sans retry automatique | Validée, consultation uniquement |
| MAIN-13 | Réutiliser composants, styles harmonisés, focus et tests de navigation existants | Aucun breadcrumb global inventé, package ou refonte des autres modules ; six largeurs à vérifier | Validée, consultation uniquement |
| MAIN-14 | Authentification, autorisation de ressource et isolation multi-tenant restent bloquantes avant exposition SaaS | Filtres et cohérence de parents ne sécurisent pas le backend ; pas de promesse de production | Validée, consultation uniquement |
| MAIN-15 | Tests Angular simulés puis recette DEV exclusivement en lecture seule, avec compteurs/empreintes avant/après | Identité DEV prouvée avant accès, aucune donnée historique corrigée ; recette d'écriture réservée au chantier séparé | Validée, consultation uniquement |
| MAIN-16 | Questions de dates générées, devise, workflow et correction auditée suivies comme dettes backend distinctes | Ne pas corriger le serveur dans UI 8.1 ni maquiller ses limites par une règle UI | Validée, consultation uniquement |

## 10. Anomalies et évolutions séparées

| Référence | Constat et action proposée | Effet sur la suite |
| --- | --- | --- |
| B-MAIN-01 | Revalider chronologie sur dossier fusionné avant flush/commit ; éviter une réponse Read invalide après écriture | Bloquant pour PATCH fiable ; cas reproduit en mémoire, HTTP/SQL non exécutés |
| B-MAIN-02 | Aligner null/NOT NULL, longueurs et contenu non blanc, ids positifs entre DTO et SQL | Risque 5xx d'écriture et données pauvres ; corrections à autoriser séparément |
| B-MAIN-03 | Refuser non-finis/coercitions arbitraires, borner minutes SQL Integer, définir la précision des coûts | Risque coût infini et dépassement entier ; pas de devise inventée |
| B-MAIN-04 | Définir règles de transitions, dates exigées, réouverture et éventuel verrou des dossiers clôturés | Lacune métier à arbitrer, pas violation d'une machine à états déjà livrée |
| B-MAIN-05 | Traduire erreurs SQL avec rollback contrôlé, traiter concurrence/idempotence et réponse après commit | Couverture CRUD isolée nécessaire avant écritures ; 409 actuel non exhaustif |
| B-MAIN-06 | Clarifier défauts administratifs UTC aware et valider sérialisation/réhydratation PostgreSQL | Pas d'ajout automatique de Z aux données historiques ni migration implicite |
| B-MAIN-07 | Authentification, autorisation par ressource et isolation tenant | Prérequis d'exposition SaaS ; hors frontend de consultation |
| B-MAIN-08 | Mesurer COUNT/offset et intérêt d'un index équipement/created_at/id, cohérence des pages | Besoin potentiel pour volumes réels, aucune migration justifiée par l'audit seul |
| B-MAIN-09 | Devise et précision monétaire, audit/version des corrections, conservation et archivage | Évolutions métier hors MVP, à concevoir avant garanties comptables ou réglementaires |

La répétition du contrôle de période est une dette de lisibilité mineure, pas
un blocage de la liste. Aucun équivalent de SensorRepository.get_by_code manquant
n'a été trouvé sur les chemins Maintenance examinés. La sécurité et la recette
réelle restent à établir : « code de lecture présent » ne signifie pas « nouvelle
intégration Maintenance validée ».

## 11. Stratégie de tests envisagée

### Angular sans base

- HttpTestingController : URLs singulières exactes, seulement GET paginé/détail
  au lot initial, ids sûrs, query whitelist, alias status, types/priorités et
  valeurs optionnelles null/omises, cinq dates Read, coût/minutes null/0/invalides.
- Pagination 1..100, hors plage, total nul ; absence de company_id/site_id,
  tri/paramètre de planning inventé, POST/PATCH/DELETE ou endpoint non paginé.
- UTC avec offset et six décimales, bornes unilatérales, égalité/inversion,
  naïf métier/admin distincts, précision et absence de conversion Date ; parent
  ou date invalide ne doit pas élargir la query. Filtre de création clairement nommé.
- Façade : choix explicites même si une seule option, suite des catalogues,
  parent hors première page, FK contradictoires, 404/403/réseau, changements
  rapides et annulation, item d'un autre équipement refusé.
- Navigation RouterTestingHarness : Equipment -> Maintenance conditionnelle,
  ids exacts, pagination réinitialisée et aucun filtre Equipment transmis ;
  liste/détail/retour avec bornes, offset, filtres et page, pas de double navigation.
- Détail : 18 champs et nulls, chronologie incohérente signalée, référence absente
  sans perte du dossier, aucun faux parent, aucune devise ni code inventés,
  pas de toast d'écriture, statut predictive sans message IA.
- Accessibilité/responsive : focus, lecture du tableau, labels, état busy,
  erreurs, absence de débordement et captures aux six cibles.

Après toute étape exécutable autorisée : tests ciblés, suite Angular complète
et build séquentiels, poids initial/chunks signalé sans hausse artificielle des
budgets. La référence de départ reste 1 482 tests/build/605,65 kB, non relancée ici.

### Backend si corrections séparément autorisées

Prévoir des fixtures réellement isolées, jamais une URL DEV/historique héritée :
création 201, Equipment absent 409, détail 200/404, PATCH 200, null requis rejeté,
longueurs Unicode, limites entières, Infinity/NaN, défauts timezone PostgreSQL et
PATCH une date confrontée à l'autre déjà stockée. Échec validé avant commit et
lecture ultérieure possible ; erreurs d'intégrité/rollback et transactions
concurrentes à tester sans assouplir les assertions. Tester les transitions
seulement après décision métier, pas selon une règle inventée par le test.

La suite actuelle de pagination ne couvre pas ces écritures. Ne pas lancer la
découverte SQL existante sans vérifier son routage et ses droits de création de
schéma. Aucune base de test nouvelle n'est présumée déjà provisionnée.

## 12. Plan de recette DEV future et garde-fous

Ce plan n'est **pas exécuté** et ne donne aucune autorisation d'écriture actuelle.
Référence opérationnelle : [guide DEV](../infra/development/README.md).

1. Avant recette autorisée, vérifier branche/HEAD attendus et absence de changement
   exécutable inattendu ; relire la procédure, pas de redémarrage/réinitialisation
   PostgreSQL automatique ni de fallback si un service manque.
2. Prouver identité concordante Angular 4201/API 8001 via /__dev/identity, santé
   API, base industrial_predict_dev sur 127.0.0.1:5434, rôle ui47_app non privilégié,
   instance attendue et migrations conformes au guide (référence 09ac8101e9fe).
   Ne pas afficher secrets ni DSN. Arrêter tout accès métier si identité ambiguë.
3. Lectures SQL seulement, transaction READ ONLY explicite : relever compteurs,
   empreintes de toutes les colonnes des huit tables et empreintes par id. Ne pas
   supposer 40 lignes aujourd'hui ; ce nombre est une référence historique.
   Relever le capteur 1 et l'écart seed connu, sans le corriger ou déclarer le
   check strict conforme. Ne jamais accéder à la base historique.
4. Depuis Angular, trois choix explicites et contrôle des GET ; aucun GET
   Maintenance avant résolution complète. Vérifier les id/FK et la liste de
   l'équipement, filtres réellement représentés, vide non filtré/filtré et pagination.
5. Capturer les URL effectivement observées, puis GET 200 et corps selon les
   capacités de l'outil ; si corroboration indépendante nécessaire, la distinguer
   d'une réponse interceptée. Comparer les 18 champs, total et ordre à SQL.
6. Vérifier la période sur created_at avec bornes réelles à la microseconde
   uniquement si les données existantes le permettent ; ne pas modifier une
   ligne pour obtenir un cas. Sinon conserver une réserve et utiliser les tests
   simulés pour les données non représentées.
7. Ouvrir un dossier réel, références, coût/minutes/dates exacts, retour contextuel
   et liens Equipment. Ne pas provoquer 5xx, doublons, cascade ou conflit par
   écriture. Identifier les types/statuts/priorités absents du jeu réel.
8. Relever les mêmes compteurs/empreintes après consultation ; exiger égalité
   sur les huit tables et toutes les lignes préexistantes. Documenter preuves
   réelles, simulations et limites séparément, sans nouvelle donnée de test.

Pour le chantier séparé d'écriture, hors MVP UI 8, prévoir **une autre autorisation
de recette**, après sécurisation du backend et arbitrages métier : nouveau dossier fictif dédié sur
Equipment préalablement vérifié, payloads minimaux, aucune modification des
lignes existantes ni DELETE de nettoyage, comparaison par id des anciennes
empreintes et conservation du dossier d'essai. Aucun test réel de concurrence ou
d'intégrité en multipliant les écritures. Le protocole exact doit être approuvé
avant son exécution ; il n'est pas implicite dans la validation de ce document.

## 13. Découpage du MVP de consultation validé

| Étape | Contenu retenu | Condition de passage |
| --- | --- | --- |
| UI 8.1 | Audit et conception, présent rapport ; MAIN-01 à MAIN-16 validées pour la consultation | Actualisation documentaire finale à valider avant commit ; aucun développement |
| UI 8.2 | Modèles Read/enums/query stricts et API GET uniquement | Autorisation distincte avant développement ; tests transport, aucune route ou formulaire anticipé |
| UI 8.3 | Liste, choix explicites, catalogue, filtres réels et pagination | Références et dates bien distinguées, tests et responsive |
| UI 8.4 | Fiche détail en lecture seule et retour à la liste | Parents réels, contexte préservé, données conservées sur erreur parent |
| UI 8.5 - Navigation et finitions UX | Navigation Equipment <-> Maintenance, actions harmonisées, contextes séparés, focus et responsive | Aucun formulaire, écriture ou transition ; vérification des six cibles et non-régression |
| UI 8.6 | Recette réelle DEV de consultation uniquement | Identité/compteurs/empreintes avant et après ; aucune écriture PostgreSQL |
| UI 8.7 | Documentation, bilan et checklist de livraison | Résultats historiques exacts, réserves visibles, commit/fusion séparément autorisés |

La création, la modification et les transitions sont reportées dans un chantier
séparé, après arbitrage métier et sécurisation du backend. Elles ne constituent
ni une sous-étape conditionnelle UI 8.5, ni une extension implicite de UI 8.2.
Les anomalies B-MAIN restent ouvertes ; aucune correction backend n'est incluse
au présent MVP. Aucun début UI 8.2 dans cette mission.

## 14. Questions à arbitrer et critères d'acceptation

Arbitrages de conception actés pour le MVP de consultation :

1. MAIN-01 validée : liste/détail, navigation et finitions UX uniquement en
   lecture seule. Aucun DTO, formulaire ou méthode d'écriture à implémenter.
2. Filtre de **création du dossier** retenu. Une recherche par date planifiée,
   début/fin d'exécution ou agenda nécessiterait une évolution API séparée.
3. Coût sans devise supposée et distinction minutes déclarées/durée écoulée
   confirmés ; aucune garantie comptable inventée à partir du Float existant.
4. Retour contextuel Equipment minimal et séparation des filtres confirmés.
   Un éventuel snapshot complet demeure optionnel et demanderait un arbitrage
   spécifique. Le retour à la liste Maintenance conserve intégralement son contexte.
5. Dates administratives naïves : ne jamais ajouter Z ni supposer UTC sans
   offset ou preuve de conversion fiable. Aucune conversion automatique approuvée.

Ces arbitrages ne constituent pas une autorisation de commencer UI 8.2.

Questions restant à arbitrer pour le chantier séparé d'écriture, hors MVP UI 8 :

- Qui peut créer/corriger, sur quels statuts ; quelles transitions/réouvertures,
  dates exigées et verrouillage des dossiers terminés/annulés ?
- Le statut initial reste-t-il planned/priority medium selon le backend,
  sans dates automatiques ? Toute restriction supplémentaire est une décision.
- Quel traitement des dates administratives naïves et des défauts ORM avant
  garanties UTC en base ? Qui autorise les correctifs B-MAIN-01/02/03/05/06 ?
- Quel niveau d'audit/version et de concurrence est requis pour la correction
  d'un historique ayant un impact analytique ? La sécurité SaaS reste distincte.

Critères de clôture documentaire UI 8.1 :

- Branche dédiée issue du main attendu et dépôt initial propre vérifiés ; main
  et origin/main restent à 15c956b. Seul ce document non suivi, index vide.
- Contrat à 18 champs, six endpoints, enums, erreurs, périodes sur created_at,
  différences SQL/Pydantic et transactions explicités avec sources du dépôt.
- MVP de consultation distinct du chantier séparé d'écriture et des fonctions
  absentes ; MAIN-01 à MAIN-16 validées uniquement pour la lecture seule,
  MAIN-08/MAIN-09 sans autorisation d'écriture ou de transition.
- UI 8.5 consacrée à la navigation et aux finitions UX, UI 8.6 exclusivement en
  lecture ; aucune création ou modification dans le découpage UI 8.
- Réserve sur dates administratives naïves explicite : sans offset ou preuve
  de conversion fiable, ne jamais ajouter Z ni supposer UTC.
- Réutilisation cohérente des modules UI 5/6/7, aucune modification de leurs
  règles métier, de leurs sources ou de leurs rapports historiques.
- Liens et contenu technique vérifiés, français sans tiret cadratin, espaces
  et git diff --check contrôlés ; tests SQL et recette DEV non exécutés.
- Aucun changement frontend/backend exécutable, migration, Docker, package,
  commit, push ou merge, aucune écriture PostgreSQL ni accès historique.

État de livraison du rapport : docs/ui-8-maintenance-design, HEAD 15c956b
inchangé, seul docs/etape-ui-8.1-maintenance.md ajouté non suivi. Décisions de
consultation validées ; actualisation finale du rapport à présenter pour validation
avant commit. Aucune autorisation de commencer UI 8.2 n'est déduite.
