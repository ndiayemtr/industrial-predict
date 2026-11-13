# AUTH-B2B-DEV-2 — garde-fous B2B du gestionnaire DEV

12 novembre 2026. **Code préparé pour revue humaine. Aucune connexion PostgreSQL,
migration, sauvegarde réelle ou restauration réelle exécutée.**

## Périmètre livré

Le point d'entrée reste `infra/development/manage.py`. Quatre actions explicites
s'ajoutent : `b2b-preflight`, `b2b-backup`, `b2b-rehearse`, `b2b-migrate`.
`b2b_policy.py` ne gère aucune connexion ni migration : il vérifie la politique,
les publications et les preuves locales. Aucun nouveau gestionnaire, modèle,
compte SQL ou système d'authentification n'est créé.

`b2b-policy.json` fixe la cible DEV, le chemin du profil privé, l'OID 16384,
le cluster et le marqueur d'instance documentés, le rôle `ui47_migrator`, le scope
des six tables, les quatre révisions et les 18 empreintes de la publication
existante. Le SHA-256 du fichier de politique est lui-même fixé dans le code.
Toute évolution requiert une revue ; aucune commande ne régénère ces approbations.

Séquence unique :

```text
09ac8101e9fe -> 12e2fc65f372 -> 4b7e2a91c6d0
             -> b2b_0001_sessions -> b2b_0002_analyze
```

`inspect_sources()` et `resolve_upgrade()` existants sont réutilisés, ainsi que
`load_config()`, `db_url()` et `inspect_connection()` du gestionnaire DEV.
Les contrôles AST/empreintes existants restent intacts. P101 est lu uniquement
pour vérifier le graphe publié complet ; aucun module P101 n'est chargé/exécuté.
`head`, autres cibles, départs intermédiaires et autres rôles sont refusés.

Cette adaptation constitue le chemin administratif DEV ciblé préparé à la suite
d'[AUTH-B2B-DEV-1](auth-b2b-dev-1.md), dont les constats d'indisponibilité étaient
l'état antérieur. Le garde générique `request_execution()`, l'INI inerte et
`general_migrations/env.py` demeurent fermés ; aucun drapeau ne les ouvre.
Les commandes historiques `migrate`, `check-db`, API et frontend restent inchangées.
Ne pas utiliser `migrate` pour B2B.

## Autorité et refus

La prévalidation est exclusivement locale : elle n'ouvre pas le profil de mot de
passe, n'appelle ni SQL, ni Docker, ni outil PostgreSQL. `--current-revision` est
une **déclaration** obligatoire, pas une observation du serveur. Son rapport
indique `stage=offline_prevalidation`, `live_verified=false`,
`approval_verified=false`, `backup_verified=false`, `execution_enabled=false`.
Une séquence acceptée ne constitue jamais une permission d'exécuter.

Chacune des trois actions opérationnelles exige un terminal interactif et la
saisie exacte d'une phrase contenant **l'action**, le **SHA-256 du plan** et,
pour restauration/migration, le **SHA-256 de l'archive**. Il n'existe ni `--yes`,
ni confirmation par fichier JSON, ni saisie automatique par pipe. La confirmation
précède toute connexion PostgreSQL ; la migration exige également les preuves
locales avant même cette demande. Une confirmation BACKUP n'autorise ni RESTORE
ni MIGRATE. Ne pas automatiser la saisie ou appeler directement les fonctions.

La frontière d'autorité est l'opérateur local autorisé, son terminal, les ACL des
fichiers privés et les identifiants SQL de migration. Ce n'est pas un service
d'approbation signé, ni une isolation contre un administrateur capable de modifier
le code ou ses secrets. Les reçus sont des preuves locales à examiner, pas des
certificats d'autorisation. Avant le DDL, la commande de migration relit aussi
la destination restaurée en lecture seule et compare son état : un booléen JSON
`verified` ne suffit pas. Le contrôle humain distinct reste obligatoire.

## Prérequis encore à qualifier avant toute opération PostgreSQL

- Profil unique : `D:\integration\industrial-predict\development\config.json`.
  Les marqueurs fixés dans la politique proviennent des rapports DEV ; toute
  divergence actuelle doit être instruite, jamais remplacée automatiquement.
- Transport privé `b2b_transport` ajouté et approuvé dans ce même profil :
  `sslmode=verify-full`, `sslrootcert` absolu hors dépôt, `ca_sha256` exact de la CA.
  Aucune CA, clé ou modification de profil privé n'a été fournie pendant ce lot.
  Le certificat doit valider **127.0.0.1** ; aucune substitution de nom/port ni
  désactivation TLS. Sans cette qualification, les actions opérationnelles refusent.
- Aucun paramètre d'environnement `PG*` hérité pour les connexions du gestionnaire.
  Les sous-processus PostgreSQL reçoivent un environnement PG fermé, explicite,
  avec le seul secret migrator en mémoire dans le processus enfant. Aucun secret
  dans argv, rapport ou erreur. Les erreurs natives sont capturées sans affichage.
- Outils locaux `pg_dump` et `pg_restore` **17.10**, approuvés dans PATH ; pas de
  téléchargement, de binaire dans Docker ou de repli vers une autre version.
- Rôle migrator non privilégié, LOGIN, propriétaire de `public`, des tables et
  séquences existantes, aucun membership de rôle, accès aux données/séquences,
  REFERENCES sur `companies(id)` et droit de maintenir Alembic. Le contrôle
  d'identifiant système utilise `pg_control_system()` : si son exécution n'est pas
  déjà autorisée au migrator, **STOP et qualification administrative distincte** ;
  aucun GRANT automatique n'est ajouté. PUBLIC/runtime ne doivent pas créer dans
  `public`. Aucun event trigger actif ou default ACL migrator applicable.
- Parent privé `...\development\evidence` existant, ACL Windows restreintes
  contrôlées par l'opérateur, espace pour dump et relecture complète en SQL privé.
  Le nouveau sous-répertoire de preuve ne doit pas exister. Les archives sont
  confidentielles ; ne pas publier le répertoire privé en bloc.
- Destination de répétition **préexistante**, vide, sans clients, sur le même
  cluster DEV, base réservée `industrial_predict_b2b_restore` ; OID et marqueur
  distincts de DEV, propriétaire compatible avec le migrator. Sa préparation est
  une opération administrative séparée : aucun CREATE DATABASE ou changement
  Docker n'est fourni/exécuté ici. Inventaire privé voisin `b2b-restore.json` :

```json
{
  "database": "industrial_predict_b2b_restore",
  "database_oid": 0,
  "instance_id": "A_REMPLACER_PAR_LE_MARQUEUR_ISOLE_APPROUVE",
  "cluster_identifier": "7697614558579179559"
}
```

Les valeurs 0 et A_REMPLACER sont délibérément invalides. Cet inventaire n'est
pas une approbation : l'identité réelle est vérifiée avant restauration. Une base
du même cluster assure l'isolation logique du schéma/données, pas une validation
de reprise après perte du cluster. Aucun choix de base arbitraire n'est possible.

## Commandes opérateur

**Seule la première commande ci-dessous est hors connexion.** Aucune commande
opérationnelle n'a été lancée pour ce lot. Arrêter au premier échec et ne jamais
relancer automatiquement une restauration ou migration incertaine.

```powershell
Set-Location -LiteralPath 'D:\projets\industrial-predict'
$ErrorActionPreference = 'Stop'
$devPython = (Resolve-Path -LiteralPath '.\backend\.venv\Scripts\python.exe').Path
$devConfig = 'D:\integration\industrial-predict\development\config.json'

& $devPython -B infra/development/manage.py b2b-preflight --config $devConfig --current-revision 09ac8101e9fe --role ui47_migrator --target b2b_0002_analyze
if ($LASTEXITCODE -ne 0) { throw 'STOP : prévalidation refusée' }
```

Après revue du code/plan et **validation humaine des opérations PostgreSQL**,
dans un terminal opérateur interactif, une fenêtre sans écritures industrielles
ou administratives doit être maintenue jusqu'aux contrôles finaux. Les applications
DEV seront maintenues fermées par une procédure approuvée ; ce lot ne les arrête
pas et ne termine aucune connexion. Ne pas agir sur les services historiques.

Sauvegarde complète actuelle, avec propriétaires/ACL, aucune exclusion :

```powershell
$devBundle = Join-Path 'D:\integration\industrial-predict\development\evidence' ('auth-b2b-' + (Get-Date -Format 'yyyyMMddTHHmmss'))
& $devPython -B infra/development/manage.py b2b-backup --config $devConfig --bundle $devBundle --target b2b_0002_analyze
if ($LASTEXITCODE -ne 0) { throw 'STOP : sauvegarde non validée' }
```

Le gestionnaire vérifie l'identité migrator, la version et l'ensemble des huit
tables/séquences dans une transaction de lecture seule REPEATABLE READ. Il exporte
son snapshot pour `pg_dump --format=custom --snapshot=...`, maintient la transaction
ouverte pendant le dump, vérifie le catalogue avec `pg_restore --list`, effectue
une relecture intégrale hors connexion et calcule SHA-256. `backup.json` contient
les empreintes privées des huit tables, schémas, ACL et séquences. Un échec laisse
un répertoire incomplet, sans preuve de succès ; ne pas le réutiliser/écraser.

Répétition exclusivement dans la base isolée inventoriée :

```powershell
& $devPython -B infra/development/manage.py b2b-rehearse --config $devConfig --bundle $devBundle --target b2b_0002_analyze
if ($LASTEXITCODE -ne 0) { throw 'STOP : restauration isolée non validée' }
```

La commande refuse une base active, un mauvais OID/marqueur/cluster, une destination
non vide, une preuve existante, une archive altérée ou un backup de plus de 24 h.
Après confirmation interactive, elle vérifie la cible en lecture seule, lance
`pg_restore --exit-on-error --single-transaction` sur **la base isolée uniquement**,
puis compare version, lignes complètes hachées, colonnes, contraintes, index,
triggers non internes, propriétaires/ACL industriels et états/paramètres des
séquences. `restore.json` n'est créé qu'après égalité et recontrôle du SHA-256.
Ni `--clean`, ni `--create`, ni suppression/recréation automatique de base.
Si la restauration échoue ou si son commit est incertain, garder la destination
isolée fermée et instruire l'incident ; pas de répétition automatique.

Commande de migration **préparée, non exécutée**, à faire approuver séparément :

```powershell
& $devPython -B infra/development/manage.py b2b-migrate --config $devConfig --bundle $devBundle --target b2b_0002_analyze
if ($LASTEXITCODE -ne 0) { throw 'STOP : examiner la phase et l’état de commit avant toute action' }
```

La commande refuse absence, altération ou péremption des deux reçus/archive (24 h),
une restauration antérieure à la sauvegarde, une différence d'inventaire, puis exige
la confirmation MIGRATE. Elle relit indépendamment la restauration isolée avant de
connecter DEV. La source active doit être identique à la sauvegarde restaurée.
Toute activité depuis le backup impose un nouveau bundle et une nouvelle répétition.

## Exécution préparée et limites de qualification

Une seule connexion migrator et transaction externe pour le DDL et les lignes
Alembic. Verrou consultatif transactionnel exclusif, `lock_timeout=5s`,
`statement_timeout=60s`, `search_path=public`, timezone UTC ; verrous SHARE sur les
huit tables industrielles et Alembic pour stabiliser les comparaisons. Ces verrous
ne remplacent pas la fenêtre sans écritures : les séquences et DDL d'autres
administrateurs exigent aussi une discipline opérateur.

Les quatre sources sont capturées après contrôle de leurs empreintes ; l'exécution
ne rouvre jamais leurs chemins. Le gestionnaire construit uniquement ces quatre
étapes Alembic en mémoire, plus un marqueur historique **jamais exécuté**. Les
fonctions upgrade publiées sont invoquées par le runtime Alembic, qui maintient
sa version normalement. Aucun chargeur physique générique, env alternatif,
SQL DDL recopié ou stamp n'est installé. Aucune migration P101/historique rejouée,
aucun GRANT/seed, aucun provisioning de compte ou session.

Avant commit : version finale, six tables vides, comptes de colonnes, 45 contraintes
validées, 16 index valides, onze séquences attendues et absence de droits runtime
B2B automatiques ; empreintes industrielles identiques. Les sources figées et
l'absence d'event trigger actif sont essentielles : ces comptes seuls ne sont pas
un comparateur arbitraire de schémas. Vérifier aussi l'annexe SQL d'AUTH-B2B-DEV-1
lors de la qualification réelle. Après commit : nouvelle connexion et mêmes
contrôles. Aucun privilège runtime B2B n'est livré ; sa qualification est distincte.

Échec avant commit : rollback, pas de retry. Exception pendant commit :
`B2B_COMMIT_UNCERTAIN`, pas de restauration/relance automatique. Échec après commit
confirmé : `B2B_COMMIT_CONFIRMED_POSTCHECK_FAILED`, garder DEV fermé. Le plan de
retour à la sauvegarde reste celui d'AUTH-B2B-DEV-1, sous approbation destructive
distincte ; pas de downgrade ni de restauration en place sur DEV active.

La CLI expose ces deux marqueurs constants sans détail de pilote ni secret :
code de sortie **3** pour commit incertain, **4** pour commit confirmé suivi d'un
échec de contrôle ; **2** pour les autres refus/erreurs. Ne pas interpréter un
code non nul comme la preuve qu'aucun commit n'a eu lieu.

**Les gardes courants API/proxy restent à la version historique et attendent huit
séquences : DEV ne doit pas être rouvert après installation avec ces attentes.**
Aucun changement Angular/P101 n'est fait ici. Cette mission prépare l'installation,
pas l'activation du runtime, d'OIDC ou la disponibilité après migration.

## Tests et état de livraison

Résultats effectivement obtenus hors connexion : **35 tests B2B**, **10 tests
historiques du gestionnaire**, **189 tests existants des migrations générales,
OIDC, comptes, sessions et plafond d'analyse** réussis, soit **234 tests**.
Les tests transactionnels simulent entièrement le runner et les connexions ;
aucune qualification PostgreSQL/TLS réelle n'en découle. `git diff --check` conforme.

Tests dédiés : refus de cible/profil/OID/marqueur/cluster/rôle/version, graphe
inattendu, empreinte divergente et changement pendant capture, P101/head, absence
d'approbation, transport faible/CA divergente, reçus manquants/faux/périmés,
archive altérée, restauration sur DEV ou répertoire non vide, dérive industrielle,
échec de sauvegarde et classification du commit. Les scénarios de transaction
utilisent un **runner Alembic remplacé par un mock** : aucune fonction upgrade
n'est invoquée. Les appels réseau/SQL/outils externes sont interdits par défaut.

Commandes de validation hors connexion :

```powershell
& backend/.venv/Scripts/python.exe -B -m unittest discover -s infra/development -p test_b2b.py -v
& backend/.venv/Scripts/python.exe -B -m unittest discover -s infra/development -p test_manage.py -v
```

Fichiers de ce lot : `infra/development/manage.py`, `infra/development/README.md`,
`infra/development/b2b_policy.py`, `infra/development/b2b-policy.json`,
`infra/development/test_b2b.py`, ce dossier. Les autres lots non commités sont
conservés. Aucun commit, push, modification de profil privé ou de base.

**Arrêt demandé : revue humaine du code, du transport, de la destination isolée
et du plan d'exploitation avant tout lancement d'une action PostgreSQL.**
