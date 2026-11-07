# P101-DEV-3D-INFRA-3 — transport de collecte PostgreSQL/TLS

Ce composant est opt-in : aucun I/O à l'import ou à la construction. Seul un appel
explicite à `open_readonly` tente une connexion. Aucun branchement par défaut,
activation de migrations, changement des contrats publiés ou activation du writer.
Le subnet candidat `172.30.121.0/28` n'est ni utilisé par défaut ni approuvé ici.

## API et intégration future

`transport.ReadOnlyPostgresTransport(campaign, policy)` réutilise `Campaign`,
`CollectorPolicy`, leurs validations et `collectors.TlsBinding` sans modification.
Il satisfait structurellement `BoundPostgresTransport` :

```python
transport = ReadOnlyPostgresTransport(campaign, policy)
collector = PostgresCollector(campaign, policy, transport=transport)
# Future action distinctement autorisée, jamais exécutée dans cette mission :
# collector.collect(SqlCredentials(role, password), revision=revision)
```

`open_readonly(*, host, port, database, role, password, ca_der, timeout, options)`
exige les valeurs exactes de la campagne/politique. `options` doit être exactement
la constante `transport.OPTIONS` (lecture seule au startup, statement_timeout 3 s,
lock_timeout 1 s). `timeout` est un nombre fini positif <= 3 s. Aucun paramètre
de downgrade TLS ou DSN n'est admis. Les mots de passe sont limités à 1–4096
caractères ASCII imprimables sans espace ; prévoir un secret aléatoire dans cet
alphabet. Les mots de passe Unicode sont refusés, sans SASLprep approximatif.

La connexion fournit `cursor`, `rollback`, `close`, et le curseur `execute`,
`fetchone`, `fetchall`, `close`. Ce n'est pas un pilote DB-API général : seules
les quatre requêtes de métadonnées existantes et les instructions transactionnelles
fixes du collecteur sont admises. Pas de paramètres SQL, DML, DDL, commit, retry,
pool ou reconnexion. Une connexion doit être utilisée séquentiellement par un
seul collecteur ; les collectes concurrentes nécessitent leurs propres connexions.

Le runner futur embarquera uniquement ces sources figées et leur manifeste.
Son collecteur Docker reste externe, sans socket Docker dans le runner.
La PKI, l'inventaire indépendant, la livraison des secrets, le digest d'image et
l'autorisation humaine restent des prérequis distincts. L'API ne délivre aucune
autorisation et tous les résultats héritant d'`Offline` restent non attestés.

## Architecture et capture du certificat

Le contrôle local de psycopg/psycopg-binary 3.3.4 trouve `ssl_in_use`, `socket`
et `used_password`, mais aucune API directe de certificat du pair. Un descripteur
de socket ne permet pas de reconstruire le contexte TLS de libpq. Le pointeur
`PGconn` pourrait servir à une extension native dépendant du backend TLS ; ce lot
n'utilise ni FFI/ctypes ni attribut libpq inventé.

L'adaptateur minimal utilise donc directement le sous-ensemble PostgreSQL v3
nécessaire à la collecte :

1. Connexion IPv4 à l'adresse numérique approuvée, sans DNS ou configuration PG*
   ambiante ; vérification de l'adresse du pair.
2. SSLRequest sur cette socket ; seule la réponse `S` est acceptée.
3. Enveloppement de cette même socket par `ssl.SSLContext(PROTOCOL_TLS_CLIENT)`.
   CA DER explicite uniquement, CERT_REQUIRED, vérification SAN du nom de campagne,
   sans repli CN, TLS >= 1.2. Aucune racine système n'est chargée.
4. Handshake puis `SSLSocket.getpeercert(binary_form=True)` : le certificat feuille
   provient de la socket qui transporte ensuite le startup, SCRAM et les requêtes.
   Aucun deuxième probe TLS, connexion de cancellation ou socket de preuve.
5. SCRAM-SHA-256 complet, vérification constante de la signature serveur avant
   AuthenticationOk. Trust, MD5, mot de passe clair et séquences invalides refusés.
6. Requête IDENTITY_SQL sur cette connexion : comparaison destination, base,
   utilisateurs SQL, cluster, instance, version, lecture seule et absence de
   privilèges élevés/marqueur DEV ; PID comparé au BackendKeyData du protocole.
7. `tls_binding(connection)` vérifie propriétaire, socket ouverte, adresse,
   certificat et version TLS et retourne le `TlsBinding` existant. Le collecteur
   effectue ses contrôles SQL/TLS habituels avant et après ses lectures.

« verify-full » désigne ici les garanties chaîne + nom, et non un paramètre libpq.
Le profil minimal utilise une CA signant directement le certificat serveur :
Python 3.12 ne fournit pas dans cette implémentation de capture publique de la
chaîne intermédiaire. `intermediates_der=()` est explicite. Ne pas substituer une
chaîne lue ailleurs à une capture de session. Une chaîne avec intermédiaires peut
passer OpenSSL mais échouera au comparateur existant si elle ne peut être reconstruite
avec les preuves fournies ; elle n'est pas un profil supporté dans ce lot.

SCRAM-SHA-256-PLUS/channel binding n'est pas implémenté ; le contrat actuel demande
SCRAM-SHA-256. Chaque ouverture crée un nouveau contexte et ne réutilise pas de
session TLS. Ce choix ne prétend pas résister à une CA compromise ou à un processus
client modifié.

## Dépendances et bornes

- Transport : bibliothèque standard uniquement, référence locale CPython **3.12.10**,
  OpenSSL **3.0.16**. Aucun psycopg, pg8000 ou scramp requis par ce module.
- Collecteur existant/vérification X.509 et tests : **cryptography 50.0.2**.
- Tests : **pytest 9.1.1**.
- Aucun paquet installé ou téléchargé. Ces versions décrivent l'environnement
  testé, pas un lock transitif/image de runner ni une recommandation de production.

Ouverture bornée à 3 s maximum, puis 7 s supplémentaires maximum, sans remise à
zéro par requête. Chaque opération socket reçoit le temps restant (<= 3 s).
4096–100000 itérations SCRAM, paquets <= 64 Kio, réponses <= 256 Kio, <= 64 lignes
et colonnes ; types texte, booléens et entiers nécessaires au collecteur seulement.
Les notifications, notices et messages non pris en charge échouent fermés.

Échec d'ouverture, de requête, de rollback ou de liaison TLS propriétaire :
fermeture tentée. `close` n'effectue pas d'unwrap réseau et ne réessaie jamais un
descripteur dont la fermeture est ambiguë. Une erreur de fermeture est remontée
avec le diagnostic constant existant ; elle ne prouve pas la libération effective.
L'appelant ferme aussi les connexions réussies, comme le fait `PostgresCollector`.

Les points d'entrée publics effacent cause et contexte des erreurs. Aucun log,
DSN, secret ou diagnostic serveur n'est émis ; repr hérite du format opaque.
Cela n'efface pas la mémoire, les variables locales d'un débogueur, un dump de
processus ou les erreurs d'un helper privé appelé directement.

## Validation hors ligne et limites

`test_transport.py` interdit les accès réseau/processus réels. Il couvre les
paramètres, CA malformée, destination divergente, modes d'authentification refusés,
signature SCRAM incorrecte, framing/EOF, délais, fermeture et assainissement.
Le vecteur SCRAM publié dans RFC 7677 est vérifié indépendamment du faux serveur.
Une intégration du collecteur existant utilise des octets PostgreSQL scriptés.

Les tests TLS utilisent OpenSSL avec deux MemoryBIO : handshake cryptographique
en mémoire, certificat exact, mauvaise CA et mauvais nom. Les clés éphémères des
fixtures sont brièvement chargées depuis le répertoire temporaire de test puis
les fichiers PEM sont supprimés. Aucune connexion TCP ni instance PostgreSQL.
Ces tests ne qualifient ni TLS sur le réseau réel, ni SCRAM avec PostgreSQL réel.

Une future campagne autorisée devra vérifier PostgreSQL 17.10, le vrai framing,
SCRAM et HBA, TLS/CA/SAN et refus négatifs sur la même session, PID et destination,
ACL réelles, timeouts (dont fermeture), profil Docker et collecte assainie. Les
gardes `request_execution`/`require_real_attestation` restent fermées. Les contrats
B2B restent limités aux révisions qu'ils reconnaissent ; ce transport n'ajoute
pas le head P101, le bootstrap, un exécuteur ou une autorité opérationnelle.

Commande de test ciblé (répertoire temporaire neuf dans le workspace si nécessaire) :

```powershell
& D:/projets/industrial-predict-oidc-m1b-venv/Scripts/python.exe -B -m pytest tests/b2b_postgres_qualification/test_transport.py -q -p no:cacheprovider
```

Références primaires : [API psycopg/libpq](https://www.psycopg.org/psycopg3/docs/api/pq.html),
[socket TLS Python](https://docs.python.org/3.12/library/ssl.html),
[flux PostgreSQL](https://www.postgresql.org/docs/17/protocol-flow.html),
[formats v3](https://www.postgresql.org/docs/17/protocol-message-formats.html),
[SASL PostgreSQL](https://www.postgresql.org/docs/17/sasl-authentication.html),
[vecteur SCRAM RFC 7677](https://www.rfc-editor.org/rfc/rfc7677.html#section-3).
