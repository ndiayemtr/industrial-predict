# UI 7.5 - Validation intégrée Measurements

22 octobre 2026, UTC. Branche feature/frontend-measurements, HEAD attendu et
constaté 7b1265a. Dépôt propre au démarrage.

**Lecture réelle Angular -> FastAPI -> PostgreSQL confirmée, sans écriture métier.
L'écart de navigation MES-10 constaté lors de UI 7.5 est résolu par UI 7.5.1.**
Les sections 1 à 9 conservent les preuves de la recette initiale, sans correction
applicative à ce stade. Les sections 10 et 11 décrivent le correctif de navigation et la finition des
actions Angular, leurs tests et les recettes complémentaires du 22 octobre 2026. Aucun commit,
push ou merge. UI 7.6 non commencée.

## 1. Préconditions et identité DEV

Procédure relue : [infra/development/README.md](../infra/development/README.md).
Commandes documentées exécutées :

```powershell
backend/.venv/Scripts/python.exe -B infra/development/manage.py check-db --config D:/integration/industrial-predict/development/config.json
backend/.venv/Scripts/python.exe -B infra/development/manage.py check --config D:/integration/industrial-predict/development/config.json
```

Les deux contrôles passent. GET /__dev/identity directs sur 8001 et via Angular
4201 répondent 200, sans redirection, avec X-Industrial-Predict-Environment:
local-development. Leur identité est concordante avec SQL avant et après recette.
GET http://127.0.0.1:8001/health répond 200, status healthy.

| Propriété | Identité vérifiée |
| --- | --- |
| Angular | http://127.0.0.1:4201 |
| FastAPI | http://127.0.0.1:8001 |
| PostgreSQL | 127.0.0.1:5434, version 17.10 |
| Base et OID | industrial_predict_dev, 16384 |
| Mode | local-development |
| Rôle applicatif et lectures SQL directes | ui47_app |
| Instance | fb3284bd-fb7b-4c22-b620-96a1564b1d0c |
| Cluster | industrial-predict-development |
| Révision Alembic | 09ac8101e9fe |

ui47_app est non superutilisateur, sans CREATEDB, CREATEROLE, REPLICATION ou
BYPASSRLS. check-db confirme les droits attendus sur les huit tables et séquences,
sans droits DDL, modification Alembic, propriété de tables ou appartenance à un
rôle supplémentaire. Aucun rôle migrator ou admin utilisé pour cette recette.
Aucune migration appliquée.

[API_PREFIX](../frontend/src/app/core/http/api-config.ts) reste relatif /api/v1.
Le [proxy DEV](../infra/development/angular-proxy.cjs) a pour unique cible 8001 et
contrôle l'identité avant transfert ; il bloque par 503 si l'identité échoue.
Les ressources API observées dans le navigateur sont sur 4201 et les GET de
corroboration portent le marqueur DEV. L'API contrôle aussi sa cible SQL.
Aucun fallback vers 8000, 4200, 5433 ou une base historique utilisé.
Aucun service, processus, conteneur ou volume redémarré, réinitialisé ou reconfiguré.
Les services DEV existants restent en fonctionnement après recette.

## 2. Méthode de preuve et séparation des contrôles

Trois preuves complémentaires sont conservées, sans instrumentation du frontend
ou du backend :

1. Parcours réel dans Angular 4201 : sélections, listes, fiches, URL, captures et
   données DOM affichées. Aucun serveur synthétique ou fixture HTTP substituée.
2. Inventaire des ressources du navigateur, sources xmlhttprequest, relevé à
   chaque étape. Il donne les URL effectivement observées. Cet inventaire peut
   dédupliquer une URL répétée ; ce n'est pas un HAR ni un journal exhaustif des
   statuts, corps ou nombres de requêtes.
3. GET de corroboration indépendants via le même proxy 4201, uniquement vers les
   URL Measurements réellement observées : 16 URL distinctes, toutes HTTP 200,
   marqueur DEV présent. Corps JSON comparés aux SELECT paramétrés en lecture seule.
   Les statuts/corps de ces GET ne sont pas présentés comme une interception des
   réponses internes du navigateur.

15 états DOM enregistrés sont comparés aux données SQL : ids, ordre, valeurs,
qualités, timestamps, unité et noms de la chaîne industrielle. Les cinq champs
des réponses détail sont également vérifiés contre SQL. Aucun appel aux endpoints
spécialisés /measurements/sensor/{id} ou /period, aucun GET Measurements global.
Aucun company_id, site_id, equipment_id ou unité envoyé comme filtre Measurements.

Les lectures SQL directes construisent exclusivement la connexion explicite DEV
avec ui47_app, sans importer app.core.database ou une configuration backend par
défaut. default_transaction_read_only=on dès la connexion, transaction REPEATABLE
READ, SET TRANSACTION READ ONLY, vérification SHOW transaction_read_only=on et
inspect_connection avant les SELECT métier, puis rollback. Fuseau de session UTC.
Aucun INSERT, UPDATE, DELETE, TRUNCATE, DDL, séquence consommée ou seed appliqué.
Aucun mot de passe ni URL complète de connexion conservé dans les preuves.

## 3. Sélection explicite et première liste

Chaîne choisie manuellement : INDUSTRIE DEMO A (Company 1) -> Site de production
(Site 1) -> Pompe de circulation P101 (Equipment 1) -> Température pompe (Sensor 1).
Aucune sélection automatique d'un descendant.

| État réellement observé | Aides restantes | Ressource Measurements observée |
| --- | ---: | --- |
| Initial | 4 | Aucune |
| Entreprise vérifiée, Site non sélectionné | 3 | Aucune |
| Site vérifié, Equipment non sélectionné | 2 | Aucune |
| Equipment vérifié, Sensor non sélectionné | 1 | Aucune |
| Sensor vérifié et historique chargé | 0 | GET paginé sensor_id=1, page=1, page_size=20 |

Les ressources des quatre premiers relevés ne contiennent aucun endpoint
Measurements, tandis que les GET des références et catalogues attendus sont
présents. La table n'apparaît qu'après le choix et la résolution du capteur.
Les rattachements affichés correspondent aux FK lues en SQL.

GET /api/v1/measurements?sensor_id=1&page=1&page_size=20 répond avec total=3,
pages=1 et l'ordre suivant, identique au SELECT timestamp DESC, id DESC :

| id | Timestamp API reçu | Valeur API / affichée | Qualité |
| --- | --- | --- | --- |
| 3 | 2026-10-16T08:00:00.123456Z | 65.4 / 65,4 | good / Bonne |
| 2 | 2026-10-15T08:00:00Z | 65.1 / 65,1 | good / Bonne |
| 1 | 2026-10-14T08:00:00Z | 64.2 / 64,2 | good / Bonne |

Unité affichée : °C, issue de Sensor 1. Le tri décroissant est vérifié sur ces
lignes ; le départage de timestamps égaux pour un même Sensor n'est pas exercé
par ce jeu, qui n'en contient pas. La réserve de pages mouvantes en concurrence
n'est pas levée par cette recette séquentielle.

## 4. Qualités et états vides réels

Distribution SQL des 18 mesures : good 15, suspect 1, bad 1, estimated 1,
missing 0. Les filtres ont été testés sur les capteurs où les données existent :

| Filtre | Sensor / rattachement Company, Site, Equipment | Résultat de liste et GET 200 corroboré |
| --- | --- | --- |
| good | 1 / 1, 1, 1 | ids 3, 2, 1, total 3 |
| suspect | 3 / 1, 1, 2 | id 8, valeur 86.5, total 1 |
| bad | 4 / 1, 2, 3 | id 12, valeur 4.1, total 1, unité mm/s |
| estimated | 5 / 2, 3, 4 | id 14, valeur 71.6, total 1 |
| missing | 1 / 1, 1, 1 | total 0, état Aucun résultat |

Les trois autres périmètres ont aussi été choisis explicitement dans les quatre
sélecteurs. Sensor 4, inactif, reste consultable. Aucune ligne missing fabriquée
pour compléter la recette. Les assertions simulées historiques restent la preuve
pour l'affichage d'une ligne de qualité missing.

Sensor 7, UI67-SEN-20261020-01, inactif et sans mesure en SQL : total=0 et état
Aucune mesure sans filtre. Distinction confirmée avec Aucun résultat sur un
historique existant filtré. Aucun zéro artificiel, message d'erreur ou suppression
de données utilisé pour construire ces états.

## 5. UTC, six décimales et bornes [début, fin)

Depuis les contrôles Angular date, heure UTC et fraction, qualité good sur Sensor 1 :

| Intervalle UTC explicitement appliqué | GET paginé / résultat SQL et UI |
| --- | --- |
| [2026-10-16T08:00:00.123456Z, 2026-10-16T08:00:00.123457Z) | id 3, total 1 : début inclus |
| [2026-10-16T08:00:00.123455Z, 2026-10-16T08:00:00.123456Z) | total 0 : fin exclue |

La mesure réelle stockée à la fraction non nulle 123456 permet de vérifier une
fenêtre d'une microseconde. Les URL Angular et XHR gardent les six chiffres ;
le JSON, time.datetime, la chaîne ISO source et le SELECT PostgreSQL concordent.
Aucun arrondi à la milliseconde, conversion locale implicite ou timestamp fabriqué.
Les corps API sont comparés comme instants aware à la précision microseconde,
et les valeurs numériques sans arrondi de présentation.

Une période plus large a ensuite été appliquée :
[2026-10-14T08:00:00.000000Z, 2026-10-16T08:00:00.123457Z).
Les zéros explicites du début sont conservés dans l'URL et les requêtes, même si
une réponse timestamp à microseconde nulle omet sa fraction dans le JSON.
Les données réelles de cette recette reviennent en Z ; le maintien d'un offset
non nul restauré en URL demeure couvert par les tests simulés UI 7.3.1/7.4,
sans prétendre avoir recréé le fuseau d'acquisition.

## 6. Pagination, détail et retour contextuel

Chaque Sensor du seed n'a que trois mesures, donc la taille usuelle 20 donne une
seule page. Une taille d'URL valide page_size=1 a été utilisée explicitement,
conformément au contrat 1..100 et au comportement de restauration existant.
Aucun changement de valeur par défaut ou ajout de données pour tester la pagination.

Avec qualité good et la période large ci-dessus : total=3 et pages=3.
Page 1 -> id 3 ; Suivant -> page 2, id 2 ; Précédent -> page 1, id 3.
Ces URL observées ont été relues via le proxy et les limites/offsets comparés à SQL.

Deux détails réels ouverts par leur lien de liste :

- GET /api/v1/measurements/3 : id 3, sensor_id 1, timestamp
  2026-10-16T08:00:00.123456Z, value 65.4, quality good.
- GET /api/v1/measurements/2 : id 2, sensor_id 1, timestamp
  2026-10-15T08:00:00Z, value 65.1, quality good.

Les cinq champs sont affichés en français, avec UTC complet et ISO reçu,
qualité déclarée et valeur numérique sans substitution. Chaîne réelle affichée :
Measurement -> Sensor 1 -> Equipment 1 -> Site 1 -> Company 1. L'unité actuelle
°C est accompagnée de sa réserve explicite d'absence de garantie historique.

Retour après la fenêtre d'une microseconde : URL de liste identique.
Retour après le détail id 2 : page=2, page_size=1, quality=good, les deux bornes
exactes, les quatre parents et le fragment measurement-results-title sont
conservés intégralement. Égalité des URL avant/après confirmée et id 2 réaffiché.

### Écart de navigation MES-10 constaté initialement, résolu en section 10

Le lien Measurement -> Sensor réel fonctionne et conduit à /sensors/1 avec les
parents réels, page=1/page_size=20, sans période ou qualité Measurements recyclée.
La fiche Sensor a bien été consultée. Ses actions réelles sont Retour à la liste
des capteurs, Modifier et le lien Equipment. **Aucune action contextuelle vers
Measurements n'est disponible.** Le menu global Mesures est présent, mais il
n'ouvre pas automatiquement l'historique du capteur courant.

L'absence est constatée dans le DOM et concorde avec le périmètre documenté de
[UI 7.4](ui-7.4-measurement-detail.md). Aucune navigation inverse n'est présentée
comme réussie. Une correction applicative distincte doit être validée si cette
action est requise avant clôture de MES-10. Elle n'est pas implémentée ici.

## 7. Conservation PostgreSQL et seed

Horodatages des instantanés :

- Avant : 2026-10-22T11:16:41.912449+00:00.
- Après tous les parcours et GET de corroboration : 2026-10-22T11:25:17.809340+00:00.

Les compteurs, empreintes globales SHA-256 et empreintes individuelles par id
sont strictement identiques. Les empreintes globales correspondent également au
relevé historique des 40 lignes de UI 6.7.2, sur la seule base DEV.

| Table | Avant | Après | SHA-256 avant = après |
| --- | ---: | ---: | --- |
| companies | 2 | 2 | `c10d5910b6589fb700a18828102a7adc2a82b45edcea8f8bd1701dde0fa6aa1b` |
| sites | 4 | 4 | `5a03a9dc79cab6ab7c5d4367e221e7b0ebaca8e10d9058a4782bbf4dd561ffaa` |
| equipments | 6 | 6 | `f9c71ac9126993e691a499533f32b1c62928ea4e21ec3095fab99b7336e44319` |
| sensors | 7 | 7 | `216175820fec02b7f7d6e0e5e51c7e099daa6b72f2f027228df3bd0043c693c4` |
| measurements | 18 | 18 | `a234b257310baa1f39e6cec647c989ba7e3e7e8627ed42476df657e86fb1d34f` |
| maintenance_records | 3 | 3 | `2843dd063d7c4590ce6f96474399465abefcf14dad9f49906df4b94c3374bb2a` |
| prediction_records | 0 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| maintenance_recommendations | 0 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

Total : **40 -> 40**, dont 18 Measurements. Toutes les colonnes et dates des
40 lignes préexistantes sont préservées, notamment Sensors 1 et 7 et les essais
DEV antérieurs. Aucune connexion à la base historique. Les cinq chaînes de FK
contrôlées par les SELECT de diagnostic ne comportent aucun orphelin ; les tables
PredictionRecord et MaintenanceRecommendation restent vides.

Capteur 1, UI47-SEN-PUMP-TEMP :

| Champ | Valeur actuelle avant/après | Attente exacte du seed |
| --- | --- | --- |
| description | Capteur fictif | Capteur fictif. |
| updated_at | 2026-10-20 22:11:55.315993 | 2026-10-16T12:00:00 |

updated_at est administratif, sans fuseau dans cette colonne ; aucun UTC n'est
inventé. L'écart préexistant est celui documenté dans
[UI 6.7](ui-6.7-sensors-integration.md), conservé sans restauration.
Le seed et son contrôle sont inchangés. Le check strict complet n'a pas été
relancé ; sa divergence est reconfirmée par lecture et comparaison à la fixture.
Aucun succès du seed strict n'est revendiqué. Les anciennes données de test
restent intactes, sans nettoyage ni suppression.

## 8. Références historiques, réserves et limites de la recette initiale

**1 456 tests Angular réussis et build production réussi de UI 7.4 restent des
références historiques, non relancées.** Bundle initial historique : 605,34 kB,
avertissement à 500 kB, budgets inchangés. Aucun nouveau résultat de build ou
suite de tests présenté comme exécuté pendant cette étape documentaire.

Les erreurs réseau/404/422, contrats numériques invalides, parents incohérents,
réponses obsolètes et autres cas défensifs restent des preuves HTTP simulées
historiques. Aucun défaut réel provoqué dans DEV pour les reproduire. Les GET,
DOM et comparaisons PostgreSQL décrits ci-dessus sont les contrôles réellement
exécutés dans cette recette, sur les données existantes.

Réserves conservées :

- Écart de navigation MES-10 constaté initialement : résolu et vérifié en UI 7.5.1, section 10.
- B-MES-01 : divergences de fuseau, ordre des bornes, inclusivité et erreurs des
  endpoints temporels spécialisés. Ces endpoints restent inutilisés.
- B-MES-02/03/04 : non-finis/coercitions numériques, écarts Pydantic/SQL,
  null/omission, intégrité et concurrence non corrigés. Les 18 valeurs finies
  consultées ne prouvent pas la sûreté générale des écritures.
- B-MES-05 : absence d'authentification et d'isolation multi-tenant ; une chaîne
  de parents correcte n'est pas une autorisation de ressource.
- B-MES-06/07 : coût COUNT/offset, concurrence, absence de snapshot d'unité.
- Seed strict non conforme ; historique de divergence et capteur 1 préservés.
- Budget Angular initial dépassé. Aucun budget relevé, package ou code modifié.
- Inventaire XHR dédupliqué, complété par des GET de corroboration et SQL,
  sans prétendre disposer d'une interception exhaustive HAR.
- Pas de charge réelle, de concurrence, de timestamp égal dans un même capteur,
  de valeur non finie ou de ligne missing dans le jeu existant.

B-SEN-02/03 demeurent aussi ouverts, sans correction par cette consultation.
Aucun formulaire d'écriture, dialogue d'abandon ou fonction IA ne fait partie
de la recette Measurements en lecture seule.

## 9. Pièces de preuve et état Git à la fin de la recette initiale

Pièces locales ignorées par Git, sans mot de passe ni dump SQL :

- [Avant](../frontend/tmp/ui-7.5/before.json), [après](../frontend/tmp/ui-7.5/after.json)
  et [comparaison des empreintes](../frontend/tmp/ui-7.5/integrity-comparison.json).
- [Étapes de sélection et ressources XHR](../frontend/tmp/ui-7.5/selection-stages.json),
  [quinze états navigateur et leurs ressources](../frontend/tmp/ui-7.5/browser-reads.json).
- [GET réels et comparaisons SQL/DOM](../frontend/tmp/ui-7.5/http-sql-comparison.json),
  [retours contextuels](../frontend/tmp/ui-7.5/navigation-checks.json),
  [actions réelles de la fiche Sensor](../frontend/tmp/ui-7.5/sensor-navigation.json).
- [Instantanés en lecture seule](../frontend/tmp/ui-7.5/snapshot.py),
  [diagnostic GET/SQL](../frontend/tmp/ui-7.5/verify_reads.py).

Captures réelles DEV :

- [Liste initiale](../frontend/tmp/ui-7.5/screenshots/01-real-list.png).
- [Période à la microseconde](../frontend/tmp/ui-7.5/screenshots/02-microsecond-inclusive.png).
- [Détail réel id 3](../frontend/tmp/ui-7.5/screenshots/03-real-detail-microseconds.png).
- [Retour page 2](../frontend/tmp/ui-7.5/screenshots/04-return-page-two.png).
- [Fiche Sensor sans action Measurements](../frontend/tmp/ui-7.5/screenshots/05-sensor-missing-measurements-link.png).
- [Qualité Estimée réelle](../frontend/tmp/ui-7.5/screenshots/06-quality-estimated.png).

L'onglet de recette a été fermé. Aucun processus DEV arrêté ou redémarré.
Git : HEAD 7b1265a inchangé sur feature/frontend-measurements, index vide.
Seul docs/ui-7.5-measurements-integration.md ajouté ; rapports antérieurs préservés.
Aucun fichier exécutable frontend/backend, SQL, migration, Docker, package ou
configuration privée modifié. Captures, diagnostics et preuves ignorés.
git diff --check et contrôle des liens/espaces réussis. Aucun secret détecté dans
le périmètre documentaire. Aucun commit, push ou merge. UI 7.6 non commencée.

À ce stade initial, la réserve de navigation nécessitait le correctif documenté ci-dessous.

## 10. UI 7.5.1 - Navigation Sensor vers Measurements

### Périmètre et rattachement vérifié

Branche et HEAD revérifiés : feature/frontend-measurements, 7b1265a.
Au début de cette intervention, seul le rapport UI 7.5 était non suivi ; aucun
fichier exécutable modifié. Les preuves initiales ci-dessus sont conservées.

Sept fichiers concernés au total :

- frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.ts :
  calcul réactif du contexte uniquement après succès des quatre lectures,
  identifiants entiers positifs sûrs et égalité des trois clés de rattachement.
- frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.html :
  lien « Voir les mesures » entre Retour à la liste et Modifier.
- frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.scss :
  mixin navigation-action secondaire existante.
- frontend/src/styles/_buttons.scss : inclusion du lien dans les interactions
  harmonisées, focus visible et respect de prefers-reduced-motion.
- frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.spec.ts :
  adaptation de l'assertion de lecture seule et présence de la nouvelle action.
- frontend/src/app/features/sensors/pages/sensor-detail/sensor-measurements-navigation.spec.ts :
  26 tests supplémentaires de navigation et de références avec HTTP simulé.
- docs/ui-7.5-measurements-integration.md : rapport initial complété ici.

Le lien disparaît pendant tout chargement ou après erreur/incohérence d'un
parent. Aucun rattachement n'est déduit du contexte de retour. Après reprise
manuelle réussie, il réapparaît. Un changement de capteur annule les anciennes
requêtes et retire immédiatement l'ancien contexte. Retour et Modifier gardent
leur URL et leurs conditions de disponibilité antérieures.

La cible comporte exactement company_id, site_id, equipment_id, sensor_id,
page=1 et page_size=20. Aucun search/status de Sensors, aucun quality/start_time/
end_time, aucune fusion des query parameters. Aucun contrat API changé.
Measurements revalide sa propre chaîne avant de lire les mesures ; seul sensor_id
avec la pagination est envoyé au GET paginé.

### Tests et build réellement exécutés

```powershell
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.5.1/vitest.config.mjs --include=src/app/features/sensors/**/*.spec.ts --include=src/app/features/measurements/**/*.spec.ts --include=src/app/app.routes.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.5.1/vitest.config.mjs
npm.cmd run build -- --configuration production --stats-json
```

- Tests ciblés : 614 réussis, 17 fichiers.
- Suite complète : 1 482 réussis, 66 fichiers, dont les 26 nouveaux tests.
- Build production réussi. Runner temporaire ignoré, maxWorkers=2, aucun package ajouté.
- Bundle initial : 605 466 octets, soit 605,47 kB, contre 605 340 octets
  (605,34 kB) de référence UI 7.4 : +126 octets. Chunk Sensor Detail : 16,42 kB.
- Avertissement existant au seuil initial de 500 kB : dépassement de 105,47 kB.
  Aucun budget augmenté, aucun autre avertissement de build.

Les tests supplémentaires vérifient la résolution progressive, les trois parents
incohérents, les clés étrangères invalides, HTTP 0/403/404/500, les reprises
manuelles, un capteur absent ou d'identité incorrecte, les réponses obsolètes,
les changements de contexte URL, les actions existantes et la navigation réelle
Angular entre les deux pages sous HttpTestingController. Ils imposent les six
paramètres exacts et refusent une réponse contenant un autre sensor_id, sans
repli vers un périmètre plus large. Ces erreurs restent simulées, sans défaut
provoqué ni donnée modifiée dans DEV.

### Navigation DEV réellement exécutée en lecture seule

Identités HTTP avant/après sur Angular 4201 et API 8001 : 200 et local-development.
API /health : 200, healthy. SQL : industrial_predict_dev, ui47_app non privilégié,
PostgreSQL 17.10 sur 5434, instance fb3284bd-fb7b-4c22-b620-96a1564b1d0c,
révision 09ac8101e9fe. Procédure officielle relue, aucun redémarrage ni fallback.
Les connexions de diagnostic SQL imposent default_transaction_read_only=on,
SET TRANSACTION READ ONLY et vérifient transaction_read_only=on.

Départ volontairement contradictoire avec le rattachement réel :

```text
/sensors/1?company_id=2&site_id=3&equipment_id=4&search=TEMP&status=inactive&page=3&page_size=50
```

La fiche affiche le capteur 1 et les parents réels Equipment 1 -> Site 1 -> Company 1.
Les liens Retour et Modifier conservent le contexte fourni. Le nouveau lien donne :

```text
/measurements?company_id=1&site_id=1&equipment_id=1&sensor_id=1&page=1&page_size=20
```

Avant activation, quatre URL XHR observées : sensors/1, equipments/1, sites/1,
companies/1 ; aucune URL Measurements. Activation au clavier par Entrée après
Shift+Tab depuis Modifier : focus sur sensor-measurements avec contour visible
(mesure navigateur 1,77778 px, règle CSS 2 px à ce zoom).

Après activation, les quatre sélecteurs Measurements correspondent réellement à
INDUSTRIE DEMO A, Site de production, Pompe de circulation P101 et Température
pompe. Qualité « Toutes », période vide et taille 20. L'inventaire comprend neuf
URL XHR distinctes au total, dont le GET paginé attendu :

```text
http://127.0.0.1:4201/api/v1/measurements?sensor_id=1&page=1&page_size=20
```

Aucun parent, filtre Sensors ou filtre temporel ajouté à cette requête. Trois
lignes rendues : ids 3, 2, 1, valeurs 65,4 / 65,1 / 64,2, qualité Bonne,
unité actuelle °C. Le premier timestamp ISO demeure
2026-10-16T08:00:00.123456Z, affiché avec les six décimales.

Un GET indépendant de corroboration, sur cette URL effectivement observée via
4201, répond HTTP 200 avec le marqueur local-development. Les cinq champs de
chaque ligne, le total 3, page 1, taille 20, pages 1 et l'ordre concordent avec
les SELECT SQL. Les valeurs et timestamps rendus dans le DOM concordent aussi.
L'inventaire XHR est dédupliqué : il ne fournit ni corps ni statuts interceptés,
ni nombre exhaustif d'appels. Le statut 200 provient du GET de corroboration.
Aucune erreur ou alerte console observée. Onglet fermé, viewport restauré.

### Intégrité PostgreSQL et seed

Compteurs avant/après identiques : companies 2, sites 4, equipments 6, sensors 7,
measurements 18, maintenance_records 3, prediction_records 0,
maintenance_recommendations 0. Total : 40 lignes métier.

Les huit SHA-256, calculés sur toutes les colonnes de chaque ligne ordonnée par
id, ainsi que les empreintes individuelles des 40 lignes, sont identiques avant/
après et aux empreintes UI 7.5 de la section 7. Aucune modification métier
constatée. Aucun orphelin sur les cinq relations contrôlées. Les 39 anciennes
lignes et le capteur fictif UI 6.7 sont préservés.

Capteur 1 inchangé : description « Capteur fictif », updated_at administratif
2026-10-20 22:11:55.315993. L'attente du seed reste « Capteur fictif. » et
2026-10-16T12:00:00. Le check strict reste non conforme, ni masqué ni déclaré
réussi. Aucun seed exécuté ou modifié. Aucune écriture SQL ou HTTP métier.

### Responsive, accessibilité et captures

Contrôles réels : 1440, 1024, 1023, 768 et 320 px CSS. Cible 390 contrôlée à
389 et 391 px : réserve maintenue car le zoom du navigateur arrondit le viewport
physique entier ; aucune capture exactement à 390 px revendiquée.
Pour chaque largeur, scrollWidth égale clientWidth : aucun débordement global.
Les trois actions restent lisibles, leurs cibles mesurent 44 px de haut et
s'adaptent par retour à la ligne. Le lien est un vrai anchor accessible au clavier.
Captures examinées visuellement, conservées uniquement dans le dossier ignoré :

- [1440 px](../frontend/tmp/ui-7.5.1/screenshots/sensor-measurements-1440.png).
- [1024 px](../frontend/tmp/ui-7.5.1/screenshots/sensor-measurements-1024.png).
- [1023 px](../frontend/tmp/ui-7.5.1/screenshots/sensor-measurements-1023.png).
- [768 px](../frontend/tmp/ui-7.5.1/screenshots/sensor-measurements-768.png).
- [389 px](../frontend/tmp/ui-7.5.1/screenshots/sensor-measurements-389.png) et
  [391 px](../frontend/tmp/ui-7.5.1/screenshots/sensor-measurements-391.png).
- [320 px](../frontend/tmp/ui-7.5.1/screenshots/sensor-measurements-320.png).
- [Liste réelle après activation à 320 px](../frontend/tmp/ui-7.5.1/screenshots/measurements-after-navigation-320.png).

Autres preuves locales ignorées : [navigation et XHR](../frontend/tmp/ui-7.5.1/navigation.json),
[responsive](../frontend/tmp/ui-7.5.1/responsive.json),
[GET/SQL/DOM](../frontend/tmp/ui-7.5.1/http-sql-comparison.json),
[avant](../frontend/tmp/ui-7.5.1/before.json), [après](../frontend/tmp/ui-7.5.1/after.json),
[comparaison d'intégrité](../frontend/tmp/ui-7.5.1/integrity-comparison.json),
[tests complets](../frontend/tmp/ui-7.5.1/full-tests.log),
[build](../frontend/tmp/ui-7.5.1/build.log).

### Réserves restantes et état Git à la fin de UI 7.5.1

La réserve fonctionnelle MES-10 est résolue. Les réserves backend B-MES-01 à
B-MES-07 et B-SEN-02/03 de la section 8 demeurent ouvertes, ainsi que l'absence
d'authentification et d'isolation multi-tenant, l'unité non historique, le seed
strict non conforme, le budget Angular dépassé et la couverture PostgreSQL non
exhaustive. Le dialogue natif d'abandon reste non vérifié manuellement, hors de
ce parcours de consultation. La réserve de viewport 390 px est explicitée ci-dessus.

Git : feature/frontend-measurements, HEAD 7b1265a inchangé, index vide.
Cinq fichiers suivis modifiés, nouveau test et rapport non suivis : sept fichiers
à examiner avant commit. Aucun changement backend, SQL, migration, Docker,
package ou autre document. Aucun secret ni capture/fixture temporaire dans le
périmètre Git. git diff --check réussi ; liens locaux vérifiés.
Aucun commit, push ou merge. UI 7.6 non commencée. Validation attendue avant commit.

## 11. UI 7.5.2 - Harmonisation des actions de détail

### Modifications et réutilisation des styles

Branche feature/frontend-measurements, HEAD 7b1265a vérifiés. Au départ, les
sept fichiers UI 7.5/7.5.1 étaient présents, index vide. Aucune modification
backend, SQL, Docker, configuration ou package.

Cinq fichiers concernés par cette finition :

- frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.scss :
  suppression du bloc local sensor-back au profit de actions.navigation-action(),
  déjà utilisée par Voir les capteurs et Modifier sur Détail équipement.
- frontend/src/styles/_buttons.scss : ajout de sensor-back et measurement-back
  aux sélecteurs existants, y compris prefers-reduced-motion. Aucun nouveau
  système de styles, aucune modification de la mixin ou de la fiche Équipement.
- frontend/src/app/features/sensors/pages/sensor-detail/sensor-measurements-navigation.spec.ts :
  ordre exact des trois actions et une seule NavigationEnd par activation.
- frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts :
  unique action de retour sur la fiche Mesure, focus, une seule navigation et
  contexte complet conservé lors du retour réel sous RouterTestingHarness.
- docs/ui-7.5-measurements-integration.md : cette section.

Le retour Mesure utilisait déjà la bonne mixin : son SCSS n'a pas été modifié.
Ses transitions et son état actif étaient absents du sélecteur global ; ils
sont désormais fournis par les mêmes règles que Détail équipement.

Ordre Capteur inchangé : Retour à la liste des capteurs, Voir les mesures,
Modifier. Deux secondaires, puis primaire bleu. Le calcul measurementsQuery et
ses conditions ne sont pas modifiés. Les destinations et paramètres demeurent
ceux validés en section 10. Détail mesure conserve un seul retour secondaire,
sans action d'écriture. PageHeader conserve son flex-wrap, son espacement et
son alignement responsive existants.

### Comparaison des trois fiches et interactions

Styles calculés relevés dans le navigateur sur les données DEV réelles :

| Propriété | Référence Equipment, action partagée | Actions Sensor | Retour Measurement |
| --- | --- | --- | --- |
| Hauteur | 44 px | 44 px | 44 px |
| Espacement intérieur | 8 px / 16 px | 8 px / 16 px | 8 px / 16 px |
| Typographie partagée | Segoe UI, 15 px, graisse 600 | Identique | Identique |
| Interligne de la mixin | 22,5 px | 22,5 px | 22,5 px |
| Arrondi | 8 px | 8 px | 8 px |
| Secondaire | fond blanc, texte #17253b, bordure #56657b | Identique | Identique |
| Primaire | #2563eb, texte blanc | Modifier identique | Sans objet |
| Transitions | 120 ms, fond/bordure/couleur/ombre | Identiques | Identiques |

La référence partagée secondaire est Voir les capteurs sur Détail équipement.
Le retour Équipement conserve son bloc historique et son interligne calculé
20 px, avec une hauteur identique de 44 px ; cette fiche de référence n'a pas
été retouchée. La bordure nominale 1 px et le focus nominal 2 px sont calculés
0,888889 px et 1,77778 px à ce zoom, de manière identique sur les trois fiches.

Focus clavier réellement observé sur Voir les capteurs, Voir les mesures et
Retour à la liste des mesures : contour bleu visible avec décalage nominal 3 px.
Navigation Sensor -> Measurements par clic, puis ouverture de la mesure 3 et
retour par Entrée réellement exécutés en DEV, en consultation uniquement.
Le retour conserve company/site/equipment/sensor=1, page=1 et page_size=20.
Les tests vérifient en complément les filtres, périodes précises, paramètres
répétés et fragment du retour, ainsi que l'absence de double navigation.

Hover, actif, focus, disabled et reduced-motion ont été contrôlés dans les règles
CSS partagées et compilées : les nouveaux sélecteurs sont présents, avec les
mêmes couleurs et transitions que la référence. Le pilotage navigateur ne
fournit pas de survol maintenu ni de bouton souris maintenu : aucune capture de
pseudo-état hover/active maintenu n'est revendiquée. Ces liens ne possèdent pas
d'état désactivé métier ; aucune fausse action désactivée n'a été ajoutée.

### Tests, build et bundle

Commandes réellement exécutées depuis frontend :

```powershell
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.5.2/vitest.config.mjs --include=src/app/features/sensors/pages/sensor-detail/*.spec.ts --include=src/app/features/measurements/pages/measurement-detail/*.spec.ts --include=src/app/features/measurements/pages/measurements-list/*.spec.ts --include=src/app/features/equipments/pages/equipment-detail/*.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.5.2/vitest.config.mjs
npm.cmd run build -- --configuration production --stats-json
```

- 256 tests ciblés réussis dans six fichiers.
- 1 482 tests complets réussis dans 66 fichiers ; assertions renforcées dans
  les tests existants, pas de changement du nombre de cas.
- Build production réussi, bundle initial 605 652 octets, soit 605,65 kB.
  Évolution depuis UI 7.5.1 : +186 octets ; depuis UI 7.4 : +312 octets.
- Seul avertissement : seuil initial 500 kB dépassé de 105,65 kB.
  Aucun budget relevé et aucun package ajouté.

Preuves locales ignorées : [tests ciblés](../frontend/tmp/ui-7.5.2/targeted-tests.log),
[tests complets](../frontend/tmp/ui-7.5.2/full-tests.log),
[build](../frontend/tmp/ui-7.5.2/build.log),
[styles calculés, règles et largeurs](../frontend/tmp/ui-7.5.2/visual-checks.json),
[focus et navigation](../frontend/tmp/ui-7.5.2/navigation.json).

### Responsive et captures

21 contrôles DOM de largeur : les trois fiches à 1440, 1024, 1023, 768, 389,
391 et 320 px CSS. Pour chacun, scrollWidth égale clientWidth, sans débordement
global. La cible 390 exacte reste une réserve d'arrondi du navigateur ; les
contrôles à 389 et 391 ne sont pas présentés comme une vérification exacte.

Captures examinées visuellement, dans le dossier ignoré :

- [Référence Équipement desktop](../frontend/tmp/ui-7.5.2/screenshots/equipment-1440.png).
- [Capteur desktop avec focus](../frontend/tmp/ui-7.5.2/screenshots/sensor-desktop.png).
- [Capteur mobile](../frontend/tmp/ui-7.5.2/screenshots/sensor-mobile.png).
- [Mesure desktop](../frontend/tmp/ui-7.5.2/screenshots/measurement-desktop.png).
- [Mesure mobile](../frontend/tmp/ui-7.5.2/screenshots/measurement-mobile.png).

Limite de capture : plusieurs captures sous viewport imposé ont échoué ou
renvoyé une image du rendu précédent. Les images conservées ont été examinées
et nommées selon leur contenu effectivement rendu. Les captures Sensor/Mesure
sont des rendus desktop/mobile, sans revendiquer une image pour chaque largeur
exacte ; les dimensions précises sont attestées par les relevés DOM séparés.
Le viewport a été restauré et les onglets de recette fermés.

### Intégrité, réserves et Git

Aucun accès SQL direct, aucune commande PostgreSQL/Docker, aucun formulaire
soumis, aucune écriture métier pendant UI 7.5.2. La consultation navigateur
emploie les GET existants. Les 40 lignes et empreintes identiques de UI 7.5.1
restent les preuves historiques de la section 10, sans prétendre à une nouvelle
comparaison SQL pour cette finition CSS. Aucun changement de données requis.
Le seed strict demeure non conforme et inchangé. Réserves B-MES et B-SEN,
authentification, isolation tenant, unité historique et couverture PostgreSQL
non exhaustive conservées. Dialogue natif d'abandon toujours non vérifié.

Périmètre cumulé UI 7.5/7.5.1/7.5.2 : huit fichiers, soit les sept listés en
section 10 et le test Measurements List ajouté au diff. Six fichiers suivis
modifiés, le rapport et le test Sensor -> Measurements non suivis ; index vide.
HEAD 7b1265a et branche feature/frontend-measurements inchangés. Aucun secret,
capture, fixture temporaire ou artefact dans le périmètre Git. Liens du rapport
et espaces vérifiés ; git diff --check réussi. Aucun changement de contrat API
ou de décision MES-01 à MES-12. Aucun commit, push ou merge. UI 7.6 non commencée.
Validation attendue avant commit.
