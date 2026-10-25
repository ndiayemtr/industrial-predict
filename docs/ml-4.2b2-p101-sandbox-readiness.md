# ML 4.2B-2.0 — Audit local de préparation du sandbox PostgreSQL P101

Date : 25 octobre 2026. Statut : documentaire, soumis à validation.

## 1. Conclusion et périmètre

Les clients Docker/Compose, Python et les dépendances Python nécessaires sont
présents. PostgreSQL 18.4 est également installé localement, hors du PATH.
**Le provisionnement n'est pas encore prêt à être exécuté** : image immuable,
transport TLS, amorçage du schéma général sans réglages DEV, autorisation admin,
bootstrap des rôles/marqueur/fixture et identité réseau restent à préparer.

Référence vérifiée dans `D:/projets/industrial-predict` : branche
`feature/ml-4-p101-persistence`, HEAD
`bf28bc6c7d9d6a030ba8023b4c09588d126918f8`, arbre propre et index vide au départ.
Ce rapport est le seul fichier créé. Aucun code ni configuration modifié.

Audit par lecture de fichiers et métadonnées locales, commandes de version et
inventaire local uniquement. Aucune connexion PostgreSQL ou HTTP, aucun démarrage
de serveur/service/conteneur, aucune ressource créée, aucune migration invoquée,
aucun test ni calcul ML. Les exécutables PostgreSQL ont uniquement reçu
`--version` ; `initdb` n'a donc initialisé aucun cluster. Aucun secret privé lu
dans une configuration externe ni reproduit ici. Les lignes de connexion/secrets
des fichiers projet examinés ont été occultées dans les sorties de lecture.

Références : [ML 2](ml-2-p101-anomaly-design.md),
[ML 3](ml-3-p101-anomaly-core.md),
[ML 4.1](ml-4.1-p101-persistence-design.md),
[ML 4.2A](ml-4.2a-p101-persistence-contracts.md),
[ML 4.2B-1](ml-4.2b1-p101-persistence-implementation.md).

## 2. Outils effectivement constatés

| Outil | Constat local et preuve | Limite |
| --- | --- | --- |
| Docker CLI | `docker --version` : 29.6.1, build `8900f1d` ; exécutable dans `C:/Program Files/Docker/Docker/resources/bin` | Aucun appel au moteur, état du daemon et images non vérifiés |
| Compose | `docker compose version` et `docker-compose --version` : v5.3.0 | Présence du client seulement ; aucun projet lancé |
| Docker Desktop | Métadonnées de `Docker Desktop.exe` : 4.82.0.233772 | Ne prouve ni disponibilité du moteur Linux/WSL ni fonctionnement réseau |
| PostgreSQL | `psql`, `postgres`, `pg_ctl`, `initdb`, `pg_config`, `pg_dump` : 18.4, chacun avec sortie de version réussie | Hors PATH ; fichiers sous `C:/Program Files/PostgreSQL/18/bin` ; aucun serveur inspecté/contacté |
| Python global et venv backend | `--version` : 3.12.10 pour les deux | Utiliser explicitement `backend/.venv/Scripts/python.exe` |
| Lanceur `py` | Présent mais `py --version` répond « No installed Python found! » | Ne pas en faire un prérequis d'exécution |
| SQLAlchemy / Alembic | Métadonnées locales `pip show` : 2.0.52 / 1.19.1 | Aucun import de l'environnement Alembic ni commande de migration |
| psycopg / psycopg-binary | 3.3.4 / 3.3.4 ; lecture de version `pq.version()` : 180003 (libpq 18.3), implémentation `binary` | Import du pilote pour version seulement, aucun `connect` |
| pytest | Métadonnées locales : 9.1.1 | Aucun test exécuté dans cette étape |
| TLS Python | `ssl.OPENSSL_VERSION` : OpenSSL 3.0.16, 11 Feb 2025 | Version du module Python, distincte de la pile TLS libpq et du futur serveur |
| OpenSSL CLI | Absent du PATH ; fichier Git `C:/Program Files/Git/usr/bin/openssl.exe` présent, métadonnées 3.5.7 | `version` échoue avec code -1073741502 ; aucune version d'exécution ni capacité de génération PEM établie |
| PKI Windows | Commandes `New-SelfSignedCertificate`, `Export-Certificate` présentes, module PKI | Aucune commande de création/export invoquée ; chaîne CA, SAN et export PEM restent à concevoir |

`Get-NetTCPConnection` n'a pas fourni d'inventaire exploitable dans ce contexte.
**Aucun port n'est déclaré libre ou réservé.** Aucune variable d'environnement
dont le nom commence par `PG`, ni `DATABASE_URL`, n'a été listée dans le processus
d'audit ; cette observation devra être répétée dans le futur processus opérationnel.
Les fichiers `.env`, profils libpq, secrets Docker et certificats privés n'ont pas
été inventoriés ou ouverts.

Aucun téléchargement ni interrogation de registre d'images n'a été effectué.
Les versions de serveur souhaitées dans les fichiers Compose sont des déclarations,
pas des observations de serveurs ou d'images présents.

## 3. Lecture du projet et écarts de préparation

| Fichiers examinés | Constat | Conséquence P101 |
| --- | --- | --- |
| `docker-compose.yml` | PostgreSQL déclaré en version majeure 17, volume nommé, publication hôte 5433, compte de connexion configuré | Configuration existante exclue du sandbox ; aucune reprise de volume, compte ou configuration |
| `infra/development/compose.yaml` | Environnement DEV distinct, image 17.10 explicitement attendue, volume externe, publication loopback 5434 | Ne pas réutiliser ce projet, son volume, ses secrets ou ses lanceurs |
| `infra/development/manage.py`, `seed.py`, README | Gestion DEV avec migrations, réglages applicatifs et contrôles HTTP ; fixture DEV propre | Aucun lancement ni import ; ce n'est pas un provisionneur P101 |
| `backend/app/core/config.py`, `core/database.py` | Settings recharge `.env` ; moteur global construit depuis la configuration applicative | Éviter ces imports dans les outils sandbox dédiés |
| `backend/alembic.ini`, `backend/migrations/env.py` | L'environnement général remplace l'URL par `settings.database_url`, importe Base/modèles et crée son moteur | Changer seulement l'URL Alembic ou passer une connexion dans `attributes` ne suffit pas : cet env ne consomme pas cette connexion |
| Neuf révisions `backend/migrations/versions/*.py` | Chaîne depuis `0468ed5be8f1` jusqu'à `09ac8101e9fe`, dont PredictionRecord `d6ec01cf13b6` ; 14 colonnes, JSON, dates prédictives avec fuseau | Schéma général obligatoire sur base vide, avant la migration P101 ; ne pas copier un dump DEV |
| `backend/p101_migrations/alembic.ini`, `env.py`, `versions/p101_0001_registry.py` | Historique indépendant, schéma/version dédiés, connexion/politique/vérificateur admin injectés obligatoires | Pas de commande CLI autonome prête à utiliser ; pas de marqueur ou fixture provisionnés par la migration |
| `backend/app/p101_postgres/*.py` | Factory explicite, garde effective, mapping, registre et service du lot | Interfaces présentes ; aucune garantie serveur acquise par lecture statique |
| Contrats ML 3/4.2A et fixture P101 | Douze observations synthétiques, deux cibles exactes, provenance et empreintes contractuelles | Réutiliser cette seule source, sans seed DEV ni ids SQL prédéfinis |
| `.gitignore` | Ignore `.env` et variantes, mais pas toutes les extensions possibles de clé/certificat/configuration | Conserver tous les secrets et fichiers privés hors dépôt ; l'ignore seul ne protège pas les clés |

Le choix recommandé reste un **nouveau cluster conteneurisé PostgreSQL 17**, avec
version mineure et digest à approuver avant création. La référence 17.10 du DEV
peut orienter la compatibilité, sans prouver sa disponibilité ni imposer la
réutilisation d'une image existante. PostgreSQL natif 18.4 constitue une alternative
installée, pas une équivalence validée : autre majeur et isolation plus dépendante
de l'administration Windows. Aucun serveur natif ne doit être démarré implicitement.

## 4. Architecture sandbox proposée, aucune ressource créée

- Nouveau projet Compose proposé `industrial-predict-p101-sandbox`, conteneur,
  volume de données et réseau portant exclusivement ce préfixe. Aucun volume
  externe partagé, montage de données DEV, réseau existant DEV ou socket Docker
  dans le conteneur. Ne pas combiner les fichiers Compose DEV par override.
- Image PostgreSQL épinglée par version et digest, UTF-8, fuseau UTC ; cluster
  initialisé à neuf. Choisir explicitement PGDATA/montage selon l'image retenue.
  Aucun dump, restauration, réplication, FDW ou extension d'accès à DEV.
- Réseau bridge dédié, option `internal` à valider avec Docker Desktop ; aucun
  rattachement aux réseaux DEV. Publication proposée `127.0.0.1:55432:5432`,
  seulement après vérification des ports/règles Windows. Aucun accès réseau large.
  Un réseau Docker isolé ne constitue pas à lui seul un pare-feu contre un admin
  hôte : documenter aussi les routes, règles d'accès et l'absence de secrets DEV.
- Client Python sur l'hôte, destination déclarée loopback IPv4, port publié
  approuvé. `server_address` désigne séparément l'adresse effectivement vue par
  PostgreSQL dans le conteneur ; `server_port` sera normalement 5432, pas 55432.
  Adresse interne stable et subnet non conflictuel à déterminer avant démarrage ;
  ne pas apprendre puis accepter silencieusement toute adresse observée.
- Base imposée par les contrats : `industrial_predict_ml_sandbox`, purpose
  `p101-ml-sandbox`. UUID d'instance et de bootstrap nouveaux, jamais copiés d'un
  environnement antérieur. Un nouveau volume/clone exige une nouvelle identité et
  une nouvelle approbation.
- CA P101 dédiée ; certificat serveur avec SAN correspondant exactement à la
  destination client (IP SAN 127.0.0.1 si cette destination est retenue), clé serveur
  distincte, validité et permissions vérifiées. Certificat et clé serveur montés
  en lecture seule ; CA privée hors Git et hors conteneur serveur. Pas de copie des
  certificats ou clés DEV.
- Comptes owner/migrateur, writer et reader distincts, plus administrateur de
  bootstrap local uniquement si nécessaire. Secrets aléatoires nouveaux, fournis
  par fichiers privés/gestionnaire de secrets, jamais en arguments de commande,
  historique shell, rapport ou logs. Pas de redémarrage automatique pendant les
  essais de rupture de connexion ; politique de rétention explicite du volume.

La séparation proposée interdit la réutilisation des identifiants DEV. La preuve
sera l'inventaire des ressources, montages, réseaux, règles d'authentification et
secrets indépendants ; **aucune connexion d'essai vers DEV** n'est nécessaire ni
autorisée pour vérifier un refus.

## 5. Exigences exactes du code ML 4.2B-1

### Configuration et approbations

`SandboxConfig` exige une `DestinationDeclaration` complète : host, port publié,
database imposée, rôle writer `p101_*`, instance UUID canonique et purpose ; puis
adresse/port serveur attendus, owner/reader distincts au format `p101_*`, révision
de persistance Git sur 40 caractères, chemin CA, mot de passe explicite et manifeste
trié d'empreintes SHA-256 des **21 chemins RELEASE_PATHS**.

La factory refuse toute variable `PG*`, ne lit ni DATABASE_URL ni `.env`, impose
`verify-full`, CA explicite, READ COMMITTED, UTF-8, UTC et search_path pg_catalog.
Elle est lazy : sa présence ne prouve aucune connexion. Elle n'est pas une factory
de migration owner prête à l'emploi : son identité est celle du writer.

Le dossier ML 4.2A n'autorise aucune écriture. L'exécution future exige une
`ExecutionApproval` indépendante et non expirée, UUID, empreinte du dossier,
révision, empreinte de politique et HMAC-SHA256, vérifiée avec une clé explicite
d'au moins 32 octets. L'émetteur, la distribution et la rotation de cette clé ne
sont pas implémentés. HMAC utilise un secret partagé : le détenteur du secret de
vérification peut aussi signer ; ce n'est pas une signature asymétrique séparant
cryptographiquement émetteur et exécuteur. Les clés fictives des tests sont exclues.

La révision de raccordement validée est le commit ML 4.2B-1 ci-dessus ; la révision
du calcul reste `b6b4d521b9c9456c160433e9343efd48d3c0168d`. L'autorité doit attester
l'association révision Git/octets du manifeste, notamment après checkout Windows.
Un hash de fichier brut n'est pas le hash du manifeste métier canonisé. Toute
correction de code ultérieure impose revue, nouvelle révision/empreintes et nouvelle
approbation ; ne pas fabriquer une révision pour satisfaire la validation.

### Rôles, TLS et garde effective

| Identité | Capacités futures nécessaires | Interdictions et vérification |
| --- | --- | --- |
| Bootstrap admin | Créer les seules ressources sandbox explicitement autorisées | Secret absent du runtime et aucun rôle/accès DEV ; accès limité au bootstrap |
| Owner/migrateur | Propriétaire des tables/fonctions, droit de création de schéma sur cette base ; session directe pour Alembic | Pas de privilèges globaux durables inutiles ; `session_user = current_user = owner` imposé par env.py : un simple SET ROLE depuis admin échouerait |
| Writer | CONNECT/USAGE nécessaires ; SELECT sources, versions, marqueur et historique ; INSERT registre/prédictions ; USAGE de la séquence ; EXECUTE lock_sources | Aucun membership, ownership, superuser, BYPASSRLS, CREATEDB, CREATEROLE, REPLICATION, CREATE, TEMP, mutation des sources ou recommandations, UPDATE/DELETE historique |
| Reader | CONNECT/USAGE et SELECT des sources/historique nécessaires au GET sandbox | Aucun droit d'écriture, de DDL ou d'exécution des fonctions privilégiées ; vérification indépendante du writer |

Prévoir une connexion owner directe temporairement autorisée, puis fermeture de
son accès/login après bootstrap et fermeture du provisionnement. Les fonctions
SECURITY DEFINER continuent à appartenir à cet owner ; elles ne doivent pas être
créées par un superuser différent, car la garde vérifie leur propriétaire.

Les GRANT de la migration ne suffisent pas seuls : supprimer les droits hérités de
PUBLIC, notamment TEMP sur la base et CREATE sur les schémas ; traiter aussi les
droits de colonne, appartenances et privilèges par défaut. Accorder CONNECT de
façon explicite après retrait des capacités PUBLIC non souhaitées. Vérifier la
visibilité des catalogues et de pg_stat_ssl avec le writer réellement limité.

Configurer le serveur avec TLS actif et règles `hostssl` limitées à cette base,
ces rôles et la provenance réseau approuvée, SCRAM ; refuser les transports TCP
sans TLS et les autres règles permissives. L'initialisation locale privilégiée
constitue une phase séparée ; ne pas laisser une règle `trust` utilisable en service.
Le plan ne requiert pas de certificat client : `verify-full` authentifie le serveur,
SCRAM authentifie le rôle. Un éventuel mTLS demanderait une conception distincte.

Lors d'une connexion future autorisée : vérifier succès avec CA/SAN attendus,
refus avec CA incorrecte, hôte incorrect, certificat invalide et TLS désactivé, sans
fallback. Puis relever ssl/protocole/chiffrement, adresse/port effectifs, base,
session_user/current_user, UUID, owner du marqueur, révisions générales et P101,
fonctions/contraintes/triggers/privilèges. Aucune de ces vérifications serveur
n'a été effectuée aujourd'hui. Le booléen pg_stat_ssl ne prouve pas à lui seul
que le client a vérifié la CA et le nom d'hôte.

### Migrations et fixture

La migration P101 exige déjà `public.alembic_version = 09ac8101e9fe` et les tables
générales. Elle utilise exclusivement `p101_pilot.alembic_version` pour sa propre
révision `p101_0001`, crée registre, contraintes et fonctions/triggers, mais **ne
crée ni rôles, ni marqueur rempli, ni mesures**. Il faut injecter dans Alembic une
connexion neuve, `p101_config` et le callback obligatoire
`p101_authorize_migration`. Ce callback doit authentifier une permission admin
distincte du droit d'écrire la paire ; un lambda retournant True n'est pas une
solution d'autorisation. L'owner doit satisfaire l'identité et le TLS avant ce DDL.

Bootstrap des données proposé : une company/site/equipment/sensor aux codes P101
contractuels ; équipement `pump` au nom contenant « synthétique », capteur
`temperature`, unité °C ; exactement douze mesures de qualité good selon
`tests/p101_anomaly/fixtures/p101-temperature-v1.json`. Les dix premières sont les
références, DEMO-M-011 et DEMO-M-012 les deux cibles. Aucun nouvel algorithme/calcul
n'est nécessaire à cet audit. Les ids SQL seront alloués par cette base et reliés
aux identités logiques, jamais repris de DEV ni des mocks.

L'empreinte canonique de fixture attendue est celle de ML 4.2A, sans la recalculer
ici. `measurements` ne possède pas de colonne `available_at` : l'attestation de
disponibilité temporelle repose sur le manifeste synthétique approuvé, pas sur une
preuve indépendante fournie par SQL. Ce raccordement ne valide donc pas la collecte
industrielle ni l'absence de fuite temporelle pour des mesures réelles.

Le bootstrap futur doit prendre le verrou advisory **exclusif** 1010042, préparer
le singleton environment_guard (instance/bootstrap UUID, base, purpose, rôles,
révisions, provisioning_closed), charger/valider les sources, puis fermer le
provisionnement dans une transaction admin contrôlée. Le service prend le verrou
partagé et des verrous SHARE ; ces derniers ne bloquent pas seuls une nouvelle
mesure insérée par un administrateur. Aucun provisionneur ne doit rester actif
après fermeture. Ne pas précharger de PredictionRecord P101 sans registre.

## 6. Blocages et points à corriger ou compléter avant usage réel

| Réf. | Constat statique | Traitement futur, sans modification aujourd'hui |
| --- | --- | --- |
| R01 — bloquant avant schéma général | L'env Alembic général ignore la connexion injectée et recharge les réglages applicatifs | Préparer un lanceur/env sandbox séparé, gardé avant DDL, rejouant les révisions générales inchangées jusqu'à 09ac8101e9fe ; aucun appel direct au lanceur DEV, aucune simple substitution d'URL dans l'ini |
| R02 — bloquant avant migration P101 | Pas d'émetteur/vérificateur admin concret ni de lanceur injectant les trois attributs obligatoires | Concevoir l'autorisation admin authentifiée et le transport owner verify-full avant toute ouverture de connexion ; env.py contrôle ssl mais ne construit ni ne prouve lui-même ce transport |
| R03 — bloquant avant service | Aucun bootstrap P101 opérationnel ni clés/certificats/identités approuvés ; marqueur vide après migration | Préparer et revoir une procédure dédiée de rôles, privilèges PUBLIC, fixture, marqueur fermé et fermeture owner ; ne pas employer seed.py DEV |
| R04 — bloquant avant démarrage | Moteur Docker, image/digest, port/subnet/IP et chaîne PEM non validés ; OpenSSL CLI disponible sur disque mais inexécutable ici | Reprendre l'inventaire réseau/processus dans un contexte adapté ; choisir et vérifier une chaîne PKI utilisable sans réutiliser les clés DEV ; ne pas certifier un port libre à partir de cet audit |
| R05 — avant premier droit d'écriture | Approbation HMAC, circuit de clés et attestation release Git/octet à organiser | Définir l'autorité et la distribution privée, durée de validité et résolution d'un commit incertain après expiration ; un nouveau jeton peut être requis, sans changer les clés logiques |
| R06 — durcissement à revoir | L'empreinte de politique lie le chemin CA, pas le contenu du certificat CA ; celui-ci est hors RELEASE_PATHS | Épingler séparément l'empreinte de CA et vérifier ses octets/ACL avant transport, ou compléter le contrat dans une étape de code autorisée ; un chemin identique ne prouve pas une CA inchangée |
| R07 — profondeur de garde à revoir | La garde inspecte nom/type/validité/différabilité des contraintes, mais pas toutes leurs expressions/colonnes ; les triggers sont contrôlés sans tous les flags d'événements/timing ; bootstrap_uuid n'est pas comparé par validate_identity | Documenter ces limites ; renforcer les contrôles d'identité/définitions avant de considérer la garde comme preuve complète d'une installation approuvée ; ne jamais contourner son rejet |
| R08 — vérification serveur requise | Fonctions PL/pgSQL, search_path, normalisation JSON, droits de verrouillage, catalogue et SET CONSTRAINTS n'ont pas été analysés par un serveur | Revue SQL préalable puis validation sur sandbox jetable autorisé ; les mocks ne prouvent ni syntaxe serveur, ni atomicité, ni concurrence |
| R09 — avant I10 | Le GET historique existant utilise la configuration/session applicative générale | Préparer un processus/test dédié et une dépendance DB reader sandbox, isolés de .env DEV ; ne pas démarrer l'API habituelle ni tester le GET DEV |

R06/R07 sont des limites identifiées du code actuel, et non des modifications
effectuées. La validation ML 4.2B-1 n'est pas une preuve de ces propriétés
supplémentaires. Aucune erreur SQL serveur précise n'est déclarée démontrée : le SQL
n'a été ni exécuté ni validé par PostgreSQL. Aucune connexion réelle ne doit être
ouverte dans le cadre de ce seul rapport pour lever ces points.

## 7. Plan futur reproductible, avec arrêts de vérification

Chaque étape ci-dessous reste **future et soumise à autorisation explicite** ; ce
rapport n'autorise ni ressources, ni connexions, ni corrections de code.

| Étape | Opération future | Vérification obligatoire avant l'opération / condition de sortie |
| --- | --- | --- |
| P0 — conception locale | Revoir R01–R09 et préparer fichiers sandbox/lanceurs/contrats nécessaires dans une étape distincte | Périmètre Git revu, code et versions approuvés ; aucun secret en Git, aucune découverte implicite de DEV |
| P1 — inventaire et image | Vérifier moteur Linux, images/digests, espace disque, port hôte, subnet et noms uniques | Autorisation des interrogations moteur et d'un éventuel téléchargement ; absence de collision ; aucun arrêt/suppression d'une ressource existante |
| P2 — PKI/configuration | Générer CA et certificat serveur, établir secrets neufs et configuration privée sous ACL | Autorisation de créer ces fichiers ; outil PKI fonctionnel, SAN/validité/empreintes approuvés ; secrets hors dépôt et logs |
| P3 — ressources | Créer nouveau réseau, volume et conteneur à partir du Compose P101 relu | Autorisation nominative de création/démarrage ; inspection du rendu sans exposer les secrets ; aucun montage/réseau DEV ; labels d'instance et boucle locale corrects |
| P4 — première connexion admin | Contrôler TLS et identité effective puis préparer rôles/base sur le cluster neuf | Autorisation de connexion/provisionnement ; image, certificat, transport et destination attendus avant login ; différence ports client/serveur explicitement prévue ; tout écart arrête la procédure |
| P5 — schéma général | Appliquer les neuf révisions via le nouveau chemin sandbox gardé | R01 levé, owner direct limité, base vide/inventaire initial connu, autorisation DDL ; après opération version publique et 14 colonnes/FK/séquence vérifiées |
| P6 — schéma pilote | Appliquer uniquement p101_0001 via env dédié et autorisation admin | R02 levé, bonne révision générale, droits/ownership corrects, connexion TLS neuve ; vérifier version P101, fonctions exactes, contraintes et triggers actifs/différés |
| P7 — bootstrap | Charger uniquement les quatre parents et douze mesures synthétiques, remplir et fermer le marqueur | Autorisation distincte de DML synthétique, verrou exclusif, mapping canonique et contenu exact ; aucune prédiction ajoutée ; droits limités vérifiés, owner déconnecté et accès opérationnel fermé |
| P8 — préflight writer/reader | Vérifier les deux rôles et le refus des mauvaises configurations sur la seule sandbox | Autorisation des connexions de validation ; aucune allocation nextval ni insertion avant garde ; TLS/ACL/marqueur/révisions conformes ; dossier et permission indépendants approuvés |
| P9 — validation I01–I12 | Exécuter un harnais PostgreSQL dédié, y compris concurrence et défauts contrôlés | Autorisation nominative des tests et perturbations du seul sandbox, preuve de référence avant chaque scénario ; rapport de résultats réels avant toute démonstration |

Ne pas utiliser un healthcheck préexistant qui démarrerait avec le service sans
avoir inclus ses connexions dans l'autorisation future. Un échec d'identité/TLS,
une ressource déjà présente ou un contenu inattendu impose l'arrêt ; ni adoption
automatique, ni nettoyage destructif, ni fallback DEV. Les trous de séquence après
rollback sont possibles ; le nettoyage ne doit pas tenter de réparer les ids.

## 8. Conditions préalables aux tests I01–I12

Les 70 tests unitaires du rapport ML 4.2B-1 sont une preuve historique hors base,
**non relancée et non élargie ici**. Aucun test I01–I12 n'est commencé ou réussi.

| Test futur | Prérequis et preuve réelle à obtenir |
| --- | --- |
| I01 Destination | Garde et TLS appliqués au sandbox réel ; refus des configurations contradictoires, aucune tentative de connexion DEV |
| I02 Rattachements | Fixture SQL jetable autorisée et inventaire parents/mesures ; erreurs d'identités/valeurs/unités/qualité refusées pour tout le lot |
| I03 Nominal | Dossier et permission valides ; deux registres/deux prédictions après commit ; relecture indépendante des 14 champs et JSON |
| I04 Retry | Réutiliser les mêmes clés/contenus avec nouvelle tentative autorisée ; conserver ids, created_at et détails initiaux |
| I05 Concurrence | Deux connexions réellement distinctes synchronisées, READ COMMITTED ; gagnant commit et gagnant rollback, exactement une paire |
| I06 Conflit | Cas contrôlés de même clé/contenu divergent et lot partiel ; aucun remplacement ; fixture de conflit séparée |
| I07 Rollback | Injections ciblées autour des réservations/insertions/contraintes ; vérification durable par nouvelle connexion, séquence exceptée |
| I08 Commit incertain | Moyen de couper uniquement les connexions sandbox avec autorisation de perturbation ; relecture nouvelle session, états confirmé/non observé/non résolu |
| I09 Sources concurrentes | Rôle writer sans mutations, administrateur de test contrôlé, protocole advisory exclusif/partagé ; aucune insertion de mesure pendant service normal |
| I10 GET historique | Instance/harness reader indépendant, autorisation HTTP future distincte ; filtres, bornes inclusives, ordre et pagination sans POST/calcul |
| I11 Abstentions | Cas ML 3 déjà contractuels ; refus avant transaction d'écriture, zéro faux score normal |
| I12 Intégrité | Compteurs et empreintes canoniques avant/après par table ; sources/maintenances/recommandations inchangées ; suppression/cascade seulement sur fixture jetable séparément autorisée |

Préalables communs : scripts de préparation reproductibles et versionnés, image
épinglée, vrai schéma migré (pas create_all seul), inventaire initial, certificats
et permissions valides, durée suffisante des approbations, connexions indépendantes
et journaux expurgés. Les perturbations de I08/I09 ne doivent toucher aucun autre
projet. La démonstration finale ne réutilisera pas une base de tests corrompue par
des scénarios négatifs ; nouvelle fixture/identité approuvée si nécessaire.

## 9. Réserves B-PRE-01 à B-PRE-11

| Réserve | État après cet audit |
| --- | --- |
| B-PRE-01 | Ouverte : isolation locale proposée, authentification/autorisation multi-tenant non résolues ; aucune exposition SaaS |
| B-PRE-02 | Ouverte : validation P101 binaire limitée au pilote ; contrats des scores génériques inchangés |
| B-PRE-03 | Ouverte : dates UTC prévues, disponibilité SQL non stockée et bornes GET réelles non vérifiées |
| B-PRE-04 | Ouverte : garde/rattachements préparés ; aucune preuve effective de sources/verrous SQL |
| B-PRE-05 | Ouverte : bornes JSON hors base existantes ; sérialisation/contraintes serveur non exercées |
| B-PRE-06 | Ouverte : protections P101 non installées ; cascades générales inchangées ; aucun nettoyage DEV |
| B-PRE-07 | Ouverte : pagination/snapshot/concurrence et performance non mesurés |
| B-PRE-08 | Ouverte : service dédié évite le commit interne ; atomicité réelle non démontrée et chemin RUL/joblib inchangé |
| B-PRE-09 | Ouverte : aucune alimentation historique ni orchestration générale ; aucun résultat persisté aujourd'hui |
| B-PRE-10 | Ouverte : provenance/approbation/empreintes préparées ; identité et définitions SQL effectives non attestées |
| B-PRE-11 | Ouverte : aucune route ajoutée, aucun GET exécuté ; détail/latest inchangés |

## 10. État Git et validation attendue

HEAD et branche conservés. Index vide ; aucun fichier suivi préexistant modifié.
Seul ajout : `docs/ml-4.2b2-p101-sandbox-readiness.md`. Contrôle final du périmètre
conforme : `git diff --check` et contrôle `git diff --no-index --check` du nouveau
rapport sans erreur d'espacement, sans indexation. Recherche de motifs de secrets
dans le rapport sans résultat ; onze réserves ouvertes présentes. Aucun
commit/push/merge/rebase.

La prochaine décision porte sur le plan et les prérequis/corrections identifiés,
pas sur une autorisation implicite de connexion ou de création. **En attente de
validation ; provisionnement, I01–I12 et ML 5 non commencés.**
