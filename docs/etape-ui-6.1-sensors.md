# UI 6.1 - Audit et conception du module Capteurs

20 octobre 2026. **Conception métier validée : SEN-01 à SEN-10 approuvées par l’utilisateur.**

Branche vérifiée : `feature/frontend-sensors`. HEAD audité :
`a76e49c1aea1999f5bbdefb76df7ee1fcce3b448`. `git status --short` vide avant
intervention : dépôt propre. Aucune création ou modification de branche, aucun
fetch, commit, push ou merge. La propreté finale attendue concerne uniquement
l'ajout du présent document.

Actualisation de validation métier : branche et HEAD de référence reconfirmés.
Le document était déjà non suivi au début de cette actualisation ; seul ce fichier
est modifié. Les tests de schémas ci-dessous sont les résultats de l’audit initial,
sans nouvelle exécution dans cette actualisation. Les tests B-SEN-01 restent proposés.

## 1. Périmètre, méthode et preuves

Audit des sources versionnées et conception Angular uniquement. Aucun changement
applicatif, backend, SQL, migration, Docker ou package. UI 6.2 n'est pas commencée
et aucune étape de développement n'est autorisée par ce document.

Sources backend examinées :

- [Modèle Sensor](../backend/app/models/sensor.py), [schémas Sensor](../backend/app/schemas/sensor.py), [repository](../backend/app/repositories/sensor_repository.py), [service](../backend/app/services/sensor_service.py), [routes](../backend/app/api/routes/sensors.py).
- [Migration Sensors](../backend/migrations/versions/572080d9e581_create_sensors_table.py), [énumérations](../backend/app/core/enums.py), [montage API](../backend/app/main.py), [Page](../backend/app/schemas/pagination.py), [calcul de pagination](../backend/app/core/pagination.py).
- [Company](../backend/app/models/company.py), [Site](../backend/app/models/site.py), [Equipment](../backend/app/models/equipment.py), [Measurement](../backend/app/models/measurement.py), [PredictionRecord](../backend/app/models/prediction_record.py).
- [Schémas Measurements](../backend/app/schemas/measurement.py), [routes Measurements](../backend/app/api/routes/measurements.py), [service Measurements](../backend/app/services/measurement_service.py), [repository Measurements](../backend/app/repositories/measurement_repository.py).
- [Tests de validation](../tests/business_validation/test_schemas.py), [tests de pagination et filtres](../tests/pagination_filters/test_routes.py), [fixture SQL des tests](../tests/dashboard/support.py).

Vérifications exécutées :

- 33 tests de `business_validation.test_schemas` réussis avec
  `backend/.venv/Scripts/python.exe -B`, chemins `backend` et `tests` ajoutés
  uniquement au processus. Ces tests incluent les enums Sensors, le défaut
  `active`, l'unité obligatoire et non vide et le PATCH partiel.
- Contrôles Pydantic ponctuels : textes name/code/sensor_type vides acceptés,
  longueurs 151/101/101/31 acceptées pour name/code/sensor_type/unit, unité
  blanche acceptée, equipment_id égal à 0 ou -1 accepté au niveau schéma.
  PATCH vide donne `{}` avec `exclude_unset`; null explicite est accepté pour
  les champs PATCH. Un champ inconnu comme company_id est ignoré par le schéma.
- Inspection AST du repository : neuf méthodes présentes, aucune `get_by_code`.
  Le processus de validation n'a pas importé `app.core.database`.
- Une première tentative avec Python global a échoué, car Pydantic y est absent.
  Aucun package installé ; vérification reprise avec succès dans le venv existant.

Les tests de routes ont été lus, sans être exécutés : leur fixture crée des
tables et des données SQLite ou PostgreSQL selon l'environnement. Aucun serveur,
appel HTTP, moteur SQL, accès aux données réelles, test de cascade, seed, build
Angular ou commande Docker lancé ici. Les comportements HTTP et SQL ci-dessous
sont établis par lecture du code, pas par une recette réelle de cette étape.

## 2. Bilan des capacités existantes

Le backend expose la consultation paginée, le détail, la création, le PATCH et
la suppression définitive de Sensors. **Le contrat CRUD déclaré ne garantit pas
un CRUD fonctionnel : la création et le PATCH de code sont bloqués par une
méthode repository manquante.** Les lectures et les PATCH sans code ne passent
pas par cette méthode ; leur fonctionnement de bout en bout reste à valider.

Le frontend possède une entrée Capteurs `/sensors` qui ouvre un placeholder.
Aucun module CRUD Sensors, DTO SensorRead ou service Sensors dédié n'existe
dans les sources examinées. Companies, Sites et Equipments disposent de vrais
modules, à utiliser comme conventions et non comme preuve du fonctionnement Sensors.

### 2.1 Champs, types et contraintes

SensorRead contient exactement les dix champs ci-dessous, sans objet parent
imbriqué ni liste de mesures.

| Champ | Création API | PATCH API | SQLAlchemy / migration |
| --- | --- | --- | --- |
| id | Non déclaré | Non déclaré | Entier, clé primaire, index ; lecture uniquement |
| name | str requis | str ou null, facultatif | VARCHAR(150), NOT NULL |
| code | str requis | str ou null, facultatif | VARCHAR(100), NOT NULL, index unique global |
| sensor_type | str requis | str ou null, facultatif | VARCHAR(100), NOT NULL |
| unit | str requis, min_length=1 | str ou null, facultatif ; min_length=1 si chaîne | VARCHAR(30), NOT NULL |
| description | str ou null, défaut null | str ou null, facultatif | TEXT nullable, pas de maximum métier déclaré |
| status | SensorStatus, défaut active | SensorStatus ou null, facultatif | VARCHAR(50), NOT NULL, défaut ORM active |
| equipment_id | int requis, sans ge=1 | int ou null, facultatif, sans ge=1 | FK NOT NULL vers equipments.id, index, ON DELETE CASCADE |
| created_at | Non déclaré | Non déclaré | DateTime sans fuseau, défaut Python datetime.utcnow |
| updated_at | Non déclaré | Non déclaré | DateTime sans fuseau, défaut datetime.utcnow, onupdate datetime.utcnow |

Les longueurs SQL ne sont pas validées par Pydantic. Name, code et sensor_type
n'ont ni minimum ni maximum API. Unit refuse `""` mais accepte `" "` et n'a pas
de maximum API. Aucun trim, passage en minuscules ou normalisation Unicode
n'est effectué sur les écritures par le service. Ne pas confondre acceptation
Pydantic et succès de persistance PostgreSQL.

Valeurs de status : `active` (libellé proposé « Actif »), `inactive` (« Inactif »).
Les libellés français ne sont jamais envoyés. Les enums rejettent casse différente,
espaces et valeurs inconnues. La colonne SQL est une chaîne, sans CHECK de statut
dans la migration examinée. Une valeur historique hors enum peut donc provoquer
une erreur de validation de réponse ; un fallback UI ne peut pas réparer cette
erreur serveur.

Sensor_type et unit sont des textes libres. Aucun catalogue, enum de type,
compatibilité type/unité, fréquence, seuil, précision, plage physique, numéro de
série, calibration ou protocole n'est fourni. Ne pas créer ces champs dans l'UI.
Les dates sont produites par l'ORM, sans server_default dans la migration initiale.
Ne pas inventer de fuseau pour les dates administratives reçues sans offset.

### 2.2 Endpoints exacts

Préfixe commun constaté dans main.py : `/api/v1`. Chemins sans slash terminal.

| Méthode et chemin complet | Réponse de succès | Erreurs et particularités |
| --- | --- | --- |
| GET `/api/v1/sensors` | 200 Page[SensorRead] | 422 si query invalide ; aucune validation d'existence du parent filtré |
| GET `/api/v1/sensors/{sensor_id}` | 200 SensorRead | 404 `Sensor not found` ; 422 si chemin non convertible en entier |
| GET `/api/v1/sensors/equipment/{equipment_id}` | 200 liste de SensorRead | Non paginé, tri id ASC ; équipement absent donne normalement `[]`, pas de contrôle parent |
| POST `/api/v1/sensors` | 201 SensorRead prévu | 422 validation ; 409 ValueError avec rollback ; défaut bloquant décrit ci-dessous |
| PATCH `/api/v1/sensors/{sensor_id}` | 200 SensorRead prévu | 404 absent ; 422 validation ; 409 ValueError avec rollback ; PATCH partiel |
| DELETE `/api/v1/sensors/{sensor_id}` | 204 sans corps | 404 absent ; suppression définitive, sans garde métier sur les descendants |

Les identifiants de chemin sont des int sans borne positive explicite. Un entier
négatif n'est pas rejeté comme tel par le validateur de chemin ; une lecture par
id sans correspondance conduit au 404. L'UI proposera des entiers positifs sûrs.
Aucun PUT, bulk, import/export, archivage, restauration ou endpoint de transfert
dédié n'est présent.

### 2.3 Pagination, filtres et recherche

| Paramètre GET liste | Type et bornes | Défaut |
| --- | --- | --- |
| page | int >= 1 | 1 |
| page_size | int de 1 à 100 | 20 |
| equipment_id | int >= 1, facultatif | absent |
| status | active ou inactive, facultatif | absent |
| search | str de 1 à 100 caractères, facultative | absente |

Page renvoie `items`, `total`, `page`, `page_size`, `pages`. Pages vaut
ceil(total/page_size), ou 0 quand total=0. Une page hors plage renvoie des items
vides avec un total éventuellement positif ; ni 404 ni recalage automatique.
Tri fixe id ASC, sans option de tri. Items et total sont deux lectures séparées,
sans garantie d'instantané immuable sous concurrence.

Les filtres sont combinés par ET. Search fait un OU entre name, code,
sensor_type et unit avec ILIKE `%terme%`. Le service retire les espaces aux
extrémités ; une recherche entièrement blanche devient une absence de filtre.
`search=` est néanmoins refusé par min_length avant ce traitement. `%` et `_`
restent des jokers SQL non échappés ; la requête SQLAlchemy est paramétrée.
Aucune recherche sur description, équipement, site ou entreprise, ni garantie
d'insensibilité aux accents. Aucun filtre dédié sensor_type ou unit, aucun
filtre company_id/site_id, aucun agrégat entreprise ou site.

La liste globale sans equipment_id existe côté API mais n'est pas proposée pour
le MVP ci-dessous. Un equipment_id inexistant peut donner une page vide ; cela
ne démontre pas l'existence du parent. Les paramètres query inconnus ne sont
pas des filtres implémentés : ne jamais envoyer company_id ou site_id à Sensors.

### 2.4 Validation de service, défaut bloquant et erreurs

Création : recherche de l'équipement, puis contrôle d'unicité via
`self.repository.get_by_code(data.code)`, puis construction et persistance.
Si l'équipement n'existe pas : ValueError convertie en 409 avec le texte
`Equipment with id '…' does not exist.`

**B-SEN-01 : SensorRepository ne définit pas get_by_code, et n'hérite pas d'un
repository qui la fournirait.** Pour un équipement existant, le POST atteint
donc un AttributeError avant création. L'exception n'est pas capturée par le
handler ValueError de la route ; un déploiement standard produit une erreur
serveur 500. Il ne s'agit pas d'un conflit de code géré. Constat statique,
confirmé par inspection AST, sans requête POST réelle.

PATCH : le capteur doit exister. Le service utilise `model_dump(exclude_unset=True)`.
Si equipment_id est fourni, il vérifie le nouvel équipement, sans restriction
d'entreprise. Si code est fourni, même inchangé, il appelle get_by_code et
rencontre le même défaut. Le contrôle prévu exclut le capteur courant du conflit,
mais ce comportement est actuellement inaccessible. Si code est omis, le défaut
ne s'applique pas ; les autres champs peuvent être transmis à la persistance.

Le texte prévu `Sensor with code '…' already exists.` et le 409 associé ne sont
donc pas garantis actuellement. Après correction éventuelle, 409 restera ambigu
entre code dupliqué et parent absent : ne pas attribuer tous les 409 au champ Code,
contrairement au traitement spécifique Companies.

Omission PATCH conserve la valeur ; description `""` et description null sont
distinctes. Null explicite sur equipment_id échoue au contrôle de parent et
conduit au 409 prévu. Null sur les autres colonnes obligatoires peut atteindre
SQL NOT NULL ; code:null rencontre d'abord la méthode absente. Aucun handler
global d'IntegrityError n'a été trouvé : dépassement SQL, course d'unicité ou FK
peuvent conduire au 500 plutôt qu'au 409/422. Les repositories commitent déjà,
puis le service répète commit/refresh : pas de transaction métier unique promise.

Un PATCH `{}` est accepté au niveau schéma ; aucune règle ne garantit une nouvelle
date updated_at sans modification SQL. Aucun ETag, version, verrou optimiste ou
clé d'idempotence n'est fourni. Ne pas renvoyer une écriture automatiquement après
un échec réseau ou 5xx dont le résultat peut être incertain.

### 2.5 Couverture et sécurité

Les tests versionnés de pagination couvrent Sensors : structure, défauts, bornes,
pages hors plage, tri, recherche sur les quatre champs, casse, espaces, filtres
combinés, total filtré et statut invalide. Ces tests ont été examinés, pas relancés.
Les fixtures insèrent directement les modèles, ce qui contourne SensorService.create
et explique pourquoi elles ne détectent pas get_by_code manquant. Aucun test CRUD
Sensors dédié couvrant ce défaut, les null SQL, les conflits ou cascades n'a été
identifié dans les suites examinées. Les tests du détecteur d'anomalies capteur
ne valident pas ce CRUD.

Les routes Sensors ont uniquement Depends(get_db), sans authentification, contrôle
de rôle, autorisation de ressource ou isolation tenant. Ni filtre equipment_id,
ni sélection frontend, ni vérification d'existence du parent ne protège l'accès.
Le backend permet aussi les lectures globales et la liste par équipement non
bornée. La pagination limite la taille de réponse courante, sans limite de page,
de débit ou de coût de recherche dédiée constatée. Aucun filtre UI ne doit être
présenté comme une garantie de sécurité multi-tenant.

## 3. Relations et conséquences métier

Chaîne réelle : **Company -> Site -> Equipment -> Sensor -> Measurement**.
Sensor porte seulement equipment_id ; site_id se déduit de Equipment.site_id,
puis company_id de Site.company_id. Un capteur peut n'avoir aucune mesure.

- Suppression : Equipment.sensors et Sensor.measurements déclarent
  `cascade="all, delete-orphan"`. Les FK équipement vers capteur et capteur vers
  mesure déclarent ON DELETE CASCADE. Supprimer un capteur implique donc ses
  mesures ; les PredictionRecord qui référencent le capteur ou ses mesures ont
  aussi des FK CASCADE. Pas de corbeille, d'estimation d'impact ou de protection
  de l'historique. Cascades constatées dans les sources, sans essai destructif.
- Réaffectation : le PATCH accepte un autre equipment_id existant, y compris dans
  une autre entreprise. Les mesures conservent sensor_id et sont alors rattachées
  au nouvel équipement par déduction. Aucun historique de rattachement n'existe.
  PredictionRecord contient son propre equipment_id : il n'est pas synchronisé
  par SensorService lors du transfert, avec risque d'incohérence historique.
- Changer unit ou sensor_type ne convertit aucune valeur Measurement, ne vérifie
  aucune compatibilité et ne versionne pas la signification des mesures passées.
  Measurement ne possède pas de champ unité historique propre.
- Passer inactive ne supprime pas les mesures et ne bloque pas MeasurementService.create,
  qui contrôle seulement l'existence du capteur. Aucune commande d'arrêt matériel,
  de collecte, de recalcul IA ou de changement du statut Equipment n'est déclenchée.

### Lien avec Measurements

L'API existe, mais `/measurements` est encore un placeholder frontend. Il est
proposé de différer l'écran de mesures et tout lien présenté comme fonctionnel.
La fiche Sensor ne chargera pas ses mesures et n'affichera ni faux compteur,
ni dernière valeur, graphique, badge de transmission ou état temps réel.

Pour un chantier ultérieur, GET `/api/v1/measurements?sensor_id=...` est paginé
(page 1, taille 20, maximum 100), filtrable par quality et dates start_time/end_time.
Quality autorise good/suspect/bad/missing/estimated. Dates avec fuseau ; période
start_time < end_time, début inclus et fin exclue, tri timestamp DESC puis id DESC.
Dates naïves ou période invalide donnent 400 ; query invalide donne 422. Un capteur
absent filtré peut donner une page vide, sans preuve d'existence.

Les variantes GET `/api/v1/measurements/sensor/{sensor_id}` et
`/api/v1/measurements/sensor/{sensor_id}/period?start_time=...&end_time=...`
sont non paginées et contrôlent l'existence du capteur (409 si absent). La variante
period utilise une fin incluse, accepte début=fin et un tri timestamp ASC ; son
service n'applique pas le même contrôle de fuseau que la liste paginée. Ne pas
interchanger ces contrats ni charger tout l'historique pour calculer un compteur.

## 4. Conventions frontend examinées

Sources principales : [routes Angular](../frontend/src/app/app.routes.ts),
[CompaniesApiService](../frontend/src/app/features/companies/data-access/companies-api.service.ts),
[SitesApiService](../frontend/src/app/features/sites/data-access/sites-api.service.ts),
[EquipmentsApiService](../frontend/src/app/features/equipments/data-access/equipments-api.service.ts),
[ReferenceDataApiService](../frontend/src/app/core/api/reference-data-api.service.ts),
[formulaire Equipment](../frontend/src/app/features/equipments/components/equipment-form/equipment-form.component.ts),
[façade Equipment](../frontend/src/app/features/equipments/equipments-list.facade.ts),
[références de création](../frontend/src/app/features/equipments/pages/equipment-create/equipment-create-references.facade.ts),
[détail Equipment](../frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts),
[édition Site](../frontend/src/app/features/sites/pages/site-edit/site-edit.component.ts),
[bilan UI 5.8](ui-5.8-equipments-delivery.md), [règles visuelles](ui-design.md).

Conventions à reprendre après accord :

- Angular 21 existant, composants standalone OnPush, routes lazy, formulaires
  réactifs typés, signaux pour les états et RxJS switchMap pour annuler les lectures
  obsolètes. Aucun nouveau package, store global ou changement Shell nécessaire.
- Structure feature avec data-access, models, façade de liste, formulaire partagé
  création/édition et pages distinctes. DTO de lecture séparé des DTO d'écriture.
- PageHeader, LoadingState et ErrorState partagés ; boutons harmonisés avec
  Nouvelle entreprise, tokens et thème Nebular existants. Statuts accompagnés de
  texte, labels liés aux champs, erreurs accessibles, focus utile, clavier.
- Companies sans parent ; Sites exige une entreprise ; Equipments exige entreprise
  puis site et vérifie l'appartenance. Références paginées par 50 avec chargement
  supplémentaire explicite, déduplication et conservation des pages après erreur.
  Une référence absente de la première page n'est pas déclarée inexistante.
- Recherche explicite par bouton ou Entrée, snapshot appliqué dans l'URL,
  pagination serveur 20/50/100 ; pas de recherche à chaque frappe ni tri local.
- Détail : rattachement réel indépendant du contexte de retour, erreurs parent
  distinctes sans effacer les données métier. Libellés nom/code via
  businessReferenceLabel, dates via formatAdministrativeDateTime.
- Écriture : whitelist de payload, PATCH différentiel, saisies conservées après
  erreur, garde de sortie et beforeunload, double soumission bloquée, aucun retry
  automatique ; succès confirmé une seule fois avec récupération si navigation échoue.

ReferenceDataApiService fournit déjà getCompanies/getCompanyById,
getSites(companyId)/getSiteById et getEquipments(siteId)/getEquipmentById.
La cascade de références Sensors peut donc réutiliser ces lectures, sans nouvelle
route backend ni modification du contrat Dashboard. La convention de Companies
« tout 409 cible Code » ne sera pas copiée.

## 5. Décisions métier validées

Les dix décisions SEN-01 à SEN-10 sont explicitement approuvées par l’utilisateur
le 20 octobre 2026, sur la branche `feature/frontend-sensors`, HEAD de référence
`a76e49c`. Cette validation porte sur la conception métier. Elle n’autorise ni
le correctif backend B-SEN-01 ni le démarrage UI 6.2. Les réserves backend de
l’audit restent applicables ; les capacités déclarées ne deviennent pas, par
cette validation, des écritures opérationnelles.

| Référence | Décision MVP validée | Motif et limites maintenues |
| --- | --- | --- |
| SEN-01 | Liste et création après sélection explicite entreprise -> site -> équipement, aucun premier choix automatique | equipment_id obligatoire dans l'UI, aucune vue fusionnée multi-équipements ; restriction à la liste globale backend approuvée |
| SEN-02 | Rattachement immuable en édition, même dans la même entreprise | equipment_id exclu du PATCH Angular ; tout transfert et son historique nécessitent une conception distincte |
| SEN-03 | Aucun DELETE dans l'interface ni dans le futur service Angular MVP | Éviter la suppression irréversible des mesures et prédictions ; aucune action désactivée simulant une capacité livrée |
| SEN-04 | Code éditable, unicité globale toutes entreprises et tous équipements confondus | Pas d'unicité locale, pas de contrôle par chargement de tous les capteurs, pas de normalisation de casse ; dépend de B-SEN-01 |
| SEN-05 | Type et unité en texte libre ; les fixer en lecture seule en édition MVP | Les mesures historiques n'ont ni unité versionnée ni conversion ; corriger type/unité exige un futur arbitrage dédié, pas un faux contrôle « aucune mesure » |
| SEN-06 | Statut éditable entre active/inactive, défaut active visible en création | Statut administratif uniquement ; aucune promesse d'arrêt d'acquisition ou de contrôle physique |
| SEN-07 | Fiche Sensor sans liste de mesures, compteur ni lien actif vers le placeholder Measurements | Futur lien prévu avec sensor_id quand le module cible sera livré ; aucun affichage temps réel ou calcul IA |
| SEN-08 | Lien « Voir les capteurs » depuis Equipment, lien vers l'équipement réel depuis Sensor | Références réelles validées ; contexte de retour conservé séparément ; pas d'élargissement Companies/Sites |
| SEN-09 | Nom/code/type/unité non blancs en création, limites Unicode 150/100/100/30 | Garde frontend plus stricte que Pydantic, conforme aux colonnes ; garde approuvée, description libre sans maximum arbitraire |
| SEN-10 | Planifier un correctif B-SEN-01 séparé avant recette réelle de création ou changement de code | Ne pas contourner par SQL, mock de production ou code figé prétendument éditable ; aucun correctif autorisé dans UI 6.1 |

SEN-05 est validée : le type et l’unité restent en lecture seule en édition MVP,
bien que l’API permette leur modification. Aucune exception ne sera déduite d’une
liste vide, du statut ou d’une première page de mesures. Leur modification reste
un chantier métier distinct, avec traitement de l’historique.

## 6. Parcours et écrans proposés

### 6.1 Liste des capteurs

PageHeader « Capteurs », action « Nouveau capteur », sélection Entreprise,
Site industriel, Équipement industriel, recherche « Nom, code, type ou unité »,
Statut (Tous, Actif, Inactif), taille de page. Tableau : Nom lié au détail,
Code métier, Type de capteur, Unité, Statut. Rattachement affiché au-dessus du
tableau, sans GET parent par ligne. Aucun indicateur IA ou mesure implicite.

1. Sans contexte : charger seulement le catalogue entreprises. Site indisponible
   jusqu'à l'entreprise, équipement indisponible jusqu'au site. Aucun GET Sensors
   avant validation de toute la chaîne ; aucun choix arbitraire même s'il n'y a
   qu'une option.
2. Entreprise choisie : charger ses sites via `/sites?company_id=...`. Site choisi :
   vérifier Site.company_id, charger `/equipments?site_id=...`. Équipement choisi :
   vérifier Equipment.site_id. Les catalogues n'imposent pas de filtre de statut
   Equipment ; aucun statut équipement n'interdit techniquement un capteur.
3. Charger `/sensors?equipment_id=...&page=...&page_size=...`, avec status/search
   seulement s'ils sont appliqués. Refuser d'afficher une réponse contenant un
   equipment_id différent du périmètre demandé, selon la convention Equipments.
4. Changement d'entreprise : vider site, équipement, recherche et résultats ;
   changement de site : vider équipement, recherche et résultats ; changement
   d'équipement : vider recherche et résultats. Conserver le statut valide et la
   taille, revenir page 1 à chaque changement. Annuler les lectures obsolètes et
   empêcher leurs réponses tardives de restaurer un ancien périmètre.
5. Recherche trimée appliquée par bouton/Entrée ; vide omise, maximum 100.
   Changement de recherche/statut/taille : page 1. Effacer la recherche conserve
   parents et statut. Les jokers gardent leur comportement backend constaté.

États distincts : sélection attendue, catalogues en chargement, parent sans
descendant, chargement Sensors, aucun capteur, aucun résultat filtré, page devenue
vide avec total positif, erreur. Pas de pagination si total=0 ; proposer un retour
manuel à une page disponible quand la page est hors plage, sans boucle de retry.

### 6.2 Détail

Routes proposées : `/sensors`, `/sensors/new`, `/sensors/:sensorId/edit`,
`/sensors/:sensorId`, avec `new` avant la route paramétrée. Id invalide : message
local sans HTTP ; id absent : 404 dédiée, sans fiche vide ni recréation.

Lecture Sensor puis Equipment réel, Site réel puis Company réelle. Contrôler
chaque id reçu. Afficher nom, code, type, unité, statut, description, équipement,
site, entreprise, created_at et updated_at. Aucun company_id/site_id n'est inventé
dans SensorRead. Référence indisponible : conserver la fiche et montrer l'erreur
de référence distincte ; pas de remplacement par le contexte URL.

Actions proposées : Retour à la liste, Modifier après chargement, lien vers
l'équipement réel lorsqu'il est résolu. Dates administratives sans conversion
locale arbitraire ni ajout fictif de UTC. Description absente : « Non renseignée ».
Pas d'onglet Measurements vide, bouton calculer, dernière mesure ou faux zéro.

### 6.3 Création, conditionnée au correctif B-SEN-01

Formulaire : entreprise, site, équipement obligatoires et vérifiés ; nom, code,
type, unité obligatoires ; statut présélectionné Actif ; description facultative.
Pas de catalogue inventé de types ou d'unités. Afficher l'aide « Code unique dans
l'ensemble de l'application ». Aucune génération automatique de code.

Préremplissage depuis un contexte explicite valide uniquement ; sans contexte,
attendre la sélection. Changer un parent invalide tous ses descendants. Les
catalogues se chargent par pages de 50, avec action supplémentaire explicite.
Un parent présent en URL mais absent des pages chargées exige une lecture ciblée.

Payload proposé : equipment_id, name, code, sensor_type, unit, status et description
si renseignée. Company_id/site_id servent uniquement à la sélection. Trim des
quatre textes obligatoires à la création, conservation de la casse et des unités
(exemples valides : °C, mm/s) ; pas de conversion métier. Limites selon SEN-09.
Description non touchée omise ; valeur saisie conservée, y compris `""`.

Après 201 valide : navigation vers l'id retourné, confirmation accessible et toast
unique. Si la navigation échoue, conserver la confirmation et un lien vers le
capteur créé ; ne pas refaire le POST. Aucun scénario de création n'est annoncé
opérationnel tant que B-SEN-01 n'est pas corrigé et validé séparément.

### 6.4 Modification

Charger Sensor et son rattachement réel. Selon SEN-02/SEN-05, entreprise, site,
équipement, type et unité sont en lecture seule. Nom, code, statut et description
sont éditables. Dates en lecture seule, suivi administratif avant les actions.
Si les références réelles sont indisponibles ou incohérentes, bloquer
l'enregistrement et conserver les saisies, comme Equipments.

PATCH différentiel, whitelist limitée à name/code/status/description ; aucun
equipment_id, sensor_type, unit, id, dates ou parent UI. Aucun appel sans différence.
Conserver exactement les champs inchangés, casse, espaces et Unicode historiques ;
pas de nettoyage au chargement ni d'envoi du code inchangé. Pour un nom/code
modifié, vérifier non blanc et longueur réelle, sans trim silencieux en édition,
selon la convention Equipment. Description omise conserve ; `""` reste vide ;
action explicite de retrait produit null. Restaurer la valeur initiale enlève
le champ du PATCH. Statut n'induit aucune autre mutation.

Un changement de code reste bloqué par B-SEN-01. Cette limite ne doit pas être
masquée par le fait que d'autres PATCH peuvent atteindre la persistance.

## 7. URL et navigation contextuelle

Snapshot proposé :
`/sensors?company_id=...&site_id=...&equipment_id=...&status=active&search=...&page=1&page_size=20`.
Seuls equipment_id/status/search/page/page_size partent vers l'API Sensors.
Company_id/site_id restent des données de contexte UI.

- Valider entiers positifs sûrs, enums exacts, page >=1, taille 1..100 et recherche
  trimée <=100. Les choix de taille affichés restent 20/50/100, mais une taille
  d'URL valide de 1 à 100 est conservée. Paramètres de périmètre invalides : notice
  et blocage, sans bascule silencieuse vers une liste globale.
- equipment_id seul : résoudre Equipment -> Site -> Company, puis afficher ce
  contexte explicite ; site_id seul : résoudre Site -> Company, attendre le choix
  d'équipement ; company_id seul : attendre site puis équipement.
- Une chaîne fournie partiellement mais contradictoire bloque la liste/création.
  Ne pas remplacer un parent fourni par un autre sans décision de l'utilisateur.
  Le contexte liste appliqué est conservé entre liste, détail et édition, y
  compris page, taille, statut et recherche ; le brouillon de recherche ne l'est pas.
- Dans une fiche atteinte par id, le rattachement affiché vient de Sensor, même si
  le contexte de retour est différent. Montrer une notice de différence et
  conserver le retour à la liste d'origine. Le contexte ne modifie aucun parent.
- Equipment -> « Voir les capteurs » construit la chaîne du parent réel, page 1,
  taille 20, sans recycler search/status Equipment dans les filtres Sensors.
  Sensor -> Equipment utilise le véritable Equipment et son site/entreprise ;
  les filtres Sensors ne deviennent pas des filtres Equipment. Un éventuel retour
  Equipment détaillé nécessite un contexte distinct et borné, pas un returnUrl libre.
- Création depuis une liste : annulation restitue le snapshot de liste initial.
  Après création avec un autre équipement choisi explicitement, proposer le détail
  créé et un retour à sa liste cohérente (page 1, sans recherche), plutôt qu'un
  périmètre mélangé. Annulation d'édition : retour fiche avec snapshot conservé.
- Aucun returnUrl externe, aucune navigation Measurements active avant livraison
  du module correspondant. Un futur lien utilisera le véritable sensor_id.

## 8. Erreurs et interactions proposées

| Situation | Comportement UI proposé |
| --- | --- |
| GET 404 sur Sensor | Fiche introuvable, retour liste, aucune création automatique |
| Parent absent ou incohérent | Erreur du parent concerné, aucune recherche Sensors élargie |
| 422 | Mapper seulement les locations body/query reconnues ; message global pour le reste ; préserver les saisies |
| 409 écriture | Message de conflit global, parent ou code possibles ; ne pas parser le texte anglais comme contrat stable |
| 401/403 éventuel | Accès refusé ; traitement défensif sans prétendre qu'une authentification existe |
| Réseau ou 5xx en lecture | Erreur lisible et relance manuelle possible |
| Réseau ou 5xx en écriture | Résultat incertain, saisies conservées ; vérifier la fiche avant nouvelle tentative, aucun retry automatique |
| Soumission en cours | Double envoi bloqué, état accessible, sortie protégée |
| Brouillon abandonné | Garde Router et beforeunload selon les modules existants |
| Succès et navigation échouée | Résultat confirmé conservé avec lien de récupération, aucune deuxième écriture |

Responsive à vérifier ultérieurement : 1440, 1024, 1023, 768, 390 et 320 px,
tableau défilable sans débordement global, actions utilisables au clavier,
statuts lisibles sans couleur seule et premier champ erroné accessible.

## 9. Besoins backend identifiés, sans implémentation

| Référence | Besoin et priorité | Effet sur la conception |
| --- | --- | --- |
| B-SEN-01 | Bloquant : ajouter get_by_code cohérent avec le repository et tester POST/PATCH code | Prérequis pour livrer et recetter les écritures proposées, chantier séparément autorisé |
| B-SEN-02 | Aligner contraintes Pydantic et SQL, refuser null pour les champs PATCH obligatoires tout en autorisant l'omission | Éviter les 500 prévisibles ; préciser trim, blancs et longueurs sans réécrire silencieusement les codes existants |
| B-SEN-03 | Traduire IntegrityError et stabiliser codes d'erreur métier, clarifier la transaction repository/service | Gérer courses d'unicité/FK et distinguer parent absent de code dupliqué ; pas de garantie actuelle |
| B-SEN-04 | Authentification, autorisation de ressource et isolation tenant | Chantier sécurité nécessaire avant exposition multi-tenant ; la cascade UI ne suffit pas |
| B-SEN-05 | Arbitrer historique et intégrité lors d'un transfert ou changement type/unité | Hors MVP selon SEN-02/SEN-05 validées ; audit PredictionRecord et unités historiques nécessaire avant élargissement |
| B-SEN-06 | Encadrer suppression, estimation d'impact et conservation historique | Hors MVP selon SEN-03 validée ; pas de simple bouton DELETE sans politique métier |
| B-SEN-07 | Harmoniser les variantes Measurements (bornes, fuseaux, pagination) | À traiter avec le futur module Measurements, sans les mélanger dans Sensors |

Filtres Sensors par entreprise/site, tri configurable, catalogue de types/unités,
compteurs et dernière mesure ne sont pas nécessaires au MVP proposé. Leur ajout
serait une évolution distincte, pas une fonctionnalité à simuler par agrégation
client de toutes les pages. Idempotence et contrôle optimiste restent des besoins
possibles si les exigences futures de concurrence le requièrent.

### 9.1 Préparation minimale de B-SEN-01, sans correction

Le défaut est localisé dans SensorRepository : `get_by_code` manque alors que
SensorService.create l’appelle après vérification de l’équipement et
SensorService.update l’appelle dès que `code` figure dans le PATCH, même identique.
La route ne capture que ValueError ; AttributeError échappe à ce traitement.

Correctif proposé : ajouter uniquement la méthode
`get_by_code(self, code: str) -> Sensor | None` au repository, sur le modèle de
EquipmentRepository.get_by_code : SELECT Sensor WHERE Sensor.code == code,
retour par `self.db.scalar(statement)`. L’import `select` existe déjà. Aucune
nouvelle dépendance, migration ou modification du modèle, du service ou des routes
n’est nécessaire pour résoudre cette absence de méthode.

La recherche doit rester globale, sans filtre equipment_id, site_id ou company_id,
par égalité exacte, sans trim, lower, ILIKE ni nouvelle règle de normalisation.
Le service possède déjà le contrôle « même id accepté, autre id refusé » en PATCH
et les routes traduisent ses ValueError en 409. Le correctif rétablit ce chemin
prévu, sans élargir les règles métier ou garantir les courses concurrentes.

### 9.2 Tests backend proposés pour B-SEN-01

Tests à écrire et exécuter uniquement après autorisation du correctif. Prévoir
une base SQLite en mémoire isolée, FK activées, sessions adaptées aux commit des
repositories, et surcharge de get_db dans TestClient. Forcer DATABASE_URL avant
tout import applicatif ; ne pas réutiliser automatiquement une configuration
PostgreSQL ou DASHBOARD_TEST_DATABASE_URL. Restaurer les overrides après chaque
test. Aucun accès ou écriture PostgreSQL, aucune suppression réelle.

Les scénarios de création doivent passer par le vrai service et le vrai repository,
sans mock de get_by_code ; des fixtures ORM peuvent préparer les parents ou un
capteur existant, mais ne remplacent pas le POST à vérifier. Préparer deux
équipements dans une même entreprise et un troisième dans une autre entreprise.
Utiliser des valeurs valides et des codes ASCII distincts, sans faire dépendre
l’unicité de particularités de collation SQLite/PostgreSQL.

| Scénario | Assertion attendue après correctif |
| --- | --- |
| Repository, code présent puis absent | Retour du Sensor attendu puis None ; recherche globale, sans mutation |
| POST sur équipement existant, code libre | 201, id retourné, equipment_id et champs conformes ; GET et lecture dans une nouvelle session concordants ; une seule ligne ajoutée |
| POST du même code, même équipement | 409 de conflit, aucune ligne supplémentaire, capteur initial inchangé |
| POST du même code, autre équipement de la même entreprise | 409, aucune ligne supplémentaire ; unicité non limitée à l’équipement |
| POST du même code, équipement d’une autre entreprise | 409, aucune ligne supplémentaire ; unicité globale confirmée |
| PATCH contenant explicitement le code courant | 200, même id/code/parent, aucune duplication ; ne pas exiger un changement de updated_at sans modification effective |
| PATCH vers un code différent et libre | 200, même id/parent, nouveau code persisté après relecture ; ancien code absent et nombre de capteurs stable |
| PATCH vers le code d’un autre capteur | 409, état initial conservé après relecture ; couvrir autre équipement, y compris autre entreprise |
| PATCH sans code, description seule | 200, code et rattachement inchangés ; non-régression du chemin qui ne consulte pas get_by_code |
| POST avec équipement absent | 409 prévu, aucune création ; non-régression du contrôle parent antérieur à get_by_code |

Sur les refus, vérifier le 409 et le détail de conflit attendu pour le scénario,
puis l’absence d’effet en persistance. Les tests backend du code identique sont
nécessaires même si le futur frontend omet le code inchangé. Aucun scénario de
transfert, DELETE ou déverrouillage type/unité n’est ajouté au périmètre MVP.

Dépendances non corrigées : **B-SEN-02** conserve les écarts de longueur, blancs et
null entre schémas et SQL. Utiliser des données valides dans cette recette ; un
succès B-SEN-01 ne prouve pas leur résolution. **B-SEN-03** conserve les
IntegrityError non traduites et les commit repository/service redondants. Les
conflits séquentiels ci-dessus valident le contrôle métier préalable, pas une
course d’unicité ni l’atomicité transactionnelle. Ces deux chantiers restent
séparés, sans élargir le correctif minimal. La validation PostgreSQL des contraintes
et de la concurrence nécessiterait une autorisation distincte ultérieure.

## 10. Risques et critères d'acceptation

Risques majeurs : écriture de code/création actuellement cassée, contraintes API/SQL
divergentes, suppression en cascade irréversible, déplacement de l'historique et
incohérences de prédictions lors d'un transfert, perte de sens des anciennes mesures
si unité modifiée, absence d'isolation multi-tenant, résultat d'écriture incertain
et catalogue partiel pris à tort pour un catalogue complet.

Critères de clôture UI 6.1 :

- Branche feature/frontend-sensors et état initial propre établis ; seules les
  lignes de ce document sont ajoutées à l'issue de l'étape.
- Contrats, contraintes API et SQL distingués ; six endpoints Sensors, pagination,
  filtres, recherche, erreurs et méthode manquante documentés avec sources.
- Conventions des trois modules existants examinées, quatre écrans conçus sans
  prétendre que les écritures sont aujourd'hui opérationnelles.
- Décisions SEN-01 à SEN-10 explicitement validées par l’utilisateur, besoins
  backend conservés et séparés, sans autorisation implicite de développement.
- Aucun code, package, backend, base ou Docker modifié ; aucun commit/push/merge ;
  UI 6.2 non commencée ; accord explicite utilisateur attendu avant développement.

Critères pour une future implémentation, sous réserve d'accord :

- Tests Angular de transport sur les paramètres exacts et whitelist, aucun DELETE
  ou transfert ; lecture Sensor typée, enums exacts, POST conditionné au correctif
  et PATCH différentiel sans code inchangé ni type/unité selon SEN-05.
- Tests de cascade entreprise/site/équipement, URL incomplète ou contradictoire,
  catalogues multipages, changement rapide de parent, réponse tardive, références
  incohérentes et absence de GET Sensors sans équipement validé.
- États liste/détail et erreurs séparés, pagination serveur et page hors plage,
  recherche explicite, retours de navigation et refresh vérifiés.
- Tests formulaires, Unicode/longueurs, null/vide/omission de description,
  différences restaurées, double clic, garde de sortie, erreurs 404/409/422 et
  écritures incertaines sans retry automatique ; succès/navigation échouée couverts.
- Recette backend séparée après correctif B-SEN-01 : création valide, code dupliqué,
  PATCH code inchangé/différent, parent absent, contraintes SQL et lecture après
  persistance. Aucun test destructif ou écriture réelle autorisé par UI 6.1.
- Contrôle responsive et accessibilité, non-régression Companies/Sites/Equipments/
  Dashboard, sans modification de leurs contrats ni déclenchement de calcul IA.

**Point d’arrêt : SEN-01 à SEN-10 sont validées. Le diagnostic et les tests
B-SEN-01 ci-dessus sont préparés uniquement ; accord explicite attendu avant
le correctif backend. UI 6.2 n’est pas commencée.**
