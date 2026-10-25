# ML 4.2B-2.2 / P2.1 — Préparation TLS et configuration privée P101

Date : 25 octobre 2026. Statut : procédure documentaire à valider ; aucune PKI créée.

## 1. Conclusion, référence et périmètre

Une méthode locale compatible PEM est disponible : **OpenSSL 3.5.7 fourni avec Git,
dans `C:/Program Files/Git/mingw64/bin/openssl.exe`**. Il répond aux commandes de
version et d'aide sans installation ni réparation. La procédure proposée utilise
ce chemin explicite, une CA P101 privée et un certificat serveur avec SAN IP
127.0.0.1. Les générations et installations décrites ci-dessous sont futures.

Une limite de sécurité reste à traiter : le code actuel épingle les octets de la
CA, pas ceux du certificat serveur. Un certificat serveur différent, toujours
valide pour 127.0.0.1 et signé par cette CA, peut être accepté par verify-full.
Le refus systématique d'un remplacement de certificat sans nouvelle approbation
ne peut donc pas être certifié avec les seuls contrats actuels (section 7).

Dépôt `D:/projets/industrial-predict`, branche
`feature/ml-4-p101-persistence`, HEAD attendu et observé
`8a064c7e9e914f53ea507a0af78e44646933c95c`. Arbre propre et index vide au départ.
Seul ce rapport est créé. Aucun import applicatif/DEV, aucune connexion PostgreSQL
ou HTTP, aucun Docker lancé, aucune image téléchargée, aucun rôle, certificat,
clé, secret ou fichier privé créé. Aucune migration, insertion, test ML, modification
du code, commit, push, merge ou rebase. P2.2, P3 et ML 5 ne sont pas commencés.

Références : [P1 Docker](ml-4.2b22-p101-docker-preflight.md),
[durcissement P101](ml-4.2b21-p101-sandbox-hardening.md),
[conception de persistance](ml-4.1-p101-persistence-design.md).

## 2. Outils PKI et diagnostic sans modification

| Élément examiné | Observation effective | Limite |
| --- | --- | --- |
| OpenSSL Git mingw64 | Version et bibliothèque 3.5.7 du 9 juin 2026 ; plateforme mingw64 ; `version -a` réussit, code 0 | Génération/signature/export jamais exécutés |
| OpenSSL Git usr/bin | Métadonnées 3.5.7 ; `version -a` échoue en sandbox, code -1073741502 (0xC0000142) | Échec d'initialisation DLL dans ce contexte ; aucune réparation tentée |
| Même usr/bin, permissions adaptées | `version` réussit : OpenSSL 3.5.7, code 0 | Différence liée au contexte d'exécution ; DLL ou règle précise responsable non isolée |
| Dépendances présentes sur disque | Runtime msys-2.0 et bibliothèques msys-crypto/msys-ssl dans usr/bin ; libcrypto/libssl dans mingw64/bin | Présence seulement ; aucun remplacement ou chargement forcé |
| OpenSSL dans PATH | Non trouvé | Utiliser le chemin mingw64 explicite ; aucune modification globale du PATH |
| OpenSSL sous PostgreSQL 18/bin | Exécutable absent | Ne pas dépendre de cette installation pour la PKI |
| PowerShell | 7.6.5, Core | Version du processus d'audit |
| Module Windows PKI | 1.0.0.0, Desktop/Core ; New-SelfSignedCertificate, Export-Certificate, Export-PfxCertificate disponibles | Commandes non invoquées ; aucune écriture dans un magasin de certificats |
| API .NET | CertificateRequest présent ; exports RSA PKCS#8/PEM et X509 ExportCertificatePem visibles par réflexion | Aucune instance de clé créée ; aucun export ni preuve complète de chaîne générée |

Les aides locales de req, x509 et verify confirment les options de configuration,
extensions, validité, série, signature CA et vérification IP/purpose. Aucune commande
de génération n'a été passée à OpenSSL. Aucun certificat existant ni magasin privé
Windows n'a été lu.

Le succès du même binaire usr/bin hors des restrictions et le succès direct du
binaire mingw64 ne justifient pas de déclarer OpenSSL corrompu ou absent. La cause
profonde du refus MSYS n'est pas démontrée ; il n'est pas nécessaire de réparer
Git, modifier des DLL, désactiver une protection ou installer OpenSSL pour retenir
le chemin mingw64 fonctionnel. Windows PKI/.NET restent une alternative possible,
mais la conversion et la gestion d'un magasin/PFX ajouteraient une autre procédure
à valider ; elles ne sont pas retenues pour ce pilote PEM.

## 3. Paramètres TLS proposés

| Objet | Paramètres proposés, à approuver avant création |
| --- | --- |
| CA dédiée | Une racine autonome P101, aucun lien avec DEV ni une CA de machine/entreprise ; RSA 4096, signature SHA-256, validité 365 jours maximum |
| Contraintes CA | BasicConstraints critique CA:true, pathlen:0 ; KeyUsage critique keyCertSign,cRLSign ; SubjectKeyIdentifier hash |
| Certificat serveur | RSA 3072, signature SHA-256, validité 30 jours maximum et jamais au-delà de la CA ; série aléatoire positive unique d'au moins 128 bits |
| Contraintes serveur | BasicConstraints critique CA:false ; KeyUsage critique digitalSignature,keyEncipherment ; ExtendedKeyUsage serverAuth ; SKI et AKI |
| Identité | SAN de type IP contenant exactement 127.0.0.1 pour la destination proposée ; aucun wildcard, identité DEV ou SAN ajouté implicitement |
| CN | Libellé public du pilote ; aucune dépendance au CN pour vérifier l'adresse IP |
| Transport | TLS serveur obligatoire, minimum TLS 1.2, TLS 1.3 autorisé selon piles réelles ; client libpq verify-full avec CA explicite |
| Authentification des rôles | Secrets distincts et SCRAM-SHA-256 sous TLS ; certificat client/mTLS non prévu par les contrats actuels |

Les durées sont des choix de politique, pas des certificats créés. Contrôler l'heure
UTC de l'hôte, du conteneur et du signataire avant émission ; arrêter en cas de
décalage, sans corriger automatiquement l'horloge. Une CA proche de l'expiration
doit être renouvelée avant de signer une nouvelle feuille.

La destination client 127.0.0.1:55432 reste une proposition issue de P1, à
revérifier avant provisionnement. Le SAN IP porte sur l'hôte client, pas sur le
port, ni sur l'adresse interne du conteneur. L'adresse/port serveur effectifs
resteront comparés séparément à la politique P101. Changer pour localhost ou un
autre nom exige SAN et destination approuvés correspondants.

## 4. Procédure reproductible future, non exécutée

### 4.1 Préparer l'espace privé et les autorisations

Avant tout fichier réel : approbation explicite de P2.2 et de son périmètre,
opérateur PKI identifié, chemin physique absolu hors du dépôt, de ses worktrees,
des dossiers synchronisés et des emplacements DEV. Aucun nom personnel ou chemin
privé réel n'est fourni ici. Refuser les jonctions/symlinks et les destinations
préexistantes non attestées ; ne pas écraser un ancien lot de certificats.

Créer ultérieurement trois périmètres séparés sous ACL restreintes :

- Signataire : clé CA chiffrée, source de sa passphrase et registre de séries ;
  accès au seul opérateur/compte de signature approuvé, avec restauration protégée.
- Staging serveur : clé serveur et certificat signé ; accès temporaire au
  provisionneur et au mécanisme Docker de copie explicitement identifié.
- Client : uniquement certificat CA public approuvé et configuration/références
  de secrets propres à chaque rôle. Aucun accès runtime à la clé CA.

Désactiver l'héritage large des ACL avant génération ; aucun Everyone/Users/
Authenticated Users en lecture des clés, mots de passe ou clés HMAC. Les accès
SYSTEM/service de staging doivent être limités à ceux réellement nécessaires.
Les administrateurs de l'hôte restent une autorité privilégiée ; ces ACL ne
constituent pas une protection contre un administrateur hostile. Ne jamais
imprimer les clés, passphrases, mots de passe, PFX, jetons ou chaînes de connexion.

### 4.2 Profils de certificat à matérialiser uniquement après autorisation

Les profils suivants sont publics et ne contiennent aucune valeur privée. Ils
devront devenir des fichiers explicites dans l'espace PKI autorisé, sans dépendre
des extensions d'un profil global ou d'une configuration DEV. Avant génération,
contrôler aussi les éventuels paramètres OPENSSL_CONF/OPENSSL_MODULES du processus
et n'accepter que les profils et modules locaux approuvés, sans modification
globale du système.

Profil CA proposé :

```ini
[req]
prompt = no
distinguished_name = dn
x509_extensions = v3_ca
[dn]
CN = P101 sandbox dedicated CA
[v3_ca]
basicConstraints = critical,CA:true,pathlen:0
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
```

Profil CSR et extensions serveur proposés ; le signataire impose ces extensions
explicitement et ne copie pas aveuglément celles d'une CSR :

```ini
[req]
prompt = no
distinguished_name = dn
req_extensions = v3_server
[dn]
CN = P101 sandbox PostgreSQL
[v3_server]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = IP:127.0.0.1
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
```

Pour la CSR, employer une section de requête identique mais sans
authorityKeyIdentifier, car l'émetteur n'est pas encore connu. La section
v3_server complète avec AKI est celle de la signature finale. Cette séparation
doit être matérialisée dans les profils futurs, pas supprimée pour contourner
une erreur d'extension OpenSSL.

### 4.3 Générer, signer et vérifier localement après autorisation

Séquence future exclusivement documentaire ; les variables représentent des
chemins et séries fournis par le dispositif privé approuvé. Aucun exemple de clé,
passphrase, série réelle ou UUID n'est fourni. Le profil CSR désigne la variante
sans AKI décrite ci-dessus.

```powershell
# FUTUR UNIQUEMENT : aucune de ces commandes n'a été exécutée.
& $opensslPath genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -aes-256-cbc -pass ("file:" + $caPassFile) -out $caKey
& $opensslPath req -new -x509 -sha256 -days 365 -key $caKey -passin ("file:" + $caPassFile) -config $caProfile -extensions v3_ca -set_serial ("0x" + $caSerialHex) -out $caCert
& $opensslPath genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out $serverKey
& $opensslPath req -new -sha256 -key $serverKey -config $serverCsrProfile -out $serverCsr
& $opensslPath x509 -req -sha256 -days 30 -in $serverCsr -CA $caCert -CAkey $caKey -passin ("file:" + $caPassFile) -set_serial ("0x" + $serverSerialHex) -extfile $serverSigningProfile -extensions v3_server -out $serverCert
```

Fixer opensslPath au binaire mingw64 vérifié. Avant chaque commande : vérifier
ses paramètres, les ACL, les chemins, la disponibilité de la CA et l'absence du
fichier de sortie ; vérifier le code de sortie immédiatement après. Générer les
secrets et séries ultérieurement via une source cryptographique approuvée ; une
passphrase ne doit jamais être passée littéralement en argument ou variable
d'environnement. Une source file: exige elle-même des ACL strictes et un contenu
mono-ligne protégé. Ne pas utiliser une passphrase de rôle comme passphrase CA.

La clé CA est chiffrée ; la clé serveur proposée est un PEM sans passphrase pour
un démarrage PostgreSQL non interactif, protégé par les permissions Linux et les
montages. Une clé serveur chiffrée exigerait un mécanisme ssl_passphrase_command
distinct, absent de cette procédure ; ne pas le supposer implémenté.

Vérifications futures hors serveur : correspondance de la clé publique du serveur
avec CSR/certificat, signature/chaîne, séries uniques, dates, SAN IP exact, usages,
CA:false/true et longueur des clés. Exemple de contrôle local futur :

```powershell
& $opensslPath verify -no-CApath -no-CAstore -CAfile $caCert -purpose sslserver -verify_ip 127.0.0.1 -x509_strict $serverCert
& $opensslPath x509 -in $serverCert -noout -checkip 127.0.0.1
& $opensslPath x509 -in $serverCert -noout -checkend 604800
$caPemSha256 = (Get-FileHash -LiteralPath $caCert -Algorithm SHA256).Hash.ToLowerInvariant()
```

Ces contrôles locaux n'ont pas été exécutés faute de certificat réel autorisé.
N'imprimer que des métadonnées publiques nécessaires et les empreintes approuvées.
Le SHA attendu par tls_root_sha256 porte sur **les octets exacts du fichier PEM**,
pas sur l'empreinte DER affichée par x509 -fingerprint, ni celle d'une clé publique.
Conserver le fichier byte pour byte, sans BOM, conversion de fins de ligne ou
réencodage après approbation. Limite du code : 65 536 octets et chemin absolu non
redirigé. Toute modification de représentation change son empreinte.

### 4.4 Installation Linux et montages, après autorisation d'infrastructure

P1 a observé une image PostgreSQL 17.10 déclarée, avec le volume de données
`/var/lib/postgresql/data`. L'installation TLS doit rester dans un espace distinct,
par exemple `/run/p101-tls`, monté en lecture seule dans le futur serveur P101.
Ne monter ni la clé CA ni sa passphrase dans PostgreSQL, ni le volume TLS d'un DEV.

Les modes POSIX vus via un bind Windows/Docker Desktop ne sont pas garantis par
les seules ACL NTFS. PostgreSQL peut refuser une clé trop permissive, même avec
un montage readonly. Prévoir une copie future dans un **nouveau volume TLS Linux
P101**, via un installateur éphémère explicitement autorisé, sans réseau et sans
contact DEV, puis montage readonly de ce volume dans le serveur. Aucune ressource
de ce type n'est créée pendant P2.1 ; sa création/copie appartient à une étape
d'infrastructure autorisée séparément.

Vérifier l'UID/GID du processus PostgreSQL dans l'image approuvée, sans supposer
999. Options de permissions à valider : clé propriétaire postgres, mode 0600 ; ou
clé root, mode 0640, groupe de lecture PostgreSQL adéquat. Répertoire privé 0700
pour postgres, ou 0750 root/groupe PostgreSQL. Certificat public 0644 ou lecture
plus restrictive compatible ; aucun droit d'écriture au processus serveur sur la
clé montée. Vérifier avec stat et lecture sous l'identité effective, sur la seule
future infrastructure P101. Ne pas tenter chmod d'un bind readonly pour réparer
une incompatibilité de modes.

Paramètres serveur futurs : ssl=on, ssl_cert_file pointant vers le certificat
serveur, ssl_key_file vers sa clé, ssl_min_protocol_version=TLSv1.2. La feuille
signée directement par la racine suffit côté certificat serveur ; le client reçoit
sa racine approuvée par son fichier CA. ssl_ca_file côté serveur concerne la
vérification des certificats clients, qui n'est pas prévue ici.

La politique pg_hba future doit autoriser uniquement hostssl sur la base P101 et
les rôles approuvés avec SCRAM, depuis le CIDR client effectivement approuvé ;
refuser hostnossl et les autres règles réseau permissives, IPv4 et IPv6. Le serveur
conteneurisé peut voir une adresse NAT/passerelle, pas 127.0.0.1 : ne pas inventer
ce CIDR d'après le seul SAN. Une phase locale de bootstrap privilégié nécessite
sa propre autorisation ; aucune règle trust réseau ne doit rester ouverte en
exploitation. Ne pas réutiliser un pg_hba, un rôle ou un secret DEV.

## 5. Structure documentaire de configuration privée

Ce schéma est **non opérationnel** : placeholders uniquement, aucun fichier de
configuration ou chargeur créé. Les seuls nombres/adresses sont les propositions
publiques du pilote ; destination interne et identités restent à approuver.

| Rubrique privée future | Champs / source | Correspondance actuelle |
| --- | --- | --- |
| Identité | instance_uuid et bootstrap_uuid canoniques nouveaux, purpose p101-ml-sandbox, base industrial_predict_ml_sandbox | DestinationDeclaration et SandboxConfig ; jamais une identité DEV copiée |
| Réseau | host 127.0.0.1, port publié proposé 55432, server_address approuvé, server_port interne proposé 5432 | Deux couples distincts, liés à la politique et vérifiés effectifs |
| CA | tls_root_certificate = `<ABSOLUTE_PHYSICAL_CA_PEM_PATH>` ; tls_root_sha256 = `<APPROVED_RAW_PEM_SHA256>` | Champs obligatoires, vérification des octets avant factory/approbations |
| Serveur TLS | Références privées clé/certificat et profils, série, dates, empreinte DER de feuille et image/digest approuvés | Dossier d'installation proposé ; empreinte de feuille non consommée par la garde actuelle |
| Rôles | owner_role = `<P101_OWNER_ROLE>` ; destination.role = `<P101_WRITER_ROLE>` ; reader_role = `<P101_READER_ROLE>` | Noms distincts au format p101_* ; aucune valeur de compte réel fournie |
| Secrets de rôles | Références séparées `<BOOTSTRAP_ADMIN_SECRET_REF>`, `<OWNER_SECRET_REF>`, `<WRITER_SECRET_REF>`, `<READER_SECRET_REF>` | Résolution privée externe ; SandboxConfig.password reçoit seulement le secret writer résolu, masqué dans repr |
| Secrets de signature | `<CA_PASSPHRASE_REF>`, `<ADMIN_HMAC_KEY_REF>`, `<BUSINESS_HMAC_KEY_REF>` | Trois secrets indépendants, jamais déduits des mots de passe SQL ; émetteurs HMAC non provisionnés |
| Release | persistence_revision = `<APPROVED_GIT_COMMIT>` ; release_files = `<EXACT_35_PATHS_AND_RAW_SHA256>` | Attestation indépendante des octets du code ; ne pas inventer une révision |
| Approbation admin | UUID, AdminAction, plan_sha256, policy_sha256, expiration UTC, signature privée | AdminApproval/Verifier ; scopes migration générale, pilote et bootstrap séparés |
| Approbation métier | UUID, dossier_sha256, persistence_revision, guard_policy_sha256, expiration et signature privée | ExecutionApproval/ApprovalVerifier ; aucune permission déduite du dossier ML 4.2A |

Les références de secrets sont une organisation documentaire, pas des valeurs
acceptées telles quelles par les dataclasses. Le résolveur privé futur doit fournir
les types attendus sans afficher de DSN ou de secret. Aucun `.env` DEV ou
DATABASE_URL implicite ; aucune variable PG* dans les processus P101 owner/writer.
La CA P101 ne doit pas être installée comme racine de confiance globale Windows.

Connexions :

- Writer : factory explicite existante, verify-full et CA épinglée, READ COMMITTED,
  UTF-8/UTC, search_path pg_catalog ; mot de passe writer seulement.
- Owner : connexion explicite fournie de l'extérieur ; validate_owner_transport
  exige URL et paramètres effectifs conformes, sslmode verify-full, bonne CA,
  ssl_in_use vrai, identité owner et options exactement
  `-c search_path=pg_catalog -c timezone=UTC`. Aucun constructeur owner réel n'est
  créé ou appelé ici.
- Reader : rôle prévu par les contrats, mais pas de factory reader dédiée dans
  le code P101 actuel. Ne pas détourner la factory writer ou ses secrets. Un
  futur harnais reader doit imposer CA/verify-full et droits de lecture explicites,
  avant toute API ou validation I10 autorisée.

## 6. Renouvellement et changement de confiance

Prévoir un rappel opérateur avant la fenêtre checkend de sept jours, sans créer
d'automatisation dans cette étape. Nouveau certificat : nouvelle clé serveur et
série, validation hors ligne, autorisation d'installation et enregistrement des
empreintes publiques ; aucune substitution silencieuse. Installer une nouvelle
version de fichiers, vérifier les modes puis activer/recharger uniquement le
futur serveur P101 lors d'une opération autorisée. Les connexions existantes
devront être renouvelées pour démontrer le nouveau certificat effectif.

Renouveler la CA implique de nouveaux octets, un nouvel SHA-256 PEM, une nouvelle
empreinte de politique et de nouvelles approbations admin/métier. Changer seulement
le chemin de CA ou les fins de ligne invalide aussi la politique. Toute transition
avec plusieurs racines dans un bundle serait une nouvelle politique explicite,
avec empreinte du bundle exact et revue de la confiance élargie.

Aucune gestion de CRL/OCSP n'est provisionnée ou prouvée par le pilote. La rotation
et les durées courtes ne sont pas une preuve de révocation immédiate. En cas de
compromission CA, interrompre le seul pilote, retirer la confiance selon une
procédure approuvée et réémettre les identités/approbations ; ne pas connecter DEV
pour vérifier un refus.

## 7. Contrôles futurs et écart d'épinglage serveur

Ces contrôles sont **documentaires, non exécutés**, à réaliser seulement sur un
PostgreSQL P101 explicitement autorisé avec matériel de test dédié.

| Contrôle futur | Preuve attendue et limite actuelle |
| --- | --- |
| TLS nominal | CA et SAN IP valides, verify-full effectif ; protocole/chiffrement serveur, ssl_in_use et pg_stat_ssl concordants ; identité réseau/base/rôle/marqueur attendue avant DDL/DML |
| Mauvaise CA | Fichier CA non approuvé refusé par verify_ca/approbation avant connexion ; avec matériel de test séparément approuvé mais mauvaise chaîne, échec TLS sans requête applicative |
| Certificat invalide | Certificat expiré, usage ou chaîne invalides refusés ; aucune relance en sslmode require/prefer/disable |
| SAN incorrect | Certificat signé par CA de test approuvée mais IP absente/incorrecte : échec de vérification de nom ; le CN ne répare pas ce SAN |
| Destination non autorisée | Refus de paramètres modifiés ou d'identité effective contradictoire avant écriture ; le test ne contacte jamais DEV |
| CA remplacée | Même chemin, autres octets : refus par digest ; nouvelle empreinte déclarée avec ancien jeton : refus de politique/signature |
| Feuille remplacée, autre CA ou SAN invalide | Échec de chaîne/identité TLS attendu ; cela ne démontre pas un épinglage de feuille |
| Feuille remplacée, même CA et SAN valide | Le code actuel peut accepter cette feuille ; le refus sans nouvelle approbation n'est pas implémenté |
| Absence de repli | Serveur sans TLS ou échec TLS : arrêt ; aucune autre destination/CA ou connexion en clair tentée ; aucune assertion fondée uniquement sur un booléen ssl |
| Permissions et montages | Modes Linux et identité du processus conformes ; clés non modifiables par le serveur, aucun montage/secret DEV, CA privée absente du conteneur |

**Écart TLS-01 :** guard_policy_fingerprint lie chemin/empreinte CA, instance,
bootstrap, rôles et release, mais pas le certificat serveur ni son SPKI.
verify-full authentifie une identité certifiée par la CA approuvée, pas l'unicité
du certificat présenté. Les ACL et la signature d'une procédure d'installation
réduisent les possibilités de substitution, sans ajouter ce contrôle au client.

Pour prouver le refus strict demandé en cas de feuille valide remplacée sans
approbation, une étape de code séparément autorisée doit définir un épinglage
du certificat DER ou du SPKI, le lier à la politique/aux approbations et comparer
la preuve du pair TLS avant SQL applicatif, avec un moyen compatible avec
psycopg/libpq. L'accès effectif à cette preuve n'est ni implémenté ni démontré ici.
Choisir DER impose une nouvelle approbation à chaque renouvellement ; SPKI seul
accepte un certificat réémis avec la même clé et ne satisfait pas un refus de
tout changement de feuille. Ce choix doit être tranché avant de déclarer ce
contrôle réussi. Aucun champ de documentation ne doit être présenté comme déjà
vérifié par le code.

## 8. R01–R09, prérequis et conditions d'arrêt avant P2.2

| Réserve | État et suite nécessaire |
| --- | --- |
| R01 | Entrée de migrations générales isolée préparée ; aucun DDL réel ni transaction Alembic validés |
| R02 | Approbation admin typée préparée ; émetteur/secret réels et connexion owner à provisionner séparément |
| R03 | Plans de rôles/bootstrap/privilèges préparés ; aucune création ou insertion ; secrets et fermeture owner restent futurs |
| R04 | P1 a constaté moteur/image/port ; P2.1 identifie OpenSSL fonctionnel et procédure PEM ; fichiers PKI, ACL/modes, réseau, stockage et installation encore absents |
| R05 | Clés HMAC admin/métier et circuit d'émission toujours non provisionnés ; elles restent distinctes de la clé CA et des secrets SQL |
| R06 | SHA-256 des octets CA lié au code existant ; génération, X.509 et contrôles réels à valider ; écart TLS-01 de feuille explicitement ouvert |
| R07 | Contrôles de catalogue/bootstrap_uuid préparés, non confrontés à PostgreSQL ; aucun contrôle SQL désactivé |
| R08 | DDL, PL/pgSQL, droits, verrous, atomicité, concurrence et I01–I12 toujours non validés sur PostgreSQL |
| R09 | Aucun harnais reader/GET autonome créé ; ne pas employer l'API DEV ; autorisation HTTP future distincte |

Avant P2.2 : approuver cette procédure et son périmètre de génération seulement,
les durées/usages/SAN, le signataire, les chemins privés et ACL, l'outil exact et
les formats ; décider du traitement TLS-01 sans attribuer une garantie absente au
code. Vérifier la séparation profil CSR/signature et la source privée de
passphrases/séries. Une autorisation de génération ne vaut pas autorisation de
créer un conteneur/volume, d'installer la clé dans Linux ou de se connecter à SQL.

Arrêt obligatoire sur outil non fonctionnel, chemin redirigé/partagé/DEV, droits
trop larges, fichier de sortie déjà présent, horloge incohérente, erreur OpenSSL,
SAN/usages/dates incorrects, digest inattendu ou signature d'approbation absente.
Aucun téléchargement, élargissement de permissions, remplacement de DLL,
acceptation de CA globale ou repli non chiffré ne doit réparer silencieusement
un tel écart.

## 9. Réserves B-PRE-01 à B-PRE-11

| Réserve | État après P2.1 |
| --- | --- |
| B-PRE-01 | Ouverte : TLS local proposé, aucune autorisation multi-tenant SaaS démontrée |
| B-PRE-02 | Ouverte : contrats de scores génériques inchangés |
| B-PRE-03 | Ouverte : aucune nouvelle preuve de dates, disponibilité SQL ou bornes GET |
| B-PRE-04 | Ouverte : aucun rattachement ou verrou réel vérifié |
| B-PRE-05 | Ouverte : sérialisation/validation JSON serveur non exercées |
| B-PRE-06 | Ouverte : protections non installées et cascades générales inchangées |
| B-PRE-07 | Ouverte : snapshot, pagination et performances non testés |
| B-PRE-08 | Ouverte : aucune transaction réelle validée ; RUL/joblib inchangés |
| B-PRE-09 | Ouverte : aucune alimentation de l'historique ou orchestration réelle |
| B-PRE-10 | Ouverte : CA prévue et écart de feuille identifié ; provenance/identité serveur non attestées |
| B-PRE-11 | Ouverte : aucun endpoint ajouté ni GET appelé |

## 10. État Git final et livraison

Branche et HEAD conservés ; index vide, aucun fichier suivi modifié. Seul ajout :
`docs/ml-4.2b22-p101-tls-readiness.md`. Contrôles finaux conformes : périmètre
limité à ce rapport, `git diff --check` et contrôle `git diff --no-index --check`
du nouveau fichier sans erreur d'espacement ; recherche de motifs de secrets/DSN
sans résultat, lecture des placeholders uniquement, R01–R09 et onze réserves
ouvertes présents. Aucune indexation ni aucun commit.

**En attente de validation technique. Aucun matériel PKI réel ni aucune ressource
P2.2/P3 n'a été créé ; aucune autorisation implicite n'est déduite du rapport.**
