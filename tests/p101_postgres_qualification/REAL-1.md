# P101-REAL-1 — première exécution sous autorisation explicite

Base contrôlée : `feature/auth-b2b-identity-access`,
`f2620aa022a4aa8d215208018b2b2886b1bcd217`, dépôt et index propres avant ce lot.
Aucun Docker, PostgreSQL, réseau de campagne, build, téléchargement, migration
ou écriture réelle n'a été utilisé pour développer/valider ce lot.

## État après FIX1 : l'exécution réelle reste fermée

Le noyau reste `execution.CampaignExecutor`. Le parcours `execute_approved` et
PostgresBackend restent préparés, mais `LiveGuard` refuse toute exécution réelle :
aucun collecteur Docker authentifié distinct du signataire readiness n'est
disponible. `run_live`, le CLI RUNNER-1 et le writer métier restent fermés. Il n'existe
ni booléen d'activation par défaut, ni connexion à l'import, ni DSN d'environnement.
`run_simulated` refuse un backend réel. Le compilateur et les 14 révisions épinglées
restent inchangés ; aucun import Python de migration, stamp ou create_all.

`wire_transport` étend le protocole INFRA-3 **sans modifier son transport RO**.
Il réutilise `_context` (CA explicite, SAN obligatoire, TLS >= 1.2), `_Scram`
(SCRAM-SHA-256 et signature serveur), la négociation SSLRequest et les primitives
de lecture bornée. Une seule socket TCP numérique est enveloppée en SSLSocket ;
le DER est capturé sur cette socket, qui transporte ensuite toutes les opérations
SQL. Adresse du pair, certificat, PID BackendKeyData et identité SQL sont vérifiés.
Aucune seconde connexion TLS et aucun pont libpq/ctypes. PsycopgBoundConnector
reste interdit ; la limite de certificat de son API n'est pas contournée.

Parse/Bind/Describe/Execute/Sync envoient les valeurs séparément du SQL. Les `%s`
des seuls templates figés deviennent `$1`, `$2`, etc. Les DDL sans paramètres
gardent littéralement `%ROWTYPE`. Le pilote gère résultats scalaires/JSON, NULL,
CommandComplete, ReadyForQuery, Notice/ParameterStatus, erreurs SQLSTATE et états
IDLE/INTRANS/INERROR. COPY, plusieurs commandes par Parse, messages inattendus,
types inconnus et réponses démesurées sont refusés. Pas de connexion de cancel.
Références : [flux PG17](https://www.postgresql.org/docs/17/protocol-flow.html),
[formats des messages](https://www.postgresql.org/docs/17/protocol-message-formats.html).

Une erreur serveur est drainée jusqu'à ReadyForQuery, sans conserver diagnostics,
DETAIL, CONTEXT ou payload. Une rupture ou erreur de protocole ferme le canal.
Un COMMIT n'est confirmé qu'avec tag COMMIT et état IDLE. Un rejet classes 23/40
avec canal sain et IDLE est un rejet connu ; toute autre perte d'acquittement est
incertaine. Aucun retry, rollback présenté comme preuve, effacement de claim ou
nouvelle tentative implicite. La clé d'opération permet une réconciliation manuelle.
La fonction de réconciliation après panne n'est pas activée dans ce lot.

## Rôles et transaction

Rôles B2B inchangés : admin de bootstrap, migrator, runtime B2B et observer.
Un **cinquième rôle** déterministe `<campaign.database>_p101_writer` appartient
uniquement à cette nouvelle campagne. Le runtime B2B ne reçoit aucun droit.
Le migrator reste non-superuser, sans CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS,
sans appartenance de rôle ; CREATE/USAGE sur public proviennent du bootstrap.

Le programme signé couvre aussi `privileges.grant_plan` : après la 14e révision,
dans la même transaction de migration, le propriétaire émet quatre GRANT fixes
sur les objets installés : SELECT pour writer/observer, INSERT pour les cinq
tables sources plus prédiction/journal, MAINTAIN sur les neuf tables métier pour
les verrous, USAGE sur les sept séquences utilisées. Il ne crée ni rôle ni mot
de passe. USAGE du schéma est une étape préalable d'admin ; la première ligne du
grant-plan l'indique, mais le migrator n'essaie pas de la réémettre.

`privileges.review` vérifie les droits effectifs, y compris droits par colonne,
absence d'UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER, d'appartenances, d'objets possédés,
de CREATE/TEMP base, de CREATE schéma, de contrôle de session_replication_role,
SUPERUSER et BYPASSRLS pour le writer/observer. MAINTAIN est requis pour les LOCK PG17 ; aucun UPDATE
n'est ajouté pour résoudre ce besoin. L'observateur n'a que SELECT/USAGE schéma,
aucun accès aux séquences. Les définitions, propriétaires et ACL du catalogue
doivent toujours correspondre à une baseline indépendante approuvée.

Writer : SERIALIZABLE READ WRITE. Observateur : REPEATABLE READ READ ONLY.
Le writer first-pair verrouille les neuf tables métier **avant le premier SELECT
dans sa transaction**, puis vérifie catalogue et absence de données. Le catalogue
capture `relrowsecurity`, `relforcerowsecurity` et les politiques (définitions,
commandes et rôles) de toutes les tables ordinaires/partitionnées de `public`.
Toute RLS active, forcée, politique présente ou inventaire incomplet est refusé.
Sous les verrous, le rôle writer est requalifié comme non-superuser, sans
BYPASSRLS, non propriétaire et sans appartenance ; les drapeaux et politiques sont
relus avant `COUNT(*)`. La baseline doit inclure cette section RLS vide : aucun
comptage filtré ne peut être accepté comme preuve de vacuité. Cela évite
de figer un snapshot antérieur à l'acquisition du verrou. Les relectures de fixtures
n'ont plus besoin de FOR SHARE (qui demanderait UPDATE) puisque les verrous de
table sont déjà détenus. Voir [LOCK PG17](https://www.postgresql.org/docs/17/sql-lock.html).
Les simulations EXEC-2 gardent leur comportement historique.

Les 15 fixtures sont synthétiques, avec dix références plus cible et évaluation
P101 existante. nextval, journal, prédiction réciproque, SET CONSTRAINTS ALL
IMMEDIATE et un COMMIT unique utilisent le plan existant. Le writer reste ouvert
pendant la connexion observer distincte ; objets physiques, sockets, handles et
PID doivent différer. Toutes les colonnes de la paire, IDs réellement retournés,
empreintes, résultats et contenu canonique sont comparés. Pas de succès par compteur.

Limites opérationnelles : timeout socket 3 s par attente, budget 30 s par canal
et noyau ; statement_timeout 5 s et lock_timeout 1 s. Le premier essai réel devra
confirmer que les 14 migrations tiennent dans ces bornes. L'obtention d'un timeout
n'autorise ni retry automatique ni élargissement silencieux des budgets.

## Autorisations et registre

Deux enveloppes Ed25519 sont nécessaires :

1. Intent EXEC-1 inchangé, liant campagne/destination, opération, sources/SQL,
   ressources, fixture, état initial et catalogue attendu, fenêtre <= 15 minutes.
2. Readiness REAL-1 distincte, liée à l'empreinte exacte de cet Intent, à son
   inventaire, au précontrôle Docker frais, aux limites des deux conteneurs,
   au lock d'artefacts et au chemin du registre ; fenêtre <= 120 secondes.

L'autorité humaine doit examiner et signer séparément les affirmations de
readiness : ressources neuves, routes non chevauchantes, stockage/ACL/durabilité
du registre, runtime/artefacts vérifiés, TLS indépendant, GRANT du rôle P101
explicitement approuvés, consentement humain. **Une signature n'est pas une preuve
physique de ces faits.** Une readiness signée authentifie l'approbation du
signataire, pas le fait que le Docker Engine ait été observé par le collecteur.
P101ResourceCollector produit `unverified_external`; aucune clé, attestation ni
provenance distincte du collecteur n'est disponible. Le drapeau
`AUTHENTICATED_DOCKER_COLLECTOR_AVAILABLE` reste donc faux et `LiveGuard` refuse
même une readiness signée affirmant le contraire. L'inventaire injecté par le
backend reste une configuration attendue, jamais une observation Docker avant
COMMIT. Le transport TLS/SQL est codé mais reste inaccessible à l'opérateur tant
que ce prérequis manque.

Le précontrôle est effectué sur l'hôte par P101ResourceCollector, en lecture seule,
en réutilisant le transport CLI borné et les formats du collecteur B2B. Son profil
est explicitement différent : une seule exception, le volume de registre P101
neuf du runner. Les observations ne sont jamais réécrites pour passer le profil
B2B sans mount. Contexte/endpoint/Engine ID, images, limites, réseau exact à deux
membres, ports absents et les deux volumes sont comparés aux références attendues.
Les options de driver des volumes doivent être absentes et leur Mountpoint doit
correspondre au nom neuf : un volume local servant de bind/NFS est refusé.
La source est `p101-docker-cli`, mais ne constitue pas une provenance authentifiée
et ne peut autoriser une exécution réelle. La fenêtre de
120 s couvre la collecte, sa revue/signature et la transaction. Le réseau/Engine
doivent rester sous contrôle de l'opérateur durant cette fenêtre (TOCTOU externe).

Le runner Linux UID 10001 utilise un dossier existant mode 0700 sur volume
persistant dédié, propriétaire UID 10001, sans symlink/junction ni parent partagé
en écriture sans sticky bit. Les claims exclusifs/fsync/verrous EXEC-1 sont
réutilisés ; le parent est désormais fsync après claim/outcome sur Linux. Un
échec conserve le claim et bloque le rejeu. Windows n'est pas autorisé pour cette
entrée réelle. La qualification après panne électrique/stockage reste externe,
requise dans la readiness ; fsync seul n'en est pas une preuve.

Les clés publiques de confiance sont administrées hors de la requête, dans
`/etc/p101-qualification/trusted-keys.json`, fichier et parents root-owned sans
écriture groupe/autres, embarqué dans l'image du runner. La commande d'exécution
ne permet pas de choisir un autre trust-store. L'API Python suppose comme EXEC-1
un appelant de confiance pour construire CampaignExecutor. Aucune clé privée de
signature n'est fournie. La configuration de campagne n'est pas autorisée à
contenir ses propres trusted_keys ; la requête ne peut pas fournir sa racine.

## Cible d'infrastructure et artefacts — rien n'est créé ici

- Image PostgreSQL locale attendue :
  `sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317`.
  Son RepoDigest réel reste à fournir indépendamment ; un image ID n'est pas un
  RepoDigest. Version SQL attendue par Campaign : 170010, à vérifier au démarrage.
- Noms PostgreSQL, base, réseau, rôles et volume data : convention B2B liée à
  l'UUID neuf. Aucun nom/ID historique ou inconnu n'est accepté par défaut.
- Bridge interne, exactement PostgreSQL + runner, aucun port publié ni autre
  réseau. `172.30.121.0/28` reste **candidat non approuvé** ; inventaire Docker et
  routes hôte/VM/VPN à contrôler avant attribution, puis approbation exacte.
- Volume data neuf `b2bq_<UUIDhex>_data` ; second volume neuf
  `b2bq_<UUIDhex>_exec_registry` monté uniquement dans le runner à
  `/var/lib/p101-qualification`, avec dossier `p101q-exec-<UUIDhex>`.
  Ce volume supplémentaire résout le conflit racine RO/registre durable ; il ne
  réutilise aucun volume DEV/OIDC/P101 historique. Aucun socket Docker monté.
- Racines RO, non privilégié, restart=no, 1 CPU chacun, PostgreSQL 1 GiB,
  runner 512 MiB, shm 64 MiB chacun. Aucun autre mount ; secrets/certificats
  PostgreSQL indépendants préparés sur son volume data, CA publique/configuration
  et requêtes d'approbation sur le volume de campagne du runner. Aucune clé privée
  de serveur PostgreSQL dans l'image du runner. Désactiver le socket Unix PG ou
  le placer sur le volume data, puisque /var/run est en lecture seule.

Le modèle Dockerfile.real1.in a une base **non renseignée**, sans tag de repli.
Il installe exclusivement depuis le wheelhouse local avec --no-index,
--no-deps, --require-hashes, puis lance operator avec action `describe` par défaut.
Le lock `p101-real1-artifacts-v1` doit fournir : platform linux/amd64, Python
3.12.10, base_image par digest, image ID/RepoDigest PostgreSQL, program_sha256,
versions de tous les packages et empreintes des fichiers locaux requirements.lock,
wheels et trust-store. Les fichiers ne sont ni téléchargés ni installés par le
parcours d'exécution : verify_artifacts refuse un lock absent/incohérent et vérifie
versions installées + hashes. La fermeture transitive, la provenance des wheels
et la reproduction du build font l'objet de la revue indépendante signée, sans
prétendre qu'une liste de versions suffit. Aucun artefact Linux figé n'est inventé.

Références existantes conservées : SQLAlchemy 2.0.52, Alembic 1.19.1,
cryptography 50.0.2, pandas 3.0.6, numpy 2.5.3, psycopg/psycopg-binary 3.3.4
(TransactionStatus uniquement). Le transport RW n'ajoute aucun package natif.
CA directe, mot de passe ASCII et absence de SCRAM channel binding hérités
d'INFRA-3 restent des limites explicites, pas des garanties de production.

## Parcours opérateur précis (commandes proposées, non exécutées)

1. Après autorisations de provisionnement distinctes : préparer les ressources
   neuves, certificats, registre durable et rôles indépendants. L'admin possède
   la base ; révoquer CREATE/TEMP publics et CREATE public du schéma ; accorder
   CONNECT, USAGE public aux rôles nécessaires et CREATE public au seul migrator.
   Le rôle P101 est LOGIN, sans privilèges élevés, appartenance ni propriété.
   Les GRANT d'objets listés plus haut seront appliqués par le migrator sous garde.
2. Assembler/revoir le wheelhouse Linux complet et les sources de la liste
   runner.source_manifest + execution.EXECUTION_SOURCES ; construire et vérifier
   l'image uniquement dans une mission autorisée. Fournir son ID réel, le RepoDigest
   PostgreSQL et un lock d'artefacts revu. Embarquer uniquement les clés publiques.
3. Fournir une baseline indépendante **complète** de catalogue PG17.10, incluant
   les GRANT P101 attendus. Ne jamais prendre l'empreinte de la destination observée
   pour l'approuver automatiquement. Le lot ne fournit aucune baseline réelle.
4. Préparer deux configurations administrées locales (hôte et runner), mêmes
   campaign/policy/resources/catalogue_sha256. Seuls registry et artifact_lock
   sont des chemins adaptés à chaque machine. Le registry hôte est un dossier
   local existant de préparation ; aucune réservation n'y est consommée par
   prepare/preflight. Le registry du runner est le chemin exact du volume ci-dessus.
   policy contient trusted_ca_der en base64 et volume_created_at ISO UTC.
   Un trust-store séparé contient les TrustedKey publics (public_key base64,
   valid_from/valid_until ISO UTC, revoked bool). Les chemins sont absolus.
5. Sur l'hôte équipé des dépendances et d'une racine de confiance administrée :

```text
python -B -m p101_postgres_qualification.operator prepare --admin-config <config-hote> --trust-store <trust-store-admin> --operation migrate
```

   Les bindings retournés complètent Intent (authority_id/key_id/approval_id,
   issued_at/expires_at UTC). Faire signer signing_bytes(Intent) extérieurement,
   signature base64. Le fichier initial contient seulement intent et signature.
   Le programme/source doit être identique à celui embarqué dans le runner.

6. Collecter le précontrôle réel depuis l'hôte, après autorisation distincte :

```text
python -B -m p101_postgres_qualification.operator preflight --admin-config <config-hote> --trust-store <trust-store-admin> --request <intent-signe.json> --docker-executable <chemin-absolu-docker> --artifact-sha256 <SHA256-du-lock>
```

   Cette action future effectue seulement les consultations Docker fixes. Son
   unsigned_readiness est une proposition à examiner, jamais une approbation.
   L'autorité vérifie les routes, le registre, les artefacts et les affirmations
   indiquées, puis signe readiness_bytes(receipt) extérieurement. Assembler
   exactement intent, signature, readiness, readiness_signature dans request.json.
   Aucun signataire ou autorisation automatique n'est fourni.

7. L'action `execute-approved` est actuellement bloquée avant toute connexion.
Elle ne pourra être utilisée qu'après fourniture d'un collecteur authentifié
distinct, avec provenance cryptographiquement liée à la campagne, à l'inventaire
et aux observations exactes. Une readiness signée par l'autorité humaine seule
ne satisfait pas ce prérequis. La commande ci-dessous reste refusée jusque-là :

```text
python -B -m p101_postgres_qualification.operator execute-approved --admin-config <config-runner> --request <request.json>
```

   Après levée vérifiable de ce blocage et autorisations humaines, les deux mots de passe (migrator puis observer) sont demandés sans écho, après
   validation des enveloppes/prérequis, sur un terminal permettant la saisie cachée.
   Le repli getpass avec écho est refusé avant toute lecture du secret. Aucun secret
   dans argv ou logs. Réservation
   durable avant socket ; identité, base vide, 14 révisions, quatre GRANT, catalogue,
   acquittement, puis catalogue depuis l'observateur indépendant. Toute divergence
   arrête le parcours. Aucun retry ni reset si claim présent.
8. Après succès explicite de migrate, préparer **une deuxième intention** first-pair
   et une readiness fraîche selon 5–7. Le writer est cette fois le rôle P101,
   puis observer. Une transaction insère les fixtures et la paire ; le rapport
   doit indiquer commit_confirmed, commit_status=confirmed, aucun échec de collecte
   ou fermeture et la clé d'opération. Sur incertitude : arrêter et réconcilier
   manuellement par cette clé, sans rejouer l'écriture.

Les rapports d'exécution sont des métadonnées assainies du parcours ; les propriétés
Offline.real_attested/authenticated restent fausses, elles ne deviennent pas des
certifications globales. Les nouveaux statuts réels n'apparaissent que via l'entrée
du connecteur réel ; les tests utilisent des sockets/trames doubles et ne prouvent
ni PostgreSQL ni sa persistance. Aucun mécanisme B2B de require_real_attestation
n'est détourné ou ouvert. La qualification réelle doit conserver aussi les preuves
de l'opérateur, de l'inventaire et du registre en dehors du rapport assaini.

## Blocages matériels encore effectifs

Pas de collecteur Docker authentifié/provenance vérifiable, campagne/ressources approuvées, RepoDigest PostgreSQL vérifié, image de runner,
wheelhouse/lock Linux revus, baseline catalogue indépendante incluant RLS/politiques, certificats/secrets,
trust-store et signatures humaines, registre initialisé/qualifié ou vérification
des routes fournis à ce lot. Le parcours refuse tant qu'ils manquent. La solution
minimale est de fournir ces éléments précis puis d'autoriser leur provisionnement
et la première exécution ; pas de nouveau noyau ni d'adaptateur TLS supplémentaire.

## Validation du lot

Premier contrôle transport/noyau sur doubles : 28 tests réussis pendant le
développement. Validation ciblée du lot : **138 tests réussis en 196,80 s**, sur
test_real1.py, test_execution.py et test_sql_backend.py. Après durcissement du
repli getpass, seuls les trois tests CLI concernés ont été relancés : **3 réussis
en 6,41 s**, 37 désélectionnés. Le contrôle final du lock d'artefacts a été durci
pour analyser exactement les octets capturés et hachés, sans rouvrir le manifeste :
**5 tests artefacts/CLI réussis en 5,61 s**, 35 désélectionnés, après ce changement.
Pas de nouvelle suite complète.

Les fixtures interdisent les connexions/processus réels. Les tests couvrent
trames étendues/valeurs liées, SCRAM et identité même canal, handshake OpenSSL
MemoryBIO CA/SAN, erreurs/fermetures, approbations et anti-rejeu, relecture
complète, profil de droits séparé, mount de registre exact, refus bind/ports/réseau
étrangers, hashes d'artefacts et chemins CLI fermés par défaut. Les contrôles
Linux/stockage et la reproduction des artefacts sont explicitement doublés dans
les tests positifs du noyau ; leur réalité n'est jamais inférée de ces doubles.

Commandes exécutées depuis le dépôt : Python backend/.venv/Scripts/python.exe -B,
sys.path augmenté dans ce seul processus avec le site-packages du venv OIDC
existant pour cryptography 50.0.2 (lecture seule, aucune installation ni connexion
OIDC), pytest -q -p no:cacheprovider et répertoires temporaires propres au lot.
Les temporaires sont supprimés après les campagnes. Aucun essai sur PostgreSQL
réel, aucune migration ou qualification de durabilité/TLS réseau.

Validation FIX1 : campagne ciblée regroupée sur `test_real1.py` et
`test_sql_backend.py`, **105 tests réussis en 76,11 s**. Elle couvre le refus
des déclarations Docker signées non authentifiées, les provenances absentes ou
divergentes, les configurations/politiques RLS et les rôles de comptage élevés.
Ces essais restent hors ligne et n'attestent ni la provenance d'un moteur Docker,
ni la configuration RLS/vacuité d'une base PostgreSQL réelle.
