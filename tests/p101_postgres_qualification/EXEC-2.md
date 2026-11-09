# P101-DEV-3D-EXEC-2 — commandes SQL et observateur, hors ligne

Base locale contrôlée : branche `feature/auth-b2b-identity-access`, HEAD
`542ba381c55793f3b9de86a33c18b96ebc9ec4af` (EXEC-1 publié selon le contexte).
Dépôt et index propres avant développement. Aucun contrôle distant dans ce lot.

## Capacités implémentées et API

`sql_backend.PostgresBackend` implémente les méthodes du backend utilisées par
`execution.CampaignExecutor`. Il n'ajoute ni orchestrateur, ni autorité, ni CLI.
`run_simulated` admet désormais deux types concrets : SimulatedBackend et ce
backend SQL, ce dernier alimenté **exclusivement** par OfflineChannelPool et
ScriptedConnection. Aucun connecteur utilisateur, sous-type ou callback de
connexion n'est accepté. Les doubles répondent à des couples SQL/paramètres
exacts, à partir de données ; ils ne délèguent jamais à psycopg.

Le noyau EXEC-1 conserve l'approbation Ed25519, les contrôles de campagne,
inventaire et sources, la réservation préalable anti-rejeu et l'unique COMMIT.
L'empreinte du programme signé inclut les nouveaux modules et le manifeste
exec2-dependencies.json. Les inventaires fournis restent des déclarations
injectées : aucune attestation Docker n'est produite ici.

Les commandes DB-API sont concrètes, avec paramètres séparés pour les données.
Le DDL natif issu exclusivement du compilateur des 14 révisions est envoyé sans
argument de paramètres : les `%ROWTYPE` ne sont jamais réinterpolés. Les révisions,
leur ordre et leur versionnement sont contrôlés à chaque appel. Les révisions
publiées, les gardes Alembic et le compilateur sont inchangés.

La session writer exige autocommit initial actif et état IDLE, puis ouvre
explicitement SERIALIZABLE READ WRITE. L'observateur ouvre REPEATABLE READ READ
ONLY ; les modes et PID sont relus dans PostgreSQL via une requête fixe.
Les rôles doivent également avoir default_transaction_read_only cohérent.
Timeouts locaux (statement 5 s, lock 1 s) et fuseau UTC sont imposés. La syntaxe
suit [BEGIN PostgreSQL 17](https://www.postgresql.org/docs/17/sql-begin.html).

L'installation prévue vérifie la base vide avec EMPTY_SQL, émet version_create,
les 14 révisions et leur bookkeeping dans la même transaction externe, puis
collecte le catalogue avant et après acquittement. Colonnes/types/defaults,
contraintes, index, fonctions, triggers, séquences, propriétaires de relations
public et ACL explicites relations/schéma/base/fonctions sont comparés à une
empreinte **indépendante**, jamais calculée automatiquement depuis la destination
à approuver. Le catalogue des tests est synthétique, pas une baseline approuvée.
Ce profil ne constitue pas encore un audit des privilèges effectifs : adhésions
de rôles, default ACL, propriétés de rôles et propriétaires des autres objets
doivent entrer dans la qualification opérationnelle avant toute activation.

Blocage de droits précis : evidence._postgres_adapter B2B attend pour runtime
business_write=false et sequence_usage=false. Ce profil publié est conservé.
Il ne peut pas exécuter les INSERT/nextval et verrous sources de first-pair.
Un profil P101 de qualification distinct, explicitement approuvé et collecté,
reste à concevoir sans élargir implicitement le profil B2B existant. Les rôles
injectés des doubles ne démontrent pas ces droits ; aucun GRANT n'est exécuté.

## Transaction P101 et relecture

L'exécution first-pair verrouille les cinq tables sources en SHARE ROW EXCLUSIVE,
refuse toute donnée métier existante, résout les 15 INSERT synthétiques par
RETURNING, puis relit chaque ligne source via un SELECT fixe. Le contenu complet,
identifiants et horodatages sont comparés, sans reconstruire les observations.
Les seuls écarts de représentation admis sont JSON datetime et valeur float.
L'évaluateur P101 et les dix références plus cible viennent de scenario.py,
inchangé ; les entrées/sorties ne sont pas recalculées par un autre modèle.

La préallocation nextval précède le journal, puis la prédiction réciproque.
SET CONSTRAINTS ALL IMMEDIATE vérifie les contraintes différées avant le COMMIT.
La paire est relue sur le writer avant commit ; aucune donnée persistante n'est
fabriquée à partir de stage_pair. Chaque INSERT exige le nombre de lignes attendu.
L'API execute refuse toute autre commande ou paramètre et tout changement d'ordre.
La méthode privée _call est une primitive interne, pas une API de SQL libre.

`QualificationObserver.verify(writer, reader, operation)` vérifie la lecture seule,
les connexions physiques, sockets, handles et PID distincts tout en gardant le
writer ouvert ; CA/SAN et identité de chaque canal sont revérifiés. Deux UUID
ou deux objets Python seuls ne suffisent pas. Le SELECT LEFT JOIN existant expose
aussi une association manquante. Le lecteur compare toutes les colonnes du
journal et de la prédiction, les IDs exacts obtenus par le writer, leurs références
réciproques, les empreintes, résultats et texte canonique. Un comptage seul n'est
jamais une preuve. Toutes ces observations restent injectées dans ce lot.

## Erreurs, COMMIT et preuves

La session passe en état committing avant l'envoi unique. Un COMMIT confirmé exige
le tag de commande COMMIT et le retour IDLE du pilote. Un tag ROLLBACK ne produit
jamais un succès. Un rejet SQLSTATE classe 23 ou 40 avec canal sain et retour
IDLE est classé rejected ; une rupture, un état inconnu ou une autre erreur à
cette frontière reste uncertain. Les états suivent la nomenclature
[libpq](https://www.postgresql.org/docs/17/libpq-status.html).
Pas de rollback présenté comme résolution d'un COMMIT incertain, ni de retry.
Les erreurs avant COMMIT permettent un rollback contrôlé ; les connexions sont
fermées une seule fois, même en cas d'échec de close. Une erreur de nettoyage
n'efface pas un acquittement déjà obtenu.

ExecutionReport ajoute operation_key, empreinte stable nécessaire à une future
réconciliation explicite par relecture. La réservation reste consommée, quelle
que soit l'issue ; aucun nouveau signataire/UUID ne débloque le rejeu. Aucun
workflow réel de reprise ou de réconciliation automatique n'est activé.
Les rapports conservent les statuts simulated_*, les indicateurs Offline faux
et un digest assaini ; SQLSTATE est filtré à cinq caractères dans SqlFailure.
Les diagnostics du pilote ne sont pas chaînés aux exceptions exposées. Aucun
DSN, mot de passe, clé privée ou payload canonique n'entre dans le rapport.
La trace SQL brute de ScriptedConnection sert uniquement aux tests synthétiques,
et ne doit pas devenir le journal d'une future campagne réelle.

## Blocage TLS précis et garanties

INFRA-3 reste inchangé. Son transport PostgreSQL v3 capture le DER serveur sur
la SSLSocket qui transporte ses requêtes SQL, vérifie CA directe et SAN, puis
SCRAM-SHA-256 avec signature serveur. Son API est limitée aux métadonnées en
lecture seule ; elle ne sait envoyer ni ces INSERT paramétrés, ni ces transactions,
ni des résultats JSON. Elle ne peut pas devenir le writer par simple raccordement.

L'inspection locale de psycopg/psycopg-binary 3.3.4 confirme socket et ssl_in_use
sur PGconn, sans API exposant le certificat DER du pair sur ce canal. Le descripteur
libpq appartient déjà à son moteur TLS : envelopper ce descripteur dans une seconde
SSLSocket n'extrait pas ce certificat. Ni verify-full déclaré, ni pg_stat_ssl,
ni certificat relu sur une connexion de sondage ne satisfont TlsBinding.

`PsycopgBoundConnector.open` refuse donc inconditionnellement, avant de lire ses
arguments. `run_live`, le CLI et les autres portes fermées restent désactivés.
Il n'existe aucun DSN par défaut ou ouverture implicite. binding réutilise les
validations CA/SAN et TlsBinding existantes sur le **même canal double** que les
curseurs ; les booléens TLS/SCRAM du double ne prouvent aucune négociation réelle.

Adaptation minimale à qualifier ultérieurement : un pont natif lié au même
libpq/OpenSSL capable d'extraire le DER depuis le handle TLS du PGconn utilisé,
ou une extension revue du transport INFRA-3 couvrant le protocole writer et JSON.
Aucun pont ctypes, seconde connexion ou assertion non démontrée n'est livré.
Les limites INFRA-3 (CA directe, mots de passe ASCII, absence de channel binding)
restent inchangées ; aucune qualification TLS réelle n'est revendiquée.

## Dépendances et prérequis opérationnels

Références supplémentaires exactes : psycopg 3.3.4 et psycopg-binary 3.3.4.
Les commandes n'utilisent ici que TransactionStatus ; aucun connect() n'est appelé.
Le rendu reste SQLAlchemy 2.0.52/Alembic 1.19.1, l'autorisation cryptography 50.0.2
et l'évaluateur conserve les dépendances RUNNER-1. Les versions seules ne prouvent
ni le libpq/OpenSSL embarqué Linux ni la reproductibilité : base par digest,
wheelhouse linux/amd64 complet et hashes transitifs restent manquants. Aucun build
ou téléchargement n'est effectué ; voir les trois manifestes infra.

Avant campagne réelle : transport writer avec DER même canal qualifié, baseline
catalogue/privilèges revue indépendamment, inventaire frais d'une nouvelle campagne
et de sa destination isolée, verrouillage/durabilité/ACL du registre anti-rejeu
qualifiés, autorité et consentement humain authentifiés séparément, artefacts
reproductibles validés. Ces prérequis ne suffisent pas à ouvrir automatiquement
run_live : son activation demanderait un lot distinct et une nouvelle revue.

## Validation hors ligne

Une seule campagne ciblée exécutée : **99 tests réussis en 132,62 s**, couvrant
test_sql_backend.py et la régression du noyau modifié test_execution.py. Les
connexions, processus, moteurs SQLAlchemy et commandes Alembic réelles sont
interdits par les fixtures. Transitions, SQL fixé/refusé, erreurs, destination,
autorisation, COMMIT incertain sans retry et comparaisons complètes sont couverts.
Aucun test ne qualifie un serveur, les contraintes réelles, le TLS réel ou la
persistance après redémarrage.

Commande unique depuis la racine du dépôt (PowerShell) :

```powershell
& backend/.venv/Scripts/python.exe -B -c "import sys; sys.path.append(r'D:/projets/industrial-predict-oidc-m1b-venv/Lib/site-packages'); import pytest; raise SystemExit(pytest.main(['tests/p101_postgres_qualification/test_sql_backend.py','tests/p101_postgres_qualification/test_execution.py','-q','-p','no:cacheprovider','--basetemp=D:/projets/industrial-predict/.pytest-exec2-offline']))"
```

Python et dépendances locales existants ; cryptography 50.0.2 est lu depuis
l'autre venv existant, via sys.path limité à ce processus. Aucune installation ou
modification de ce venv, aucune connexion OIDC. Les réservations temporaires des
tests sont supprimées après la campagne. Aucun second lancement.
