# ML 4.2B-1 — Implémentation statique de la persistance PostgreSQL P101

Date : 25 octobre 2026. Statut : implémentation locale à valider, sans commit.
Références conservées : [ML 2](ml-2-p101-anomaly-design.md),
[ML 3](ml-3-p101-anomaly-core.md), [ML 4.1](ml-4.1-p101-persistence-design.md),
[ML 4.2A](ml-4.2a-p101-persistence-contracts.md).

## 1. Référence et limites d'exécution

Départ vérifié : branche `feature/ml-4-p101-persistence`, HEAD
`db045d92233bc192eedf18d75d8d278370ec034a`, index et arbre propres.
Le dépôt est `D:/projets/industrial-predict`. Branche et HEAD conservés ; main
reste à `85d4bf0f1a03bbb841b5c2deebb8f12786c22dca`.

Cette sous-étape ajoute les adaptateurs et les fichiers de migration, **sans les
exécuter sur une base**. Aucune connexion PostgreSQL/HTTP, session SQLAlchemy réelle,
création de base/rôle/table/schéma réel, migration appliquée ou instruction métier
INSERT/UPDATE/DELETE exécutée. Les Table SQLAlchemy définies en mémoire et la
compilation SQL ne créent aucun objet serveur. Aucun endpoint, frontend, package,
entraînement ou joblib ; aucun commit, push, merge ou rebase.

Les seules évaluations de données sont les préparations synthétiques nécessaires
aux tests unitaires, réutilisant la fixture et les fonctions ML 3/ML 4.2A.
Aucune donnée industrielle réelle ou historique DEV n'est lue ou modifiée.
ML 4.2B-2 et ML 5 ne sont pas commencés.

## 2. Fichiers créés, aucun fichier suivi modifié

Dix-sept fichiers nouveaux :

| Fichier | Rôle |
| --- | --- |
| `backend/app/p101_postgres/__init__.py` | Package opt-in sans moteur global |
| `backend/app/p101_postgres/tables.py` | Métadonnées SQLAlchemy Core indépendantes pour les 14 colonnes existantes et le registre |
| `backend/app/p101_postgres/runtime.py` | Configuration explicite, approbation indépendante signée, preuve des fichiers et erreurs typées |
| `backend/app/p101_postgres/session.py` | Factory lazy de sessions sandbox, sans fallback DEV |
| `backend/app/p101_postgres/mapping.py` | Revalidation du dossier, des sources et mapping final Read/details |
| `backend/app/p101_postgres/guard.py` | Requêtes d'identité/catalogue et contrôles fail-closed |
| `backend/app/p101_postgres/repository.py` | Réservation, lecture séparée après conflit, insertion et contraintes différées, sans commit |
| `backend/app/p101_postgres/service.py` | Coordination du lot, commit unique, rollback, retries bornés et résolution |
| `backend/app/p101_postgres/ddl.py` | Corps statiques des quatre fonctions SQL et construction de leurs définitions |
| `backend/p101_migrations/alembic.ini` | Configuration Alembic sandbox sans URL |
| `backend/p101_migrations/env.py` | Entrée de migration exigeant connexion, politique et vérificateur admin explicites |
| `backend/p101_migrations/versions/p101_0001_registry.py` | Migration sandbox p101_0001 et downgrade conservateur, jamais exécutés ici |
| `tests/p101_postgres/conftest.py` | Données et clés fictives, sessions simulées, garde contre accès réel |
| `tests/p101_postgres/test_mapping_runtime.py` | Mapping, approbation, configuration et bornes JSON |
| `tests/p101_postgres/test_guard_repository_migration.py` | Instantanés de catalogue simulés, compilation et lecture AST/textuelle |
| `tests/p101_postgres/test_service_simulated.py` | Machine à états simulée et ordre des opérations |
| `docs/ml-4.2b1-p101-persistence-implementation.md` | Ce rapport |

Les producteurs ML, StatisticalAnomalyDetector, modules ML 3/ML 4.2A, migrations
générales, core.database, configuration DEV, routes et frontend sont inchangés.

### Choix SQLAlchemy

L'adaptateur suit le principe existant d'un repository sans commit, mais n'importe
pas PredictionRepository ni PredictionRecord directement : ces imports passent
par les modèles/core.database et sa configuration globale. Il déclare une Table
Core qualifiée public.prediction_records sur une MetaData autonome et utilise
des instructions paramétrées, dans la Session possédée par le service.
Un test AST compare ses quatorze colonnes aux attributs du modèle existant, sans
importer celui-ci ni créer son moteur. Les deux dates restent timezone=True.
Cette copie de métadonnées devra être maintenue/vérifiée contre le schéma effectif.

## 3. Architecture effectivement implémentée

### 3.1 Revalidation et preuve indépendante

Le service reçoit un PreparationDossier ML 4.2A, mais ne déduit aucun droit de ses
propriétés ou de son seul type Python. `validate_dossier` reconstruit les propositions
logiques et repasse par prepare_batch ; le dossier reproduit doit être identique.
Abstention, lot partiel, proposition altérée ou incohérence de clé/contenu sont refusés
avant l'ouverture de session. Les propositions initiales restent immuables.

Une **ExecutionApproval distincte** est obligatoire : UUID d'approbation, empreinte
du dossier exact, révision du raccordement, expiration, empreinte de politique de
garde et signature HMAC-SHA256. ApprovalVerifier exige une clé indépendante explicite
d'au moins 32 octets, sans clé par défaut, émetteur embarqué ou endpoint de signature.
La signature lie aussi la destination déclarée et le scope p101-write-pair-v1.
Elle est contrôlée avant session et immédiatement avant commit ; une expiration
pendant la préparation SQL provoque un rollback avant commit.

La politique liée couvre hôte/port déclaré, adresse/port internes attendus, rôles,
instance, révisions générale/sandbox et chemin de CA TLS. Elle inclut aussi un
manifeste de **21 fichiers de version**, comprenant adaptateurs, contrats/calcul,
fixture et migration. Les fichiers doivent correspondre aux SHA-256 approuvés,
sans redirection symbolique vers d'autres chemins. Leur lecture n'intervient
qu'après authentification de l'approbation. Cela détecte une modification des octets
depuis l'approbation ; l'association de ces octets à la révision Git est une preuve
que l'émetteur indépendant devra vérifier avant de signer.

La révision de calcul reste celle de ML 3 validée. La révision du raccordement
**n'est pas encore disponible**, car aucun commit de cette étape n'est autorisé.
Aucun SHA documentaire n'est substitué. Les tests utilisent une révision et une
clé explicitement fictives ; leurs signatures ne sont pas des permissions réelles.
L'émetteur, les secrets privés, la procédure de revue de version et les permissions
de production ne sont ni provisionnés ni validés par ces tests.

### 3.2 Factory sandbox et garde effective

SandboxConfig doit être fourni explicitement : destination, adresse/port serveur,
owner/reader distincts du writer, révision de raccordement, manifeste de fichiers,
CA TLS et mot de passe non vide. Le mot de passe est exclu du repr. Aucun fichier
privé n'est créé ou chargé automatiquement.

create_session_factory ne se connecte pas lors de sa construction et n'est pas
appelée sur un moteur réel pendant les tests. Elle configure : PostgreSQL+psycopg,
READ COMMITTED, autoflush=False, expire_on_commit=False, paramètres SQL masqués,
TLS verify-full, CA explicite, UTF-8, search_path pg_catalog, UTC et délais bornés.
La sérialisation JSON est compacte, UTF-8 et refuse les nombres non finis.
DATABASE_URL et `.env` ne sont jamais consultés ; la présence de variables PG*
libpq provoque un refus plutôt qu'un héritage implicite d'environnement/service/passfile.

Chaque transaction commence avant les requêtes de garde. check_destination ne
contient que des lectures de catalogue et refuse une valeur absente/inattendue :

- adresse/port réels du serveur, base, session_user/current_user, TLS actif ;
- UUID/purpose du marqueur, owner/writer/reader attendus, provisioning_closed ;
- révisions installées 09ac8101e9fe et p101_0001, isolation READ COMMITTED ;
- absence de privilèges superuser/BYPASSRLS/CREATEDB/CREATEROLE/replication,
  de memberships, de propriété des tables, de CREATE de schéma ou de TEMP ;
- SELECT nécessaires et INSERT limité aux deux tables, absence de mutations des
  sources/recommandations et d'UPDATE/DELETE/TRUNCATE de l'historique/marqueur,
  y compris vérification des privilèges d'écriture de colonnes ;
- fonctions présentes sans surcharge, propriétaire attendu, SECURITY DEFINER,
  search_path fixe, empreinte exacte du corps, aucun EXECUTE public ; seul le
  helper de verrouillage est directement exécutable par le writer ;
- contraintes UNIQUE immédiates, FK différée validée vers la bonne table avec
  NO ACTION, checks présents ; triggers actifs sur les bonnes tables/fonctions,
  liens inverses différables initialement différés.

Le port publié client peut différer du port interne de PostgreSQL : les contrôles
ne les confondent pas. Une erreur de catalogue, marqueur absent ou droits excessifs
fait échouer la garde avant séquence/réservation/INSERT. Ces requêtes n'ont pas été
exécutées et leurs résultats réels restent à vérifier sur le sandbox autorisé.

### 3.3 Verrouillage des douze sources et mapping

Le helper SQL lock_sources est préparé avec SECURITY DEFINER et search_path fixé
à pg_catalog ; il vérifie session_user contre le writer du marqueur fermé et ne
prend aucun paramètre SQL arbitraire. Il acquiert un verrou advisory partagé puis
des verrous SHARE sur les quatre parents synthétiques exacts et les mesures du
capteur ; exactement douze mesures sont exigées. Le provisionnement futur devra
prendre le verrou advisory exclusif correspondant et être arrêté en exploitation.
Les rôles d'exécution n'ont pas de droits d'insertion/mutation des sources.

validate_sources contrôle le snapshot verrouillé : codes/parents, type pump et
temperature, unité °C, nom synthétique, ids INTEGER positifs non booléens, unicité
des mesures et instants, qualité good, finitude et égalité exacte des valeurs et
timestamps au manifeste. Les métadonnées available_at/synthetic/fixture_id viennent
du manifeste autorisé, pas d'une colonne SQL imaginaire ou d'un historique réel.

map_prediction construit les quatorze champs Read avec les ids fournis par ce
mapping et les vrais ids alloués par la séquence en exploitation future ; aucun
id SQL n'est inventé par l'adaptateur. Dans les tests, ces ids sont des données
fictives de simulation, sans rapport avec DEV.

Les détails finaux ferment le schéma attendu, remplacent les identités logiques
par les ids/codes aux emplacements ML 2, enrichissent les dix références et la cible,
gardent la vraie clé logique et la révision de calcul, sans revision_status provisoire.
Les limites de 6 000 octets UTF-8, chaînes/profondeur, finitude, score/alerte, dates,
niveau/horizon null et rattachements sont contrôlées avant commit. created_at provient
d'une lecture clock_timestamp avec fuseau et doit être postérieur à prepared_at/cutoff.
Un retry valide les détails stockés tout en conservant run_id/prepared_at/created_at
et id de la première écriture, sans les remplacer par ceux de la tentative.

## 4. Transaction, idempotence et issues

P101PersistenceService exige une session fraîche, sans transaction ou modifications
en attente. Il n'appelle ni PredictionService.create ni persist_*, et ne déclenche
aucune recommandation. Le flux implémenté est :

1. Revalidation du dossier et de l'approbation indépendante, avant session.
2. Transaction unique, garde effective et snapshot des douze sources verrouillées.
3. Date réelle d'écriture commune et réservation des deux clés en ordre stable.
4. Allocation par nextval de la véritable séquence obtenue avec pg_get_serial_sequence ;
   registre réservé avec prediction_id réel et FK différée, avant les prédictions.
5. Deux réservations nouvelles → deux INSERT paramétrés ; deux existantes → lecture
   et validation des anciennes lignes ; mélange existant/nouveau → conflit et rollback.
6. Validation des quatorze champs/détails, contrôle explicite des contraintes
   différées nommées, matérialisation JSON du reçu avant commit.
7. Dernière vérification de l'approbation, puis **un seul commit** pour le lot.

Le repository traite uniquement le conflit sur idempotency_key par DO NOTHING,
sans UPDATE. Après conflit, il utilise une instruction SELECT distincte pour une
nouvelle visibilité READ COMMITTED ; il compare les digests **et les octets** de
clé/contenu, puis les anciennes prédictions et le mapping actuel. Une divergence
n'est jamais présentée comme un retry réussi. Les séquences peuvent avancer même
lors d'un retry/rollback ; les trous d'ids ne sont pas des lignes orphelines.

Toute erreur avant commit appelle rollback sur tout le lot. Un deadlock 40P01 ou
une erreur de sérialisation 40001 autorise au plus deux nouvelles tentatives,
chacune avec nouvelle session, nouvelle garde et nouvelle validation. Aucun retry
automatique des conflits métier. Un rollback qui échoue n'est pas déclaré confirmé.

BatchReceipt expose created, existing ou commit_unknown ; ses lignes sont conservées
en JSON immutable et retournées comme copies. Lors d'une erreur de commit, seules
les violations d'intégrité et les états de rollback identifiés sont traités comme
échecs confirmés. Une déconnexion, absence de SQLSTATE ou 40003
statement_completion_unknown donne commit_unknown, sans prétendre annuler une
transaction éventuellement déjà validée. Aucun refresh ORM après commit n'est requis.

resolve utilise une nouvelle transaction gardée, sans allocation/réservation/INSERT :
deux clés cohérentes donnent existing, zéro clé donne not_observed (pas « rollback
prouvé »), une seule clé donne conflit, une indisponibilité donne resolution_unavailable.
La résolution ne réinsère jamais automatiquement. Une tentative ultérieure exige
toujours son approbation valide et les mêmes protections uniques.

## 5. Migration dédiée : fichiers préparés, non appliqués

Historique séparé `backend/p101_migrations`, révision p101_0001 sans parent dans
cette branche sandbox ; version_table p101_pilot.alembic_version. La révision
générale préalable reste 09ac8101e9fe ; les migrations générales ne sont pas modifiées.

env.py refuse le mode offline et toute configuration sans connexion dédiée,
SandboxConfig et vérificateur admin indépendant fournis explicitement. Il ne crée
aucun moteur et ne lit aucune URL implicite. Avant DDL, il prévoit des contrôles
d'adresse/port/base, owner effectif, TLS et révision générale, puis exige une
approbation de migration distincte. L'intégration de ce vérificateur admin avec une
autorité réelle reste un prérequis de provisionnement ; aucun callback permissif
ou booléen issu du dossier n'est fourni par défaut.

La migration définit :

- schéma/version dédiés et table environment_guard singleton, sans insertion du
  marqueur ou création de fixtures ; service refusé tant que le bootstrap distinct
  n'a pas fourni le marqueur valide et fermé ;
- idempotency_records : PK UNIQUE immédiate sur clé SHA-256, contenu et octets
  canoniques bornés, prediction_id NOT NULL/UNIQUE, FK NO ACTION DEFERRABLE INITIALLY
  DEFERRED, date de première écriture ;
- quatre fonctions à empreintes contrôlées : canonical_value, enforce_shape,
  enforce_link et lock_sources ;
- trigger de forme/immutabilité du rôle pilote et deux constraint triggers inverses
  différés entre registre et PredictionRecord ; comparaison au contenu canonique ;
- révocation des privilèges publics sur les objets sandbox/fonctions, grants limités
  aux rôles dédiés existants, usage de la séquence réellement attachée ;
- downgrade refusant des registres ou prédictions P101 présents ; s'il est autorisé
  sur un espace vide, révocation des capacités d'écriture avant retrait des triggers,
  suppression des seuls objets sandbox et conservation du schéma/version Alembic.

Ces corps PL/pgSQL, droits, casts JSON et commandes Alembic sont **du code source
non validé par PostgreSQL** à ce stade. Les tests AST/textuels et compilations
SQLAlchemy n'en prouvent ni la syntaxe serveur complète ni les effets réels.
Ne pas appliquer ces fichiers au DEV permanent ou les présenter comme une migration
déjà installée.

## 6. Tests exécutés : uniquement hors base

Commande depuis la racine :

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
backend/.venv/Scripts/python.exe -m pytest tests/p101_postgres -q -p no:cacheprovider
```

Dernier résultat : **70 tests réussis en 3,27 s**, aucun échec. Les passes de revue
précédentes ont réussi avec 65 puis 69 puis 70 tests ; les relances ciblées étaient
justifiées par l'ajout des contrôles de politique signée/fichiers, du traitement
40003, des vérifications de compatibilité et du downgrade. Aucune suite backend
complète, test PostgreSQL, migration ou commande de build n'a été exécuté.

Les tests bloquent Engine.connect, Connection.execute et les appels réels de
Session.execute/flush/commit, ainsi que les connexions et résolutions réseau.
La factory est testée avec un constructeur de moteur espion, jamais un moteur réel.
Les objets de session/repository simulés ne dérivent pas d'une connexion serveur.
Les fichiers de migration sont lus via AST/texte ; leurs fonctions upgrade/downgrade
et l'entrée env.py ne sont pas appelées.

| Validation unitaire/statique | Preuve obtenue |
| --- | --- |
| Dossier et lot | Reconstruction du dossier exact ; lot incomplet/objet d'autorisation inadéquat refusé avant session |
| Autorisation indépendante | HMAC, expiration, dossier/révision/politique modifiés et mauvaise empreinte des fichiers refusés ; clés de test fictives uniquement |
| Configuration | Construction explicite sans DATABASE_URL, TLS verify-full, refus PG*, mot de passe masqué ; aucune connexion |
| Garde effective | Instantanés fabriqués : mauvaise identité/rôle/TLS/révision/privilèges, fonction modifiée/publique, contrainte/triggers manquants ou désactivés refusés |
| Sources et mapping | Douze mesures synthétiques, parents/unité/qualité/valeur/temps/doublon/id invalides refusés ; quatorze champs et détails enrichis contrôlés |
| Compatibilité | Attributs du modèle existant lus en AST comparés aux quatorze colonnes Core et dates avec fuseau |
| Réservation | Compilation PostgreSQL de ON CONFLICT DO NOTHING/RETURNING ; SELECT simulé séparé après conflit |
| Retry | Repository simulé conservant id/date/run originels ; contenu divergent refusé |
| Coordination | Ordre garde → réservations → deux insertions → contraintes → commit unique ; rollback global simulé sur plusieurs points d'erreur et lot partiel |
| Commit incertain | 08006/40003/SQLSTATE absent → commit_unknown ; violation confirmée → rollback ; retries 40P01 bornés et re-gardés |
| Résolution | Simulations existing/not_observed sans nextval, réservation, insertion ou commit d'écriture |
| Migration | Métadonnées compilées, portée AST/texte, FK différée, UNIQUE, protections inverses, search_path et refus de downgrade avec données |

**Les mocks ne prouvent ni atomicité PostgreSQL, ni rollback durable, ni concurrence,
ni commit réel.** Aucun des I01–I12 PostgreSQL n'est déclaré réussi dans cette étape.

## 7. Ce qui reste non vérifié et prérequis ML 4.2B-2

Avant toute connexion future, obtenir une autorisation distincte pour :

1. Un cluster/base/volume sandbox distincts, leurs ports publié/interne, TLS/CA,
   UUID d'instance et configuration privée sous ACL, sans identifiants DEV ;
2. Trois rôles dédiés non hérités : owner/migrateur, writer limité, reader GET ;
   supprimer les capacités PUBLIC/colonne/TEMP incompatibles et vérifier l'absence
   de privilèges sur DEV sans utiliser DEV comme cible d'essai ;
3. L'approbation admin authentifiée des migrations, leur application contrôlée au
   seul sandbox, le bootstrap du marqueur et des douze fixtures immuables ;
4. Le commit de version revu, les preuves de révision/fichiers, la distribution
   privée d'une clé d'approbation indépendante et la première permission signée
   pour ce dossier précis ; ne jamais réutiliser les clés/identifiants fictifs des tests ;
5. Les tests PostgreSQL I01–I12 : vraies connexions indépendantes, migrations réelles,
   grants, verrous SHARE/advisory, races de réservation, snapshots READ COMMITTED,
   contraintes/triggers différés, types/date/JSON, rollbacks et coupures de commit ;
6. Une instance dédiée de consultation GET et les preuves avant/après de toutes
   les tables ; aucun POST voisin de recommandations/RUL/Health Score.

Le SQL de catalogue, l'ownership, les privilèges exacts de fonctions/colonnes,
les noms de contraintes Alembic, la visibilité après conflit et les fonctions JSON
peuvent nécessiter un ajustement motivé par les futurs tests réels. La garde reste
fail-closed si un fait attendu est absent ; ne pas la désactiver pour contourner
une erreur de provisionnement. Le provisionneur privilégié doit respecter le verrou
advisory exclusif et rester arrêté après fermeture du marqueur : des verrous SHARE
seuls ne bloquent pas l'insertion de nouvelles mesures par un administrateur.

Le contrôle HMAC authentifie la possession d'une clé de confiance et les octets
approuvés ; il ne crée pas l'autorité humaine ni la preuve Git à leur origine.
La clé privée et le fichier CA doivent être protégés ; un propriétaire SQL ou un
administrateur local reste une autorité privilégiée, pas un adversaire rendu
inoffensif par ce pilote. Aucun déploiement SaaS n'est certifié par cette étape.

## 8. Réserves B-PRE-01 à B-PRE-11

| Réserve | État et limite après ML 4.2B-1 |
| --- | --- |
| B-PRE-01 | Ouverte : garde et permission indépendante préparées, aucune preuve sur destination réelle ni autorisation SaaS multi-tenant |
| B-PRE-02 | Ouverte globalement : validation P101 binaire/finitude limitée à cet adaptateur, producteurs génériques inchangés |
| B-PRE-03 | Ouverte backend : UTC/cutoff/mapping testés hors base, timestamptz réel et routes non durcies |
| B-PRE-04 | Ouverte : contrôle de sources préparé ; verrous/rattachements SQL non exercés |
| B-PRE-05 | Ouverte globalement : détails fermés/bornés en mémoire, sérialisation/relecture serveur non prouvées |
| B-PRE-06 | Ouverte : NO ACTION, liens inverses et downgrade conservateur écrits mais jamais installés ; cascades générales inchangées |
| B-PRE-07 | Ouverte : aucune garantie de snapshot/pagination ou mesure de charge |
| B-PRE-08 | Ouverte : évite le chemin à commit interne ; RUL/joblib existants inchangés ; état réel des transactions du pilote non prouvé |
| B-PRE-09 | Ouverte : aucune alimentation d'historique effectuée, aucune orchestration générale |
| B-PRE-10 | Ouverte : preuve de fichiers et révisions préparée, aucune version d'exécution/provenance serveur réellement validée |
| B-PRE-11 | Ouverte : aucune nouvelle route détail/latest ; GET historique n'a pas été appelé |

## 9. État Git et livraison

Branche `feature/ml-4-p101-persistence`, HEAD inchangé
`db045d92233bc192eedf18d75d8d278370ec034a`, index vide. Les dix-sept fichiers de
la section 2 sont nouveaux et non indexés ; aucun fichier suivi préexistant modifié.
Contrôle final du périmètre conforme : 17 fichiers nouveaux, aucun changement suivi
et index vide. `git diff --check` et le contrôle `git diff --no-index --check` de
chaque fichier nouveau sont sans erreur d'espacement. La recherche de motifs de
secrets/DSN et la lecture des valeurs de configuration n'ont identifié aucun secret
réel ni identifiant DEV ; les valeurs des tests sont explicitement fictives.
Aucune indexation, aucun commit ni test supplémentaire après la rédaction du rapport.

**Bilan soumis à validation technique. ML 4.2B-2 et ML 5 non commencés. Aucune
infrastructure ou première persistance réelle n'est autorisée implicitement.**
