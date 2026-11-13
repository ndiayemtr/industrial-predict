# AUTH-B2B-DEV-1 — installation B2B DEV à valider

Date : 12 novembre 2026. **Préparation uniquement ; aucune connexion PostgreSQL,
aucune migration, aucun DML, aucun GRANT, aucune sauvegarde réelle exécutés.**
Les résultats DEV fournis sont les préconditions déclarées, pas une observation
nouvelle. Aucun modèle, Docker, Angular, P101 ou lot préexistant n'est modifié.

## 1. Décision proposée et limite d'exécution

Cible unique : `industrial_predict_dev`, client `127.0.0.1:5434`, conteneur
`industrial-predict-postgres-ui47`. Profil unique :
`D:\integration\industrial-predict\development\config.json` ; secrets voisins,
hors Git. Ne pas utiliser `infra/ui47`, les ports historiques ou un `.env` backend.

Appliquer, dans cet ordre, **quatre** révisions, depuis l'unique version
`09ac8101e9fe` jusqu'à l'unique version **`b2b_0002_analyze`** :

| Révision | Parent | Effet |
| --- | --- | --- |
| `12e2fc65f372` | `09ac8101e9fe` | `oidc_transactions`, contraintes et index d'expiration |
| `4b7e2a91c6d0` | `12e2fc65f372` | utilisateurs, identités, appartenances, permissions |
| `b2b_0001_sessions` | `4b7e2a91c6d0` | unicité identité/utilisateur et sessions |
| `b2b_0002_analyze` | `b2b_0001_sessions` | remplacement du CHECK des permissions |

Graphe linéaire reconnu, sans branche, merge ni dépendance additionnelle.
La publication suivante est `p101_0001_operations`, **exclue** : ajout de
`prediction_records.p101_operation_id`, contraintes et FKs réciproques avec une
nouvelle table de journal, fonctions et triggers, dont des triggers sur
`prediction_records`. Une cible `head` inclurait ces effets hors périmètre si
le graphe général était chargé. Le graphe historique seul s'arrête à
`09ac8101e9fe` et ne découvre pas les publications B2B.

**Installation non exécutable avec l'outillage approuvé actuel.**
`backend/general_migrations/env.py` lève inconditionnellement
`MigrationExecutionDisabled`, l'INI est inerte, `request_execution()` refuse
toujours et seule l'étiquette synthétique `oidc-migration-test` est reconnue.
`preflight()` impose en outre le scope agrégé incluant P101 ; il n'est donc pas
un contrôle d'autorisation DEV B2B ciblé. Un succès statique ne lève aucun refus.

`infra/development/manage.py migrate` cible seulement `09ac8101e9fe`, puis
accorde des droits industriels et USAGE sur toutes les séquences : il n'installe
pas B2B et ne convient pas à cette opération. `backend/migrations/env.py`
recharge les réglages applicatifs et ne constitue pas un chargeur de cette chaîne.

Il faut un lot d'activation revu séparément : autorité et approbation liées aux
octets/destination, inventaire indépendant, chargeur immuable, transport vérifié,
transaction unique et scope limité aux quatre révisions. Aucun chargeur alternatif,
SQL manuel, `create_all`, `stamp`, modification des gardes ou faux profil de test
n'est fourni comme contournement. Cette mission prépare la décision ; elle
n'autorise pas ce lot d'activation ni l'installation.

## 2. Effets SQL exhaustifs et impact industriel

Les définitions complètes figurent en annexe, compilées hors connexion depuis
les déclarations AST vérifiées, sans importer les modules de révision et sans
invoquer leurs fonctions `upgrade`.

| Révision | Opérations explicites, dans l'ordre |
| --- | --- |
| OIDC | CREATE TABLE `public.oidc_transactions` ; CREATE INDEX `ix_oidc_transactions_expires_at` |
| Comptes | CREATE TABLE `public.local_users` ; CREATE TABLE `public.external_identities` ; CREATE INDEX `ix_external_identities_user_id` ; CREATE TABLE `public.company_memberships` ; CREATE INDEX `ix_company_memberships_company_id` ; CREATE TABLE `public.membership_permissions` |
| Sessions | ALTER TABLE `public.external_identities` ADD CONSTRAINT `uq_external_identities_id_user` UNIQUE (`id`,`user_id`) ; CREATE TABLE `public.application_sessions` ; CREATE INDEX `ix_application_sessions_user` ; CREATE INDEX `ix_application_sessions_expiry` |
| Analyse | ALTER TABLE `public.membership_permissions` DROP CONSTRAINT `ck_membership_permissions_role_cap` ; ADD CONSTRAINT de même nom avec plafond étendu |

Total : **14 opérations Alembic de schéma**, six tables, cinq index secondaires,
six PK, cinq UNIQUE, sept FK, 27 CHECK finaux, soit 45 contraintes finales.
Les PK/UNIQUE ajoutent onze index de support : **16 nouveaux index au total**.
Les trois PK entières simples utilisent SERIAL dans le dialecte PostgreSQL :
`local_users_id_seq`, `external_identities_id_seq`, `company_memberships_id_seq`,
leurs valeurs par défaut `nextval` et dépendances de propriété. Aucun nouveau
numérateur de session/OIDC ou de permissions. Tous les objets sont dans `public`.
Le catalogue attribue les noms des quatre PK de comptes non nommées explicitement
(`local_users_pkey`, `external_identities_pkey`, `company_memberships_pkey`,
`membership_permissions_pkey`) ; refuser tout conflit préexistant.

Alembic devra également faire évoluer sa **ligne de métadonnées** dans
`public.alembic_version` à chaque révision, dans la même transaction. Ce DML
technique sera inhérent à une installation future autorisée ; il n'est pas du
provisionnement métier et n'a pas été exécuté ici. Une interdiction de tout DML
même futur rendrait aussi une migration Alembic normale impossible.

Les publications n'incluent ni INSERT de compte/grant/session, ni UPDATE/DELETE
métier, ni GRANT/REVOKE, ni seed, backfill, trigger ou fonction B2B. Les six tables
doivent donc être **vides** juste après installation, avant ouverture du runtime.
Les droits nouveaux constituent un acte administratif distinct à approuver.

La seule référence aux huit tables industrielles est la FK
`company_memberships.company_id -> public.companies.id ON DELETE RESTRICT`.
Elle ne change aucune ligne ni colonne de `companies`. Elle crée des triggers
internes d'intégrité référentielle, y compris sur la table référencée : le schéma
industriel n'est donc pas intégralement identique au niveau de ces triggers.
Une fois des appartenances créées, supprimer/modifier une entreprise référencée
pourra être empêché par la FK ; aujourd'hui les six tables sont annoncées absentes.
La création de FK prend des verrous sur `companies` et peut attendre/bloquer des
écritures concurrentes. Les autres FK sont internes aux nouvelles tables, toutes
en RESTRICT, sans CASCADE. Les index sont ordinaires, pas CONCURRENTLY.

**Conclusion statique : aucune mutation de donnée industrielle prévue.**
La conservation réelle nécessite fenêtre sans écritures, comparaison des données,
séquences, ACL et schémas avant/après. Les 40 lignes des anciens rapports ne sont
pas une référence actuelle : établir un nouvel état avant installation.
Examiner aussi les event triggers préexistants, ACL par défaut et objets homonymes ;
des effets administratifs extérieurs aux quatre sources ne sont pas exclus par
leur seule lecture. Aucun résultat de durabilité/verrouillage réel n'est revendiqué.

## 3. CHECK d'analyse et dépendances runtime

`b2b_0002_analyze` est disponible et son hash/AST est reconnu. Ce n'est pas le nom
d'un CHECK : il remplace `ck_membership_permissions_role_cap`. Le nouveau prédicat
conserve toutes les combinaisons historiques et admet `predictions:analyze`
uniquement pour `company_admin`. Il est requis pour le runtime d'analyse décrit
dans `backend/app/b2b_runtime.md`, pas pour la simple existence des six tables.
Le retenir dans cette cible évite un schéma incompatible avec ce runtime sans
installer P101. Il ne donne aucun droit : il faut encore utilisateur actif,
lien issuer/subject exact, appartenance active et grant explicite dans l'entreprise.

La FK composite des sessions `(external_identity_id,user_id)` doit viser
`external_identities(id,user_id)` via l'UNIQUE ajoutée. La FK composite des
permissions `(membership_id,role)` doit viser `company_memberships(id,role)`.
Les PK/UNIQUE OIDC empêchent la collision d'identifiant et de digest de state.
L'annexe inclut tous les CHECK de formats, états, rôles, dates, durée, rotation et
version de contrat. Aucun de ces contrôles ne remplace l'admission du runtime.

## 4. Rôles SQL et transport — conditions de passage

État documentaire : `ui47_migrator` est propriétaire du schéma et des objets
migrés, rôle distinct non superutilisateur ; son secret a été vérifié lors de
la transition DEV. Ce n'est pas une preuve de ses ACL actuelles. À requalifier
avant exécution, en transaction de lecture seule :

- LOGIN, CONNECT sur la seule cible, USAGE et CREATE sur `public`, propriété
  d'`alembic_version` et des nouveaux objets ; capacité de modifier sa ligne de
  version ; REFERENCES (`id`) sur `companies` ou propriété de cette table.
- NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS ; pas
  d'héritage/appartenance permettant une élévation inattendue. Aucun rôle admin
  dans le moteur API. Ne pas ajouter un rôle si le contrôle échoue.
- `search_path` effectif limité à `public` (résolution implicite de `pg_catalog`
  conservée), aucun CREATE pour PUBLIC/runtime, aucune résolution via schéma
  utilisateur ou schéma temporaire contrôlable. Qualifier les noms administratifs.
- Transport : le profil public DEV ne prouve ni CA ni certificat serveur.
  La frontière générale exige `sslmode=verify-full` et une CA épinglée.
  Ne pas abaisser à `prefer`, `require` ou `disable` pour activer B2B. Si la
  cible loopback/certificat n'est pas compatible, **STOP**, décision transport
  distincte nécessaire, sans changement Docker dans ce lot.
- Propriétaires, ACL et default ACL à examiner avant création : aucune permission
  implicite PUBLIC, aucun grant global « toutes les tables/séquences » pour B2B.

Droits runtime à qualifier séparément ; les droits CRUD industriels existants
ne prouvent aucun droit sur les nouveaux objets :

| Objet | Besoin du code existant |
| --- | --- |
| `local_users`, `external_identities` | SELECT ; UPDATE sur une colonne au minimum pour les verrous de lignes |
| `company_memberships`, `membership_permissions` | SELECT ; UPDATE sur une colonne au minimum pour FOR SHARE |
| `application_sessions` | SELECT, INSERT ; UPDATE limité à `last_activity_at`, `revoked_at`, `replaced_by` ; aucun DELETE |
| `oidc_transactions` | SELECT, INSERT, DELETE pour consommation atomique ; UPDATE sur une colonne pour FOR UPDATE |
| `alembic_version` | SELECT seulement pour le runtime |
| Trois nouvelles séquences | aucun besoin du runtime de session/OIDC ; provisioning administratif distinct |

PostgreSQL ne possède pas ici de privilège « verrou seulement » : UPDATE(id),
UPDATE(membership_id) ou UPDATE(transaction_id) sont de réelles capacités de
modification, même si l'adaptateur n'en fait pas usage. Le profil minimal acceptable
pour memberships/grants reste à approuver ; **ne pas accorder UPDATE global ni
prétendre que le runtime ne peut pas gérer une appartenance après un tel grant**.
Si aucun profil acceptable n'est qualifié, conserver le runtime fermé. Aucun
GRANT n'est inclus dans la migration ni exécuté par ce dossier. Aucun nouveau
droit sur les tables industrielles n'est nécessaire pour l'installation elle-même.

## 5. Commandes PowerShell exactes disponibles

Depuis le dépôt, ces commandes sont **hors connexion**. Elles ne lisent pas les
secrets ni les fichiers privés. Arrêter au premier échec :

```powershell
Set-Location -LiteralPath 'D:\projets\industrial-predict'
$ErrorActionPreference = 'Stop'
$devPython = (Resolve-Path -LiteralPath '.\backend\.venv\Scripts\python.exe').Path
$devConfig = 'D:\integration\industrial-predict\development\config.json'
if (-not (Test-Path -LiteralPath $devConfig -PathType Leaf)) { throw 'Profil DEV absent' }
git status --short
if ($LASTEXITCODE -ne 0) { throw 'État Git indisponible' }
@'
import sys
sys.path.insert(0, 'backend')
from app.general_migrations import inspect_sources, resolve_upgrade
s = inspect_sources()
expected = ('12e2fc65f372','4b7e2a91c6d0','b2b_0001_sessions','b2b_0002_analyze')
assert resolve_upgrade(s.revisions,'09ac8101e9fe','b2b_0002_analyze') == expected
print(' -> '.join(('09ac8101e9fe',) + expected))
for f in s.sources:
    print(f.path, f.sha256)
print('OFFLINE ONLY; execution disabled')
'@ | & $devPython -B -
if ($LASTEXITCODE -ne 0) { throw 'Sources/graphe refusés' }
```

Prévalidation DEV existante **à exécuter seulement lors de la future fenêtre
autorisée de lecture**, avant installation ; non exécutée dans cette mission :

```powershell
& $devPython -B infra/development/manage.py check-db --config $devConfig
if ($LASTEXITCODE -ne 0) { throw 'STOP : prévalidation DEV refusée' }
```

Ce contrôle lit PostgreSQL sans DML mais ne qualifie ni le migrator, ni TLS,
ni toutes les contraintes ; il faut les lectures complémentaires ci-dessous.
Il attend la version historique et exactement huit séquences : **ne pas l'utiliser
comme contrôle après B2B** (on attend onze séquences si la base initiale en a huit).

**Commande de migration : indisponible, volontairement non inventée.** Ni
`manage.py migrate`, ni un `alembic upgrade b2b_0002_analyze` avec les INI actuels
ne constituent une commande DEV B2B approuvée. La future commande devra recevoir
explicitement le profil ci-dessus, départ `09ac8101e9fe`, cible
`b2b_0002_analyze`, liste exacte des quatre révisions, manifeste immuable et
référence d'approbation authentifiée. Sa syntaxe exacte doit être livrée et revue
avec le lot d'activation ; aucune commande d'installation utilisable n'existe
aujourd'hui. Ne pas remplacer ce manque par une URL en ligne de commande.

## 6. Lectures SQL avant/après à intégrer au futur lanceur

Connexion privée issue de `load_config($devConfig)` / `db_url(config, role)` de
`infra/development/manage.py`, sans afficher l'URL. Ne pas exécuter `migrate()`.
Charger uniquement les fonctions de configuration, sans settings applicatifs ;
imposer echo=False, hide_parameters=True, délais de connexion et transport
préalablement approuvé. Une transaction `REPEATABLE READ READ ONLY`, puis ROLLBACK,
pour les relevés. Aucune chaîne de connexion dans les logs ou transcriptions.

Lectures de contrôle (à faire avant et après, comparer les résultats privés) :

```sql
SELECT current_database(), current_user,
       current_setting('app.development_instance_id', true) AS instance_id,
       current_setting('cluster_name'), current_setting('server_version'),
       current_setting('search_path'), inet_server_addr(), inet_server_port(),
       (SELECT oid FROM pg_database WHERE datname=current_database()) AS database_oid;
SELECT version_num FROM public.alembic_version ORDER BY version_num;
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
       rolreplication, rolbypassrls, rolinherit
FROM pg_roles WHERE rolname IN ('ui47_migrator','ui47_app');
SELECT member::regrole, roleid::regrole, admin_option FROM pg_auth_members;
SELECT has_database_privilege('ui47_migrator',current_database(),'CONNECT'),
       has_schema_privilege('ui47_migrator','public','USAGE'),
       has_schema_privilege('ui47_migrator','public','CREATE'),
       has_column_privilege('ui47_migrator','public.companies','id','REFERENCES'),
       has_table_privilege('ui47_migrator','public.alembic_version','SELECT'),
       has_table_privilege('ui47_migrator','public.alembic_version','UPDATE');
SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid=pg_backend_pid();
SELECT nspname, nspowner::regrole, nspacl FROM pg_namespace WHERE nspname='public';
SELECT defaclrole::regrole, defaclnamespace::regnamespace, defaclobjtype, defaclacl
FROM pg_default_acl;
SELECT evtname, evtevent, evtenabled, evtfoid::regprocedure FROM pg_event_trigger;
SELECT c.relname, c.relkind, c.relowner::regrole, c.relacl,
       c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' ORDER BY c.relname;
SELECT conrelid::regclass, conname, contype, convalidated,
       condeferrable, condeferred, pg_get_constraintdef(oid, true)
FROM pg_constraint WHERE connamespace='public'::regnamespace
ORDER BY conrelid::regclass::text, conname;
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname='public' ORDER BY tablename,indexname;
SELECT c.relname, i.indisvalid, i.indisready
FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public';
SELECT tgrelid::regclass, tgname, tgisinternal, pg_get_triggerdef(oid, true)
FROM pg_trigger WHERE tgrelid IN
 (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace)
ORDER BY tgrelid::regclass::text,tgname;
SELECT * FROM pg_policies WHERE schemaname='public';
```

Vérifier avec l'identité migrator puis app réelle : rôles effectifs attendus,
cluster `industrial-predict-development`, version documentaire 17.10, OID 16384,
marqueur d'instance égal au profil privé. Comparer l'identifiant système du cluster
au `cluster_identifier` privé via une lecture administrative autorisée de
`pg_control_system()` ; ne pas élargir les privilèges du migrator pour cela.
Le port SQL serveur est 5432, le port **client** approuvé 5434 : ne pas les confondre.
`pg_stat_ssl` ne prouve pas la validation CA/nom côté client : contrôler aussi les
paramètres de connexion et l'empreinte de CA hors SQL.

Avant : exactement une ligne Alembic historique, six noms de tables absents,
absence des trois séquences et de tout objet/index homonyme attendu. Huit tables
industrielles conformes, PK `companies(id)` compatible et valide ; état SQL/ACL
attendu, absence d'event trigger non qualifié. Refuser tout état partiel.

Après : exactement une ligne `b2b_0002_analyze`, six tables ordinaires appartenant
au migrator, colonnes/types/nullabilité/defaults exacts selon annexe, six compteurs
à zéro, 45 contraintes B2B validées, 16 index valides/prêts et trois séquences
propres aux nouvelles tables. Contrôler également `pg_attribute`, `pg_attrdef`
et `pg_depend` pour les colonnes, defaults et dépendances des séquences ; ne pas
se contenter d'un compte d'objets. Pas de `p101_prediction_operations`, colonne
`p101_operation_id`, nouvelle fonction ou trigger P101.

Comparer les ACL effectives (`has_table_privilege`, `has_column_privilege`,
`has_sequence_privilege`) à la matrice approuvée, y compris les refus DDL,
TRUNCATE, TRIGGER, REFERENCES, droits Alembic et absence de grant option. Les ACL
brutes seules ne prouvent pas les droits hérités/PUBLIC/propriétaire. Ne pas tester
les refus par une écriture. Des tests réels de verrous sur deux connexions et
de consommation/rotation sont une qualification ultérieure distincte, pas une
prévalidation sans écriture.

Pour chacune des huit tables `companies`, `sites`, `equipments`, `sensors`,
`measurements`, `maintenance_records`, `prediction_records`,
`maintenance_recommendations` : relever count, toutes les lignes ordonnées par PK
et SHA-256 de leur représentation canonique, globalement et par ligne, sans publier
le contenu ; préserver timezone/encodage/format de sérialisation. Même algorithme
et même fenêtre sans écritures avant/après. Capturer les valeurs `last_value` et
`is_called` des huit séquences existantes par SELECT, sans appeler `nextval`.
Comparer aussi colonnes, contraintes/index industriels, ACL, propriétaires,
fonctions et triggers, avec la seule différence autorisée des triggers internes
de la nouvelle FK vers `companies`. Toute autre différence => STOP, diagnostic,
aucune réparation automatique.

## 7. Sauvegarde vérifiée et restauration avant DDL

L'archive historique avant renommage contenait des tables vides : elle ne remplace
pas une sauvegarde actuelle. Ne pas copier le volume PostgreSQL actif.

Fenêtre sans écriture applicative ni administrative dès le relevé initial et
jusqu'aux contrôles finaux ; suspendre les seuls clients DEV avec une procédure
approuvée, sans changer Docker. Vérifier l'absence de sessions d'écriture ; ne pas
terminer automatiquement les connexions d'autrui. Si la fenêtre n'est pas assurée,
ne pas migrer : sauvegarde et empreintes ne décriraient pas le même état.

Préparer une archive logique complète custom avec **pg_dump 17.10**, propriétaires,
ACL, schémas et données, aucune exclusion, aucune option `--no-owner/--no-acl`.
Identité `ui47_migrator` seulement si elle lit tous les objets/séquences et données ;
sinon administration dédiée **du même profil DEV**, après contrôle d'identité.
Pas de compte superutilisateur dans le runtime. Le dump de base ne contient pas
les définitions de rôles ni les paramètres propres à la base : conserver leurs
états, memberships, propriétaires et marqueur d'instance dans des preuves privées
de restauration, sans exporter de mots de passe ni toucher aux rôles.

Commandes natives exactes pour la sauvegarde future, **après** validation du
transport et préparation d'un environnement libpq de processus éphémère depuis le
seul profil DEV : PGHOST=127.0.0.1, PGPORT=5434,
PGDATABASE=industrial_predict_dev, PGUSER=ui47_migrator (ou admin autorisé),
secret lu en mémoire par le chargeur privé, PGSSLMODE=verify-full et PGSSLROOTCERT
issu de la configuration CA approuvée. Vider les variables PG héritées et interdire
PGSERVICE/PGOPTIONS et toute cible implicite. Ne pas afficher cet environnement.
**Ce chargeur transport/backup n'existe pas dans le dépôt ; aucune valeur de CA
ni service libpq approuvé n'est confirmée. Ces commandes ne sont donc pas une
procédure autonome prête à connecter. Ne pas les lancer sans ce prérequis.**

```powershell
$devDump = (Get-Command pg_dump.exe -ErrorAction Stop).Source
$devRestore = (Get-Command pg_restore.exe -ErrorAction Stop).Source
& $devDump --version
if ($LASTEXITCODE -ne 0) { throw 'pg_dump indisponible' }
& $devRestore --version
if ($LASTEXITCODE -ne 0) { throw 'pg_restore indisponible' }
# Arrêt humain si les deux versions ne sont pas 17.10.
# $devBackupDir : nouveau répertoire privé sous evidence, ACL restreintes,
# créé par le futur chargeur ; ne jamais réutiliser/écraser une ancienne preuve.
if (-not (Test-Path variable:devBackupDir)) { throw 'Répertoire de preuve non préparé' }
$devArchive = Join-Path $devBackupDir 'before-b2b.dump'
if (Test-Path -LiteralPath $devArchive) { throw 'Archive déjà présente' }
& $devDump --host=127.0.0.1 --port=5434 --dbname=industrial_predict_dev --no-password --format=custom --file=$devArchive
if ($LASTEXITCODE -ne 0) { throw 'STOP : sauvegarde échouée' }
if ((Get-Item -LiteralPath $devArchive).Length -eq 0) { throw 'Archive vide' }
& $devRestore --list $devArchive | Set-Content -LiteralPath (Join-Path $devBackupDir 'archive-toc.txt') -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'STOP : catalogue illisible' }
# Décompression/lecture intégrale hors connexion ; contient les données privées.
& $devRestore --file=(Join-Path $devBackupDir 'archive-readback.sql') $devArchive
if ($LASTEXITCODE -ne 0) { throw 'STOP : relecture intégrale échouée' }
Get-FileHash -LiteralPath $devArchive -Algorithm SHA256 |
    Select-Object Algorithm, Hash |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $devBackupDir 'archive-sha256.json') -Encoding utf8
```

Le futur chargeur doit lancer ces programmes avec arguments structurés et
environnement privé limité au processus enfant, capturer/sanitiser les erreurs,
puis supprimer la référence aux secrets en mémoire. Ne pas affecter un mot de
passe à une ligne de commande ou à l'environnement persistant de PowerShell.
Le SQL de relecture est une preuve privée, jamais un script d'installation B2B.

`pg_restore --list` et la relecture complète **ne prouvent pas la restaurabilité**.
Avant tout DDL, faire une répétition complète dans une destination de restauration
jetable explicitement approuvée et isolée (pas créée ni connectée dans cette mission,
ni les bases historiques/protégées), rôles nécessaires disponibles, aucun client.
La commande native sera :

```powershell
# Variables et environnement de la destination de restauration indépendante
# validés par le chargeur administratif ; aucune valeur par défaut DEV.
if (-not (Test-Path variable:devRestoreDatabase)) { throw 'Cible de répétition non approuvée' }
if ($devRestoreDatabase -eq 'industrial_predict_dev') { throw 'Répétition sur DEV interdite' }
& $devRestore --no-password --exit-on-error --single-transaction --dbname=$devRestoreDatabase $devArchive
if ($LASTEXITCODE -ne 0) { throw 'STOP : restauration de répétition échouée' }
```

Refuser également les autres bases protégées via l'inventaire du futur chargeur ;
ce seul test de nom n'est pas une autorisation de connexion. Exiger sortie 0,
version `09ac8101e9fe`, comparaison intégrale des huit tables/séquences/ACL/schémas
avec la référence et empreinte d'archive inchangée. Conserver journal expurgé,
SHA-256, versions outils et résultat de répétition. Aucune restauration n'a été
vérifiée pendant cette préparation. Sans répétition réussie, installation bloquée.

Restauration de DEV après incident : avant COMMIT certain, rollback de la transaction
unique puis contrôles ; après COMMIT confirmé, ne pas appeler `downgrade` (sessions
et analyse le refusent). Après accusé de COMMIT perdu, état **incertain** : aucune
relance ni restauration automatique ; reconnecter en lecture seule à la même cible,
qualifier version/objets/données, décider humainement.

Si retour à la sauvegarde nécessaire, laisser DEV fermé, conserver l'état incident
et toute donnée postérieure, mesurer la perte potentielle depuis la sauvegarde,
obtenir l'autorisation destructive spécifique. Restaurer d'abord l'archive vérifiée
dans une destination isolée, puis préparer un remplacement contrôlé de DEV ou une
restauration en place **sur base remise vide selon plan approuvé**. Un restore sur
une DEV non vide ne supprime pas les objets B2B supplémentaires : ne pas utiliser
aveuglément `--clean`, DROP/CASCADE ou `--create`. Le remplacement peut changer
l'OID et exige de requalifier le profil/les gardes ; ne pas modifier leurs attentes
pour masquer l'incident. Ces opérations destructives restent hors autorisation de
cette mission ; aucun script de suppression n'est fourni.

## 8. Transaction et exploitation après installation

Le futur exécuteur doit posséder une connexion migrator et une transaction externe
unique, vérifier identité et version avant DDL, fixer `search_path=public`,
`lock_timeout` et `statement_timeout` bornés (proposition 5 s / 60 s à qualifier),
`target_metadata=None`, DDL transactionnel, aucun commit par révision, aucune
connexion secondaire/autocommit. Exécuter exactement les quatre publications
immuables, vérifier les effets dans la transaction, puis confirmer explicitement
le commit ; vérification sur nouvelle connexion ensuite, sans retry automatique.

Attention : `manage.py` et `angular-proxy.cjs` attendent encore
`09ac8101e9fe`. Après migration, les gardes DEV actuels refuseront l'identité,
le contrôle SQL des huit séquences échouera et le proxy/API pourront renvoyer 503.
C'est un risque opérationnel certain, même sans mutation industrielle. Aucune
modification Angular ni de lanceur n'est faite ici. Pour rouvrir DEV, un lot distinct
doit faire approuver l'attente de version exacte et le contrôle explicite des huit
séquences industrielles plus trois B2B. Ne pas supprimer ou élargir les gardes pour
faire passer le contrôle. Installation du stockage ne signifie pas activation OIDC,
provisionnement de comptes, ouverture du runtime ou validation P101.

## 9. Plan court soumis à validation humaine

1. Valider les quatre révisions et le périmètre exact, les impacts FK/indisponibilité,
   puis faire livrer/revoir la frontière d'exécution DEV ciblée et son transport.
2. Approuver la fenêtre sans écritures et la destination de répétition ; relever
   l'identité, les ACL et les empreintes actuelles. Toute divergence => STOP.
3. Produire le dump actuel ; vérifier intégrité et restauration isolée complète.
   Tant que la répétition et le plan de retour ne sont pas validés, aucun DDL.
4. Autoriser explicitement l'installation ; exécuter uniquement jusqu'à
   `b2b_0002_analyze`, transaction unique, sans P101, sans provisioning de lignes.
5. Contrôler version, six tables vides, schéma/ACL exacts et huit tables/séquences
   industrielles préservées, puis traiter séparément droits runtime et réouverture.

**Statut : analyse ciblée prête à revue ; exécution bloquée par l'absence de
frontière DEV B2B activée, de transport qualifié et de sauvegarde restaurée vérifiée.**
Une validation humaine de ce plan ne transforme pas les gardes actuels en exécuteur.

## 10. Preuves locales et sources

Contrôle effectivement effectué : `inspect_sources()` puis `resolve_upgrade()`
hors connexion, 18 empreintes vérifiées (sources historiques, manifeste,
publications et frontière). Aucun import de révision. Les quatre SHA-256 UTF-8/LF :

```text
12e2fc65f372       8dd65b4517c0fba38f789b8b2ce016cafa80794fd0bcf6b8a35d194773da5274
4b7e2a91c6d0       0aed6450f32f5b5459684de15c72f442cdaa39672df30224affb6b55221f1a26
b2b_0001_sessions  64da06799a0c0d5033343ec91d6a5539d6cdef98ffc9a74f3d64a6a8beb1fe66
b2b_0002_analyze   ae59ca35458ca475e01057f025ff5b8e9f91af7e18301a0e6e3817454cb575fe
```

Validation locale complémentaire : **189 tests réussis** dans les cinq suites
`test_general_migrations.py`, `test_oidc_migration.py`,
`test_professional_account_migration.py`, `test_application_session_migration.py`
et `test_analysis_permission_migration.py`. Ce sont des contrôles hors connexion
des publications, du graphe, des schémas et des refus d'exécution ; aucune preuve
d'installation PostgreSQL n'en découle. Compilation documentaire : 14 opérations
et comptes de contraintes vérifiés indépendamment. Aucun test nouveau ajouté.

Sources : [frontière générale](../backend/general_migrations/README.md),
[garde](../backend/app/general_migrations.py),
[manifeste](../backend/general_migrations/revision_manifest.json),
[DEV permanent](../infra/development/README.md),
[lanceur DEV](../infra/development/manage.py),
[sessions](../backend/app/application_sessions.md),
[runtime](../backend/app/b2b_runtime.md),
[store OIDC](../backend/app/oidc_transaction_store.py).

## Annexe — SQL attendu, document de revue uniquement

Ces définitions décrivent les effets attendus ; elles ne constituent pas un
exécuteur approuvé. Aucun BEGIN/COMMIT, DML Alembic ou GRANT n'y est fourni.

### 12e2fc65f372

```sql
CREATE TABLE public.oidc_transactions (
	transaction_id VARCHAR(64) NOT NULL,
	state_digest VARCHAR(64) NOT NULL,
	browser_binding_digest VARCHAR(64) NOT NULL,
	policy_digest VARCHAR(64) NOT NULL,
	nonce VARCHAR(43) NOT NULL,
	code_verifier VARCHAR(43) NOT NULL,
	issuer VARCHAR(2048) NOT NULL,
	client_id VARCHAR(512) NOT NULL,
	callback_url VARCHAR(2048) NOT NULL,
	return_target VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	contract_version TEXT NOT NULL,
	CONSTRAINT pk_oidc_transactions PRIMARY KEY (transaction_id),
	CONSTRAINT uq_oidc_transactions_state_digest UNIQUE (state_digest),
	CONSTRAINT ck_oidc_transactions_transaction_id_hex CHECK (transaction_id ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_oidc_transactions_state_digest_hex CHECK (state_digest ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_oidc_transactions_browser_binding_digest_hex CHECK (browser_binding_digest ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_oidc_transactions_policy_digest_hex CHECK (policy_digest ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_oidc_transactions_expiry CHECK (expires_at > created_at),
	CONSTRAINT ck_oidc_transactions_nonce_length CHECK (char_length(nonce) = 43),
	CONSTRAINT ck_oidc_transactions_code_verifier_length CHECK (char_length(code_verifier) = 43)
);

CREATE INDEX ix_oidc_transactions_expires_at ON public.oidc_transactions (expires_at);
```

### 4b7e2a91c6d0

```sql
CREATE TABLE public.local_users (
	id SERIAL NOT NULL,
	state VARCHAR(16) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_local_users_positive_id CHECK (id > 0),
	CONSTRAINT ck_local_users_state CHECK (state IN ('active', 'suspended'))
);

CREATE TABLE public.external_identities (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	issuer VARCHAR(2048) NOT NULL,
	subject VARCHAR(2048) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_external_identities_positive_id CHECK (id > 0),
	CONSTRAINT ck_external_identities_issuer CHECK (issuer <> '' AND issuer = trim(issuer)),
	CONSTRAINT ck_external_identities_subject CHECK (subject <> '' AND subject = trim(subject)),
	CONSTRAINT ck_external_identities_key_bytes CHECK (octet_length(issuer) + octet_length(subject) <= 2048),
	CONSTRAINT uq_external_identities_key UNIQUE (issuer, subject),
	CONSTRAINT fk_external_identities_user FOREIGN KEY(user_id) REFERENCES public.local_users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_external_identities_user_id ON public.external_identities (user_id);

CREATE TABLE public.company_memberships (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	company_id INTEGER NOT NULL,
	state VARCHAR(16) NOT NULL,
	role VARCHAR(32) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_company_memberships_positive_id CHECK (id > 0),
	CONSTRAINT ck_company_memberships_positive_company_id CHECK (company_id > 0),
	CONSTRAINT ck_company_memberships_state CHECK (state IN ('active', 'inactive')),
	CONSTRAINT ck_company_memberships_role CHECK (role IN ('reader', 'technician', 'company_admin')),
	CONSTRAINT uq_company_memberships_user_company UNIQUE (user_id, company_id),
	CONSTRAINT uq_company_memberships_id_role UNIQUE (id, role),
	CONSTRAINT fk_company_memberships_user FOREIGN KEY(user_id) REFERENCES public.local_users (id) ON DELETE RESTRICT,
	CONSTRAINT fk_company_memberships_company FOREIGN KEY(company_id) REFERENCES public.companies (id) ON DELETE RESTRICT
);

CREATE INDEX ix_company_memberships_company_id ON public.company_memberships (company_id);

CREATE TABLE public.membership_permissions (
	membership_id INTEGER NOT NULL,
	permission VARCHAR(32) NOT NULL,
	role VARCHAR(32) NOT NULL,
	PRIMARY KEY (membership_id, permission),
	CONSTRAINT fk_membership_permissions_membership_role FOREIGN KEY(membership_id, role) REFERENCES public.company_memberships (id, role) ON DELETE RESTRICT,
	CONSTRAINT ck_membership_permissions_role_cap CHECK ((role IN ('reader', 'technician', 'company_admin') AND permission IN ('companies:read', 'assets:read', 'measurements:read', 'predictions:read')) OR (role IN ('technician', 'company_admin') AND permission = 'maintenance:write') OR (role = 'company_admin' AND permission = 'memberships:manage'))
);
```

### b2b_0001_sessions

```sql
ALTER TABLE public.external_identities ADD CONSTRAINT uq_external_identities_id_user UNIQUE (id, user_id);

CREATE TABLE public.application_sessions (
	secret_digest VARCHAR(64) NOT NULL,
	csrf_digest VARCHAR(64) NOT NULL,
	user_id INTEGER NOT NULL,
	external_identity_id INTEGER NOT NULL,
	authenticated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL,
	absolute_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	idle_timeout_seconds INTEGER NOT NULL,
	absolute_timeout_seconds INTEGER NOT NULL,
	revoked_at TIMESTAMP WITH TIME ZONE,
	replaced_by VARCHAR(64),
	contract_version VARCHAR(32) NOT NULL,
	CONSTRAINT pk_application_sessions PRIMARY KEY (secret_digest),
	CONSTRAINT fk_application_sessions_user FOREIGN KEY(user_id) REFERENCES public.local_users (id) ON DELETE RESTRICT,
	CONSTRAINT fk_application_sessions_external_identity_user FOREIGN KEY(external_identity_id, user_id) REFERENCES public.external_identities (id, user_id) ON DELETE RESTRICT,
	CONSTRAINT fk_application_sessions_replacement FOREIGN KEY(replaced_by) REFERENCES public.application_sessions (secret_digest) ON DELETE RESTRICT,
	CONSTRAINT ck_application_sessions_secret_digest_hex CHECK (secret_digest ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_application_sessions_csrf_digest_hex CHECK (csrf_digest ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_application_sessions_positive_ids CHECK (user_id > 0 AND external_identity_id > 0),
	CONSTRAINT ck_application_sessions_policy CHECK (idle_timeout_seconds > 0 AND absolute_timeout_seconds >= idle_timeout_seconds),
	CONSTRAINT ck_application_sessions_times CHECK (authenticated_at <= created_at AND created_at <= last_activity_at AND last_activity_at < absolute_expires_at),
	CONSTRAINT ck_application_sessions_absolute_expiry CHECK (absolute_expires_at = authenticated_at + absolute_timeout_seconds * interval '1 second'),
	CONSTRAINT ck_application_sessions_revocation CHECK (revoked_at IS NULL OR revoked_at >= last_activity_at),
	CONSTRAINT ck_application_sessions_rotation CHECK (replaced_by IS NULL OR (revoked_at IS NOT NULL AND replaced_by <> secret_digest)),
	CONSTRAINT ck_application_sessions_contract CHECK (contract_version = 'b2b-session-v1')
);

CREATE INDEX ix_application_sessions_user ON public.application_sessions (user_id, secret_digest);

CREATE INDEX ix_application_sessions_expiry ON public.application_sessions (absolute_expires_at);
```

### b2b_0002_analyze

```sql
ALTER TABLE public.membership_permissions DROP CONSTRAINT ck_membership_permissions_role_cap;

ALTER TABLE public.membership_permissions ADD CONSTRAINT ck_membership_permissions_role_cap CHECK ((role IN ('reader', 'technician', 'company_admin') AND permission IN ('companies:read', 'assets:read', 'measurements:read', 'predictions:read')) OR (role IN ('technician', 'company_admin') AND permission = 'maintenance:write') OR (role = 'company_admin' AND permission IN ('memberships:manage', 'predictions:analyze')));
```
