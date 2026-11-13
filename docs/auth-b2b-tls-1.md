# AUTH-B2B-TLS-1 — procédure opérateur PostgreSQL DEV UI47

13 novembre 2026 — **préparation uniquement**. Aucune commande Docker/PostgreSQL,
génération de certificat, modification de profil privé ou de volume effectuée.
Seul ce document est ajouté. Toutes les commandes ci-dessous sont **à exécuter
après validation humaine**, dans l'ordre, en arrêtant au premier échec.

## Choix et conditions de départ

Le Compose officiel `infra/development/compose.yaml` monte le volume externe
`industrial-predict-postgres-ui47-data` dans `/var/lib/postgresql/data` et ne
surcharge que `cluster_name`. Conserver image, conteneur, ports, volume et Compose.
Stocker les fichiers serveur sous **PGDATA/tls-ui47-v1**, et les paramètres dans
`postgresql.auto.conf` via ALTER SYSTEM : ils survivent aux arrêts et à une future
recréation technique utilisant le même volume. Aucun `compose up`, `down`, nouveau
mount, initdb ou remplacement de volume n'est nécessaire.

CA DEV locale dédiée, clé CA chiffrée conservée hors Docker ; certificat serveur
signé par cette CA, SAN **IP:127.0.0.1**, EKU serverAuth, validité proposée 365 jours
(CA 5 ans). La clé serveur sans passphrase permet un démarrage non interactif ;
sa protection repose sur ACL Windows puis propriétaire postgres/mode 0600 Linux.
Ne jamais copier la clé CA dans le conteneur ou le volume. Ne pas installer cette
CA dans le magasin Windows global : seul `sslrootcert` explicite lui fait confiance.
Les extensions et options utilisées sont celles d'[OpenSSL 3](https://docs.openssl.org/3.0/man1/openssl-req/)
et de [x509](https://docs.openssl.org/3.0/man1/openssl-x509/).

Prévoir une fenêtre sans écritures DEV, et maintenir les clients DEV fermés selon
la procédure d'exploitation approuvée. Ne pas arrêter les services historiques.
Le contrôle local par socket admin ci-dessous doit déjà fonctionner ; sinon STOP,
aucune modification de pg_hba ni ajout de trust. La CA/passphrase sera placée en
archive hors ligne protégée, accessible aux seuls opérateurs autorisés ; garder
un inventaire des dates d'expiration et prévoir le renouvellement avant échéance.

## 1. Précontrôles, dossier privé et sauvegarde

PowerShell 7 ; OpenSSL 3 approuvé doit être disponible par chemin explicite/PATH.
Aucun OpenSSL trouvé dans le PATH pendant cette mission : faire qualifier le
binaire séparément, sans installation automatique. Le backend local contient
psycopg **3.3.4**, libpq binaire **18.3** (`180003`), inspectés sans connexion.
La capacité de négociation réelle avec PostgreSQL 17.10 sera prouvée à l'étape 4.

```powershell
Set-Location -LiteralPath 'D:\projets\industrial-predict'
$ErrorActionPreference = 'Stop'
$devPython = (Resolve-Path '.\backend\.venv\Scripts\python.exe').Path
$devConfig = 'D:\integration\industrial-predict\development\config.json'
$tlsRoot = 'D:\integration\industrial-predict\development\tls-ui47-v1'
$tlsContainer = 'industrial-predict-postgres-ui47'
$ossl = (Get-Command openssl.exe -ErrorAction Stop).Source
function Run([string]$Exe, [string[]]$Argv) {
    & $Exe @Argv
    if ($LASTEXITCODE -ne 0) { throw "STOP : échec de $Exe" }
}
function DevSql([string]$Sql) {
    $Sql | & docker exec -i --user postgres $tlsContainer psql -X -w -h /var/run/postgresql -p 5432 -v ON_ERROR_STOP=1 -U ui47_admin -d industrial_predict_dev
    if ($LASTEXITCODE -ne 0) { throw 'STOP : administration locale refusée' }
}
Run $ossl @('version') # exiger OpenSSL 3 approuvé, pas un téléchargement implicite
@'
import sys
sys.path.insert(0,'infra/development')
import manage
c=manage.load_config(sys.argv[1])
manage.verify_container(c)
manage.verify_volume(c)
print('Identité Docker/volume officielle conforme')
'@ | & $devPython -B - $devConfig
if ($LASTEXITCODE -ne 0) { throw 'STOP : identité DEV non conforme' }
DevSql "SELECT current_database(),current_user,version(),current_setting('data_directory'),current_setting('config_file'),current_setting('app.development_instance_id',true); SELECT version_num FROM public.alembic_version; SELECT name,setting,context,source,sourcefile,pending_restart FROM pg_settings WHERE name IN ('ssl','ssl_cert_file','ssl_key_file','ssl_min_protocol_version');"
```

Exiger PostgreSQL 17.10, rôle ui47_admin, base DEV, marqueur égal au profil privé,
version Alembic unique `09ac8101e9fe`, PGDATA `/var/lib/postgresql/data`, config
dans ce PGDATA, ssl=off. Si chemin/source de réglage différents, ou surcharge SSL
en ligne de commande, arrêter et réviser cette procédure. Ne pas afficher le
profil, les fichiers password ni `docker inspect` complet.

```powershell
if (Test-Path -LiteralPath $tlsRoot) { throw 'STOP : dossier TLS déjà présent' }
New-Item -ItemType Directory -Path $tlsRoot | Out-Null
$tlsSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
Run 'icacls.exe' @($tlsRoot,'/inheritance:r','/grant:r',"*${tlsSid}:(OI)(CI)F",'*S-1-5-18:(OI)(CI)F','*S-1-5-32-544:(OI)(CI)F')
Get-Acl -LiteralPath $tlsRoot | Format-List # opérateur, SYSTEM, Administrateurs seulement
Copy-Item -LiteralPath $devConfig -Destination (Join-Path $tlsRoot 'config.before.json')
Run 'docker' @('exec','--user','postgres',$tlsContainer,'sh','-ceu','umask 077; test ! -e /tmp/ui47-before-tls.dump; pg_dump -h /var/run/postgresql -p 5432 -U ui47_admin -w -d industrial_predict_dev -Fc -f /tmp/ui47-before-tls.dump; pg_restore --list /tmp/ui47-before-tls.dump >/dev/null; pg_restore --file=/dev/null /tmp/ui47-before-tls.dump')
Run 'docker' @('cp',"${tlsContainer}:/tmp/ui47-before-tls.dump",(Join-Path $tlsRoot 'before-tls.dump'))
Get-FileHash -LiteralPath (Join-Path $tlsRoot 'before-tls.dump') -Algorithm SHA256
@'
import hashlib, subprocess, sys
from pathlib import Path
r=Path(sys.argv[1]); p=r/'auto-before.tar'
with p.open('xb') as f:
    subprocess.run(['docker','cp','-a','industrial-predict-postgres-ui47:/var/lib/postgresql/data/postgresql.auto.conf','-'],stdout=f,check=True)
(r/'auto-before.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest(),encoding='ascii')
'@ | & $devPython -B - $tlsRoot
if ($LASTEXITCODE -ne 0) { throw 'STOP : sauvegarde configuration absente' }
```

Archive complète actuelle, propriétaires/ACL inclus, catalogue et contenu relus ;
conserver l'empreinte dans les preuves privées. Ce contrôle ne prouve pas une
restauration et ne remplace pas la répétition B2B exigée par AUTH-B2B-DEV-2.
Le rollback TLS ci-dessous restaure uniquement la configuration, jamais les données.

Définir cette sonde Windows en mémoire puis capturer la référence industrielle :

```powershell
$tlsProbe = @'
import json, os, sys
from pathlib import Path
sys.path.insert(0,'infra/development')
import manage, psycopg
from sqlalchemy import create_engine
mode, root = sys.argv[1], Path(sys.argv[2])
try:
    assert mode in ('before','after','rollback')
    assert not any(k.upper().startswith('PG') for k in os.environ)
    c=manage.load_config('D:/integration/industrial-predict/development/config.json')
    tls={'sslmode':'verify-full','sslrootcert':str(root/'ca.crt')} if mode=='after' else {'sslmode':'disable'}
    opts={**tls,'connect_timeout':5,'options':'-c search_path=public -c timezone=UTC','gssencmode':'disable'}
    engine=create_engine(manage.db_url(c,'admin'),echo=False,hide_parameters=True,connect_args=opts)
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as db:
            with db.begin():
                db.exec_driver_sql('SET TRANSACTION READ ONLY')
                manage.inspect_connection(db,c,'admin')
                assert db.exec_driver_sql('SHOW ssl').scalar_one()==('on' if mode=='after' else 'off')
                snap=manage.b2b_snapshot(db)
        if mode=='before':
            with (root/'industrial-before.json').open('x',encoding='utf-8') as f: json.dump(snap,f)
        else:
            assert snap==json.loads((root/'industrial-before.json').read_text(encoding='utf-8'))
    finally: engine.dispose()
    if mode=='after':
        for role in ('app','migrator'):
            engine=create_engine(manage.db_url(c,role),echo=False,hide_parameters=True,connect_args=opts)
            try:
                with engine.connect() as db:
                    with db.begin():
                        db.exec_driver_sql('SET TRANSACTION READ ONLY')
                        manage.inspect_connection(db,c,role)
                        assert db.exec_driver_sql('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').scalar_one() is True
            finally: engine.dispose()
        u=manage.db_url(c,'migrator')
        try:
            with psycopg.connect(host=u.host,port=u.port,dbname=u.database,user=u.username,password=u.password,
                    **{**opts,'sslrootcert':str(root/'wrong-ca.crt')}) as db:
                raise AssertionError('Une mauvaise CA a été acceptée')
        except psycopg.OperationalError as e:
            assert 'certificate verify failed' in str(e).lower(), 'Refus non attribuable au certificat'
    print({'before':'Référence enregistrée','after':'verify-full OK; mauvaise CA refusée; données industrielles identiques','rollback':'Rollback configuration OK; données industrielles identiques'}[mode])
except Exception:
    print('STOP : qualification TLS/identité/données échouée',file=sys.stderr)
    raise SystemExit(2) from None
'@
$tlsProbe | & $devPython -B - before $tlsRoot
if ($LASTEXITCODE -ne 0) { throw 'STOP : référence industrielle absente' }
```

`sslmode=disable` est réservé au relevé administratif initial et au contrôle après
retour à ssl=off ; aucun profil B2B ni garde n'est abaissé.
La sonde ne fait que des lectures et compare les huit tables/séquences existantes.

## 2. Certificats et installation persistante

```powershell
Push-Location -LiteralPath $tlsRoot
try {
    Run $ossl @('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-aes-256-cbc','-out','ca.key')
    # Passphrase saisie dans OpenSSL, jamais dans argv, environnement ou transcription.
    Run $ossl @('req','-new','-x509','-key','ca.key','-sha256','-days','1825','-subj','/CN=Industrial Predict DEV UI47 CA','-addext','basicConstraints=critical,CA:TRUE,pathlen:0','-addext','keyUsage=critical,keyCertSign,cRLSign','-out','ca.crt')
    Run $ossl @('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-out','server.key')
    Run $ossl @('req','-new','-key','server.key','-subj','/CN=industrial-predict-dev-ui47','-out','server.csr')
    "basicConstraints=critical,CA:FALSE`nkeyUsage=critical,digitalSignature,keyEncipherment`nextendedKeyUsage=serverAuth`nsubjectAltName=IP:127.0.0.1" | Set-Content -LiteralPath 'server.ext' -Encoding ascii
    Run $ossl @('x509','-req','-in','server.csr','-CA','ca.crt','-CAkey','ca.key','-CAcreateserial','-days','365','-sha256','-extfile','server.ext','-out','server.crt')
    Run $ossl @('verify','-CAfile','ca.crt','-purpose','sslserver','-verify_ip','127.0.0.1','server.crt')
    Run $ossl @('pkey','-in','server.key','-pubout','-out','key-public.pem')
    Run $ossl @('x509','-in','server.crt','-pubkey','-noout','-out','cert-public.pem')
    if ((Get-FileHash key-public.pem).Hash -ne (Get-FileHash cert-public.pem).Hash) { throw 'Clé/certificat incohérents' }
    # CA de test indépendante ; clé de test confinée au même dossier privé.
    Run $ossl @('req','-new','-x509','-newkey','rsa:2048','-noenc','-days','1','-subj','/CN=UI47 Wrong CA Test','-addext','basicConstraints=critical,CA:TRUE','-keyout','wrong-ca.key','-out','wrong-ca.crt')
} finally { Pop-Location }
Run 'docker' @('exec','--user','0',$tlsContainer,'sh','-ceu','test "$PGDATA" = /var/lib/postgresql/data; test ! -e "$PGDATA/tls-ui47-v1"; install -d -m 0700 -o postgres -g postgres "$PGDATA/tls-ui47-v1"; cp -p "$PGDATA/postgresql.auto.conf" "$PGDATA/tls-ui47-v1/auto.before.conf"')
Run 'docker' @('cp',(Join-Path $tlsRoot 'server.crt'),"${tlsContainer}:/var/lib/postgresql/data/tls-ui47-v1/server.crt")
Run 'docker' @('cp',(Join-Path $tlsRoot 'server.key'),"${tlsContainer}:/var/lib/postgresql/data/tls-ui47-v1/server.key")
Run 'docker' @('exec','--user','0',$tlsContainer,'sh','-ceu','chown postgres:postgres "$PGDATA/tls-ui47-v1/server.crt" "$PGDATA/tls-ui47-v1/server.key"; chmod 0644 "$PGDATA/tls-ui47-v1/server.crt"; chmod 0600 "$PGDATA/tls-ui47-v1/server.key"; stat -c "%U %G %a %n" "$PGDATA/tls-ui47-v1" "$PGDATA/tls-ui47-v1/server.key"')
```

Exiger répertoire postgres:postgres 700 et clé postgres:postgres 600 ; ne pas fixer
un UID Docker supposé. La CA et sa clé ne sont jamais envoyées au serveur.
Les fichiers serveur sont dans le volume Linux : leurs modes sont distincts des
ACL du répertoire Windows. Les sauvegardes physiques du volume contiendront la
clé serveur et devront rester protégées. Conserver la clé CA chiffrée hors ligne.

## 3. Activation par rechargement

Les paramètres TLS sont rechargeables dans PostgreSQL 17 ; confirmer localement
`context=sighup` et `pending_restart=false`. Une erreur de fichier au rechargement
laisse l'ancienne configuration SSL active : `pg_reload_conf()=true` indique
l'envoi du signal, pas la réussite TLS. Vérifier par une nouvelle connexion.
[Référence serveur PostgreSQL 17](https://www.postgresql.org/docs/17/ssl-tcp.html),
[contexte du paramètre ssl](https://github.com/postgres/postgres/blob/REL_17_STABLE/src/backend/utils/misc/guc_tables.c).

```powershell
DevSql @'
ALTER SYSTEM SET ssl_cert_file = 'tls-ui47-v1/server.crt';
ALTER SYSTEM SET ssl_key_file = 'tls-ui47-v1/server.key';
ALTER SYSTEM SET ssl_min_protocol_version = 'TLSv1.2';
ALTER SYSTEM SET ssl = 'on';
SELECT name,error FROM pg_file_settings WHERE error IS NOT NULL;
SELECT pg_reload_conf();
'@
DevSql "SELECT name,setting,pending_restart FROM pg_settings WHERE name IN ('ssl','ssl_cert_file','ssl_key_file','ssl_min_protocol_version');"
```

Attendre le traitement du signal, ouvrir une nouvelle session et exiger ssl=on,
les chemins prévus, aucune erreur de configuration. Examiner les journaux dans
un canal privé si échec. Aucune modification pg_hba : TLS est disponible sur le
même port, sans imposer TLS à tous les anciens clients ; B2B l'impose côté client.
Ce lot ne configure pas de certificats clients/mTLS (`ssl_ca_file` inutile ici).

**Redémarrage seulement après décision humaine distincte**, clients DEV fermés,
configurations et clés validées, sauvegarde/rollback disponibles. Un mauvais
certificat peut empêcher le démarrage : ne pas redémarrer pour tenter de réparer
un reload échoué. Si un redémarrage a été approuvé pour valider la persistance,
utiliser exclusivement les contrôles officiels, sans recréation :

```powershell
Run $devPython @('-B','infra/development/manage.py','db-stop','--config',$devConfig)
Run $devPython @('-B','infra/development/manage.py','db-start','--config',$devConfig)
```

## 4. Qualification Windows et profil privé

`verify-full` vérifie chaîne et identité ; libpq accepte le SAN IP pour une
connexion à 127.0.0.1. Les paramètres sont transmis par psycopg à libpq.
[Validation libpq](https://www.postgresql.org/docs/17/libpq-ssl.html),
[paramètres psycopg](https://www.psycopg.org/psycopg3/docs/api/connections.html).

```powershell
$tlsProbe | & $devPython -B - after $tlsRoot
if ($LASTEXITCODE -ne 0) { throw 'STOP : ne pas enregistrer b2b_transport' }
# Comparer cette empreinte publique à celle de la CA approuvée, avant son épinglage.
$tlsCaHash = (Get-FileHash -LiteralPath (Join-Path $tlsRoot 'ca.crt') -Algorithm SHA256).Hash.ToLowerInvariant()
$tlsCaHash
```

Succès requis sur de **nouvelles connexions Windows** app/migrator avec la bonne
CA, `pg_stat_ssl.ssl=true`, identité/version attendues ; refus cryptographique
avec la CA valide mais indépendante. Une erreur réseau ou d'authentification
ne valide pas le test négatif. La sonde compare aussi toutes les empreintes
industrielles avant/après et ne journalise aucun secret ni exception de pilote.

Seulement après ces succès et revue de l'empreinte, ajouter le champ privé :

```powershell
$tlsProfileAcl = Get-Acl -LiteralPath $devConfig
$tlsProfile = Get-Content -LiteralPath $devConfig -Raw | ConvertFrom-Json -AsHashtable
if ($tlsProfile.ContainsKey('b2b_transport')) { throw 'STOP : champ déjà présent, revue nécessaire' }
$tlsProfile['b2b_transport'] = @{ sslmode='verify-full'; sslrootcert=(Join-Path $tlsRoot 'ca.crt'); ca_sha256=$tlsCaHash }
$tlsProfile | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $devConfig -Encoding utf8NoBOM
Set-Acl -LiteralPath $devConfig -AclObject $tlsProfileAcl
@'
import sys
sys.path.insert(0,'infra/development')
import manage,b2b_policy
c=manage.load_config(sys.argv[1]); b2b_policy.transport(c)
print('Profil et SHA-256 CA conformes ; aucune migration lancée')
'@ | & $devPython -B - $devConfig
if ($LASTEXITCODE -ne 0) { throw 'STOP : profil TLS refusé' }
```

Préserver tous les autres champs et l'ACL du profil ; ne jamais l'afficher.
Le hash est celui des octets PEM exacts : une réécriture du fichier nécessite
une nouvelle validation de l'empreinte. Aucun changement de politique/manifestes
B2B, aucun appel à b2b-backup/rehearse/migrate dans ce lot TLS.

## 5. Retour arrière sans toucher aux données

Maintenir B2B fermé. Sur le **même conteneur/volume vérifié**, restaurer l'unique
fichier de configuration sauvegardé, puis recharger ; jamais restaurer un dump
sur DEV pour annuler TLS. Aucune autre modification concurrente de configuration
n'est admise entre sauvegarde et rollback, sinon instruire un retour ciblé.

```powershell
Run 'docker' @('exec','--user','postgres',$tlsContainer,'sh','-ceu','test "$PGDATA" = /var/lib/postgresql/data; test -f "$PGDATA/tls-ui47-v1/auto.before.conf"; cp -p "$PGDATA/tls-ui47-v1/auto.before.conf" "$PGDATA/postgresql.auto.conf"; pg_ctl -D "$PGDATA" reload')
Copy-Item -LiteralPath (Join-Path $tlsRoot 'config.before.json') -Destination $devConfig -Force
DevSql "SHOW ssl; SELECT version_num FROM public.alembic_version;"
$tlsProbe | & $devPython -B - rollback $tlsRoot
if ($LASTEXITCODE -ne 0) { throw 'STOP : retour arrière non qualifié' }
```

Attendre ssl=off ; version `09ac8101e9fe`, identités et empreintes industrielles
inchangées. La référence `industrial-before.json` est comparée sans être réécrite.
Si le serveur est déjà arrêté, employer **à la place du docker exec** le tar
préservant les métadonnées Linux sauvegardé à l'étape 1 ; pas de pipeline binaire
PowerShell. [Docker cp](https://docs.docker.com/reference/cli/docker/container/cp/)
supporte un conteneur arrêté et l'option archive conserve UID/GID.

```powershell
@'
import hashlib, subprocess, sys, tarfile
from pathlib import Path
sys.path.insert(0,'infra/development')
import manage
c=manage.load_config('D:/integration/industrial-predict/development/config.json')
manage.verify_container(c); manage.verify_volume(c)
r=Path(sys.argv[1]); p=r/'auto-before.tar'
assert hashlib.sha256(p.read_bytes()).hexdigest()==(r/'auto-before.sha256').read_text(encoding='ascii')
with tarfile.open(p) as t:
    members=t.getmembers()
    assert len(members)==1 and members[0].name=='postgresql.auto.conf' and members[0].isfile()
with p.open('rb') as f:
    subprocess.run(['docker','cp','-a','-','industrial-predict-postgres-ui47:/var/lib/postgresql/data/'],stdin=f,check=True)
'@ | & $devPython -B - $tlsRoot
if ($LASTEXITCODE -ne 0) { throw 'STOP : restauration configuration échouée' }
Copy-Item -LiteralPath (Join-Path $tlsRoot 'config.before.json') -Destination $devConfig -Force
Run $devPython @('-B','infra/development/manage.py','db-start','--config',$devConfig)
$tlsProbe | & $devPython -B - rollback $tlsRoot
if ($LASTEXITCODE -ne 0) { throw 'STOP : retour arrière non qualifié' }
```

Aucun fichier de données, volume ou certificat n'est supprimé.
Ne jamais abaisser B2B à require/prefer/disable pour le rouvrir.

**Décision attendue : valider la procédure, le binaire OpenSSL, les ACL, la fenêtre
DEV et le plan de retour. Aucun changement d'environnement n'est autorisé par
la simple livraison de ce document.**

Contrôles effectués sur ce livrable : 10 blocs PowerShell et 5 blocs Python
analysés syntaxiquement sans exécution ; aucun caractère de remplacement ou
espace final. La qualification réelle des certificats, de TLS et du rollback
reste à réaliser après validation humaine.
