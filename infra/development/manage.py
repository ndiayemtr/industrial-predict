"""Explicit local development tooling, separate from normal API/Angular startup."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from urllib.request import urlopen

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

import b2b_policy as b2b
import b2b_activation as activation

REPO = Path(__file__).resolve().parents[2]
REVISION = '09ac8101e9fe'
RUNTIME_REVISION = 'b2b_0002_analyze'
RUNTIME_MODE = 'b2b-preparation'
SOURCE_CLUSTER = '7673083456081215526'
TABLES = ('companies', 'sites', 'equipments', 'sensors', 'measurements',
          'maintenance_records', 'prediction_records', 'maintenance_recommendations')
B2B_TABLES = ('local_users', 'external_identities', 'company_memberships',
              'membership_permissions', 'application_sessions', 'oidc_transactions')
BUSINESS_SEQUENCES = frozenset(table + '_id_seq' for table in TABLES)
B2B_SEQUENCES = frozenset(('local_users_id_seq', 'external_identities_id_seq', 'company_memberships_id_seq'))


def load_config(filename):
    path = Path(filename).resolve(strict=True)
    if path.is_relative_to(REPO):
        raise ValueError('Private configuration must be outside Git')
    config = json.loads(path.read_text(encoding='utf-8'))
    activation.require_preparation(config)
    expected = {'mode': 'local-development', 'db_host': '127.0.0.1', 'db_port': 5434,
                'database': 'industrial_predict_dev', 'api_port': 8001, 'frontend_port': 4201,
                'container': 'industrial-predict-postgres-ui47', 'volume': 'industrial-predict-postgres-ui47-data',
                'database_oid': 16384}
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError('Development target mismatch')
    if not re.fullmatch(r'[0-9]+', config.get('cluster_identifier', '')) or config['cluster_identifier'] == SOURCE_CLUSTER:
        raise ValueError('Development cluster missing or protected')
    if not re.fullmatch(r'[0-9a-f-]{36}', config.get('instance_id', '')):
        raise ValueError('Development instance marker missing')
    if not isinstance(config.get('volume_created_at'), str) or not config['volume_created_at']:
        raise ValueError('Persistent volume identity missing')
    config['_path'] = str(path)
    config['_directory'] = str(path.parent)
    return config


def db_url(config, role):
    if role not in ('app', 'migrator', 'admin'):
        raise ValueError('Unknown development role')
    password = (Path(config['_directory']) / f'{role}-password.txt').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'[0-9a-f]{64}', password):
        raise ValueError('Development secret missing or malformed')
    return URL.create('postgresql+psycopg', username=f'ui47_{role}', password=password,
                      host=config['db_host'], port=config['db_port'], database=config['database'])


def inspect_connection(connection, config, role='app', revision=True, *, expected_revision=REVISION):
    proof = dict(connection.execute(text("""SELECT current_database() AS database,
        current_user AS role,current_setting('server_version') AS version,
        current_setting('app.development_instance_id',true) AS instance_id,
        current_setting('cluster_name') AS cluster_name,
        (SELECT oid FROM pg_database WHERE datname=current_database()) AS database_oid,
        pg_backend_pid() AS backend_pid,
        (SELECT rolsuper FROM pg_roles WHERE rolname=current_user) AS superuser,
        (SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user) AS createdb,
        (SELECT rolcreaterole FROM pg_roles WHERE rolname=current_user) AS createrole,
        (SELECT rolreplication FROM pg_roles WHERE rolname=current_user) AS replication,
        (SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user) AS bypassrls""")).mappings().one())
    if proof['database'] != config['database'] or proof['database_oid'] != config['database_oid'] or proof['instance_id'] != config['instance_id'] or proof['role'] != f'ui47_{role}':
        raise ValueError('Connected development identity mismatch')
    if not proof['version'].startswith('17.10') or proof['cluster_name'] != 'industrial-predict-development':
        raise ValueError('PostgreSQL version mismatch')
    if role != 'admin' and any(proof[key] for key in ('superuser','createdb','createrole','replication','bypassrls')):
        raise ValueError('Excessive development privileges')
    if revision:
        proof['revision'] = connection.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one()
        if proof['revision'] != expected_revision:
            raise ValueError('Development migration mismatch')
    return proof


def runtime_connect_args(config):
    # Reuse the approved inventory and CA verifier without changing migration policy.
    policy = b2b.policy()
    destination = policy['destination']
    if any(config.get(key) != value for key, value in destination.items()):
        raise ValueError('Runtime destination differs from approved DEV inventory')
    if Path(config['_path']).resolve() != Path(policy['profile']).resolve():
        raise ValueError('Unapproved runtime profile')
    transport = b2b.transport(config)
    if any(key.upper().startswith('PG') for key in os.environ):
        raise ValueError('Ambient libpq settings forbidden for DEV runtime')
    return {**transport, 'connect_timeout': 3, 'gssencmode': 'disable',
            'options': '-c search_path=public -c timezone=UTC'}


def runtime_engine(config):
    arguments = runtime_connect_args(config)  # Reject invalid TLS before reading a password.
    return create_engine(db_url(config, 'app'), echo=False, hide_parameters=True,
                         pool_pre_ping=True, connect_args=arguments)


def inspect_runtime_connection(connection, config):
    runtime_connect_args(config)
    proof = inspect_connection(connection, config, expected_revision=RUNTIME_REVISION)
    cluster = connection.exec_driver_sql('SELECT system_identifier::text FROM pg_control_system()').scalar_one()
    ssl = connection.exec_driver_sql('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').scalar_one()
    if cluster != config['cluster_identifier'] or ssl is not True:
        raise ValueError('Runtime cluster/TLS identity mismatch')
    return {**proof, 'cluster_identifier': cluster, 'ssl': True, 'tls_verify_full': True,
            'runtime_mode': RUNTIME_MODE, 'business_routes_enabled': False}


def inspect_runtime_schema(connection, *, profile=RUNTIME_MODE):
    activation.require_profile(profile)
    tables = dict(connection.exec_driver_sql("SELECT tablename,tableowner FROM pg_tables WHERE schemaname='public'").all())
    if set(tables) != set(TABLES) | set(B2B_TABLES) | {'alembic_version'} or any(
            owner != 'ui47_migrator' for owner in tables.values()):
        raise ValueError('Runtime tables or owners mismatch')
    if connection.exec_driver_sql("SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname='public'").scalar_one() != 'ui47_migrator':
        raise ValueError('Runtime schema owner mismatch')
    sequences = dict(connection.exec_driver_sql("SELECT sequencename,sequenceowner FROM pg_sequences WHERE schemaname='public'").all())
    if set(sequences) != BUSINESS_SEQUENCES | B2B_SEQUENCES or any(
            owner != 'ui47_migrator' for owner in sequences.values()):
        raise ValueError('Runtime sequence set or owners mismatch')
    for name in sorted(sequences):
        privileges = {p: bool(connection.execute(text('SELECT has_sequence_privilege(current_user,:name,:privilege)'),
                        {'name': 'public.' + name, 'privilege': p}).scalar_one()) for p in ('USAGE', 'SELECT', 'UPDATE')}
        expected = {'USAGE': name in BUSINESS_SEQUENCES, 'SELECT': False, 'UPDATE': False}
        if privileges != expected:
            raise ValueError('Unexpected runtime sequence privileges')
    if profile == activation.CANDIDATE:
        return {'sequence_usage_only': True, **activation.inspect_acl(connection, profile=profile)}
    # Preparation phase only: no B2B endpoints are mounted. A future activation
    # must separately qualify a minimal grant profile instead of inheriting CRUD.
    for name in B2B_TABLES:
        for privilege in activation.TABLE_PRIVILEGES:
            if connection.execute(text('SELECT has_table_privilege(current_user,:name,:privilege)'),
                                  {'name': 'public.' + name, 'privilege': privilege}).scalar_one():
                raise ValueError('B2B privileges require a separately reviewed activation profile')
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'REFERENCES'):
            if connection.execute(text('SELECT has_any_column_privilege(current_user,:name,:privilege)'),
                                  {'name': 'public.' + name, 'privilege': privilege}).scalar_one():
                raise ValueError('B2B column privileges not enabled during preparation')
    return {'sequence_usage_only': True, 'b2b_access': 'not_enabled'}


def inspect_db(config, *, profile=RUNTIME_MODE):
    activation.require_profile(profile)
    engine = runtime_engine(config)
    try:
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.exec_driver_sql('BEGIN TRANSACTION READ ONLY')
            try:
                result = inspect_runtime_connection(connection, config)
                result.update(inspect_runtime_schema(connection, profile=profile))
                result['counts'] = {table: connection.exec_driver_sql(f'SELECT count(*) FROM public.{table}').scalar_one() for table in TABLES}
                permissions = {}
                for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','TRIGGER','REFERENCES'):
                    permissions[privilege] = [bool(connection.execute(text('SELECT has_table_privilege(current_user,:table,:privilege)'),
                        {'table':'public.'+table,'privilege':privilege}).scalar_one()) for table in TABLES]
                result['crud_all_tables'] = all(all(permissions[p]) for p in ('SELECT','INSERT','UPDATE','DELETE'))
                result['extra_table_privileges'] = any(any(permissions[p]) for p in ('TRUNCATE','TRIGGER','REFERENCES'))
                result['schema_create'] = connection.execute(text("SELECT has_schema_privilege(current_user,'public','CREATE')")).scalar_one()
                result['database_create'] = connection.execute(text('SELECT has_database_privilege(current_user,current_database(),\'CREATE\')')).scalar_one()
                result['temporary_tables'] = connection.execute(text('SELECT has_database_privilege(current_user,current_database(),\'TEMP\')')).scalar_one()
                result['alembic_update'] = connection.execute(text("SELECT has_table_privilege(current_user,'public.alembic_version','UPDATE')")).scalar_one()
                result['owns_business_tables'] = connection.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user")).scalar_one() != 0
                result['role_memberships'] = connection.execute(text('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)')).scalar_one()
                if not result['crud_all_tables'] or not result['sequence_usage_only'] or any(result[k] for k in ('extra_table_privileges','schema_create','database_create','temporary_tables','alembic_update','owns_business_tables','role_memberships')):
                    raise ValueError('Unexpected runtime privileges')
                return result
            finally:
                connection.exec_driver_sql('ROLLBACK')
    finally:
        engine.dispose()


def check_api(config):
    with urlopen(f"http://127.0.0.1:{config['api_port']}/__dev/identity", timeout=4) as response:
        proof = json.load(response)
        if response.headers.get('X-Industrial-Predict-Environment') != 'local-development':
            raise ValueError('API marker missing')
    if (proof.get('mode') != config['mode'] or proof.get('database') != config['database']
            or proof.get('instance_id') != config['instance_id'] or proof.get('role') != 'ui47_app'
            or proof.get('revision') != RUNTIME_REVISION
            or proof.get('database_oid') != config['database_oid']
            or proof.get('cluster_name') != 'industrial-predict-development'
            or proof.get('cluster_identifier') != config['cluster_identifier']
            or proof.get('runtime_mode') != RUNTIME_MODE or proof.get('business_routes_enabled') is not False
            or proof.get('ssl') is not True or proof.get('tls_verify_full') is not True
            or any(proof.get(k) is not False for k in ('superuser','createdb','createrole','replication','bypassrls'))):
        raise ValueError('API target mismatch')
    return proof


def free_port(port):
    with socket.socket() as candidate:
        candidate.bind(('127.0.0.1', port))


def compose_command(config, *args):
    return ['docker','compose','--project-name','industrial-predict-ui47','--env-file',
            str(Path(config['_directory'])/'compose.env'),'-f',str(REPO/'infra/development/compose.yaml'),*args]


def verify_container(config):
    # Refuse to manage a same-name container attached to another volume/project.
    result = subprocess.run(['docker','inspect',config['container']],capture_output=True,check=True,text=True)
    container = json.loads(result.stdout)[0]
    if container['Config']['Labels'].get('com.docker.compose.project') != 'industrial-predict-ui47':
        raise ValueError('Development Docker project mismatch')
    mounts = [m for m in container['Mounts'] if m['Destination'] == '/var/lib/postgresql/data']
    if len(mounts) != 1 or mounts[0].get('Name') != config['volume']:
        raise ValueError('Development Docker volume mismatch')
    if container['HostConfig']['PortBindings'] != {'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'5434'}]}:
        raise ValueError('Development Docker binding mismatch')


def verify_volume(config):
    result = subprocess.run(['docker','volume','inspect',config['volume']],capture_output=True,check=True,text=True)
    volume = json.loads(result.stdout)[0]
    if volume['Name'] != config['volume'] or volume.get('CreatedAt') != config['volume_created_at']:
        raise ValueError('Persistent volume changed; automatic recreation forbidden')


def migrate(config):
    # Explicit migration identity only. App settings are assigned before imports.
    engine = create_engine(db_url(config, 'migrator'), echo=False)
    try:
        with engine.connect() as connection:
            inspect_connection(connection, config, 'migrator', revision=False)
    finally:
        engine.dispose()
    os.environ['DATABASE_URL'] = db_url(config, 'migrator').render_as_string(hide_password=False)
    os.environ['APP_ENV'] = 'local-development'
    os.environ['DEBUG'] = 'false'
    sys.path.insert(0, str(REPO/'backend'))
    os.chdir(REPO/'backend')
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(str(REPO/'backend/alembic.ini')), REVISION)
    # Explicit grants after migrations; runtime cannot edit Alembic metadata.
    admin = create_engine(db_url(config, 'admin'), echo=False)
    try:
        with admin.begin() as connection:
            inspect_connection(connection, config, 'admin')
            for table in TABLES:
                connection.exec_driver_sql(f'GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE public.{table} TO ui47_app')
            connection.exec_driver_sql('GRANT SELECT ON TABLE public.alembic_version TO ui47_app')
            connection.exec_driver_sql('GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO ui47_app')
    finally:
        admin.dispose()


def b2b_plan(config, target):
    return b2b.release(config, current=REVISION, role='ui47_migrator', target=target)


def b2b_confirm(action, plan, *, archive_hash='none'):
    """Local operator boundary, deliberately no --yes or JSON approval switch."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError('B2B requires an interactive operator terminal')
    token = f'{action} {b2b.digest(b2b.canonical(plan))} {archive_hash}'
    print('Review destination, exact release and private backup/restore evidence before proceeding.')
    print('This confirms only this operation. Type exactly: ' + token)
    if input('Confirmation: ') != token:
        raise ValueError('B2B human confirmation missing')


def b2b_engine(config):
    transport = b2b.transport(config)
    if any(key.upper().startswith('PG') for key in os.environ):
        raise ValueError('Ambient libpq settings forbidden for B2B engine')
    # Explicit connection parameters suppress inherited libpq service/options.
    url = db_url(config, 'migrator')
    return create_engine(url, echo=False, hide_parameters=True,
                         connect_args={**transport, 'connect_timeout': 5,
                                       'options': '-c search_path=public -c timezone=UTC'})


def b2b_identity(connection, config, *, expected_revision, empty=False):
    inspect_connection(connection, config, 'migrator', revision=False)
    versions = connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars().all() if not empty else []
    if not empty and versions != [expected_revision]:
        raise ValueError('B2B live revision mismatch')
    cluster = connection.exec_driver_sql('SELECT system_identifier::text FROM pg_control_system()').scalar_one()
    if cluster != config['cluster_identifier']:
        raise ValueError('B2B live cluster mismatch')
    safe = connection.exec_driver_sql("""SELECT
        (SELECT rolcanlogin FROM pg_roles WHERE rolname=current_user) AND
        has_schema_privilege(current_user,'public','USAGE') AND
        has_schema_privilege(current_user,'public','CREATE') AND
        (SELECT nspowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)
         FROM pg_namespace WHERE nspname='public') AND
        NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)) AND
        NOT EXISTS (SELECT 1 FROM pg_event_trigger WHERE evtenabled <> 'D') AND
        NOT EXISTS (SELECT 1 FROM pg_default_acl WHERE defaclrole=(SELECT oid FROM pg_roles WHERE rolname=current_user)
                    AND defaclnamespace IN (0,'public'::regnamespace)) AND
        NOT has_schema_privilege('ui47_app','public','CREATE') AND
        NOT EXISTS (SELECT 1 FROM pg_namespace n, LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
                    WHERE n.nspname='public' AND a.grantee=0 AND a.privilege_type='CREATE')""").scalar_one()
    if safe is not True:
        raise ValueError('B2B SQL ownership/ACL/event policy mismatch')
    objects = set(connection.exec_driver_sql("SELECT tablename FROM pg_tables WHERE schemaname='public'").scalars())
    if empty:
        if objects:
            raise ValueError('Restore destination is not empty')
        # Refuse residual views, sequences, functions etc., not just tables.
        if connection.exec_driver_sql("SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace").scalar_one():
            raise ValueError('Restore destination has residual objects')
        if connection.exec_driver_sql("SELECT count(*) FROM pg_proc WHERE pronamespace='public'::regnamespace").scalar_one():
            raise ValueError('Restore destination has residual functions')
    else:
        expected = set(TABLES) | {'alembic_version'}
        if expected_revision != REVISION:
            expected |= {name.split('.')[1] for name in b2b.policy()['scope']}
        if objects != expected:
            raise ValueError('B2B live table set mismatch')
        sequences = set(connection.exec_driver_sql("SELECT sequencename FROM pg_sequences WHERE schemaname='public'").scalars())
        expected_sequences = {table + '_id_seq' for table in TABLES}
        if expected_revision != REVISION:
            expected_sequences |= {'local_users_id_seq', 'external_identities_id_seq', 'company_memberships_id_seq'}
        if sequences != expected_sequences:
            raise ValueError('B2B live sequence set mismatch')
        if not connection.exec_driver_sql("""SELECT bool_and(relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))
            FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','S')""").scalar_one():
            raise ValueError('B2B requires migration ownership of tables/sequences')
        if not connection.exec_driver_sql("SELECT has_column_privilege(current_user,'public.companies','id','REFERENCES')").scalar_one():
            raise ValueError('B2B REFERENCES missing')


def b2b_snapshot(connection):
    """Canonical private fingerprints: complete business rows, schema, ACL, sequences."""
    table_list = ','.join("'" + t + "'" for t in TABLES)  # fixed code constants only
    result = {}
    for table in TABLES:
        rows = connection.exec_driver_sql(f'SELECT row_to_json(t)::text FROM public.{table} t ORDER BY id').scalars()
        import hashlib
        digest = hashlib.sha256()
        count = 0
        for row in rows:
            raw = row.encode('utf-8')
            digest.update(len(raw).to_bytes(8, 'big') + raw)
            count += 1
        result[table] = {'count': count, 'sha256': digest.hexdigest()}
    catalog = f"""SELECT c.relname, c.relowner::regrole::text AS owner, c.relacl::text AS acl,
        c.relrowsecurity, c.relforcerowsecurity, a.attname, format_type(a.atttypid,a.atttypmod) AS type,
        a.attnotnull, pg_get_expr(d.adbin,d.adrelid) AS default_value
        FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE c.relnamespace='public'::regnamespace AND c.relname IN ({table_list})
        AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum"""
    constraints = f"""SELECT c.relname, k.conname, pg_get_constraintdef(k.oid,true) AS definition, k.convalidated
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
        WHERE c.relnamespace='public'::regnamespace AND c.relname IN ({table_list}) ORDER BY c.relname,k.conname"""
    indexes = f"""SELECT p.tablename,p.indexname,p.indexdef,i.indisvalid,i.indisready
        FROM pg_indexes p JOIN pg_class c ON c.relname=p.indexname AND c.relnamespace='public'::regnamespace
        JOIN pg_index i ON i.indexrelid=c.oid WHERE p.schemaname='public' AND p.tablename IN ({table_list})
        ORDER BY p.tablename,p.indexname"""
    triggers = f"""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid,true) AS definition
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        WHERE c.relnamespace='public'::regnamespace AND c.relname IN ({table_list}) AND NOT t.tgisinternal
        ORDER BY c.relname,t.tgname"""
    for key, query in (('columns', catalog), ('constraints', constraints), ('indexes', indexes), ('triggers', triggers)):
        result[key] = list(connection.exec_driver_sql('SELECT row_to_json(q)::text FROM (' + query + ') q').scalars())
    sequence_names = ','.join("'" + table + "_id_seq'" for table in TABLES)
    result['sequence_catalog'] = list(connection.exec_driver_sql(f"""SELECT row_to_json(q)::text FROM (
        SELECT s.sequencename,s.sequenceowner,s.data_type::text,s.start_value,s.min_value,s.max_value,
               s.increment_by,s.cycle,s.cache_size,c.relacl::text AS acl
        FROM pg_sequences s JOIN pg_class c ON c.relname=s.sequencename AND c.relnamespace='public'::regnamespace
        WHERE s.schemaname='public' AND s.sequencename IN ({sequence_names}) ORDER BY s.sequencename) q""").scalars())
    result['sequences'] = {}
    for table in TABLES:
        name = table + '_id_seq'
        state = connection.exec_driver_sql(f'SELECT last_value,is_called FROM public.{name}').one()
        result['sequences'][name] = list(state)
    return result


def b2b_receipt(directory, stage, plan, **values):
    receipt = {'format': 'dev-b2b-evidence-v1', 'stage': stage,
               'plan_sha256': b2b.digest(b2b.canonical(plan)),
               'created_at': datetime.now(timezone.utc).isoformat(), **values}
    # Exclusive creation: no overwriting a prior proof.
    with (directory / (stage + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
    return receipt


def b2b_pgtool(config, name, arguments):
    executable = shutil.which(name)
    if not executable:
        raise ValueError('PostgreSQL 17.10 client tool missing')
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, check=True).stdout
    if not re.search(r'\b17\.10\b', version):
        raise ValueError('PostgreSQL client version mismatch')
    transport = b2b.transport(config)
    url = db_url(config, 'migrator')
    # Password exists only in this child's environment, never argv/stdout.
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith('PG')}
    environment.update(PGPASSWORD=url.password, PGSSLMODE=transport['sslmode'],
                       PGSSLROOTCERT=transport['sslrootcert'], PGCONNECT_TIMEOUT='5',
                       PGOPTIONS='-c search_path=public -c timezone=UTC')
    try:
        result = subprocess.run([executable, '--host=127.0.0.1', '--port=5434',
                                 '--username=ui47_migrator', '--no-password', *arguments],
                                env=environment, capture_output=True, timeout=1800)
        if result.returncode:
            raise ValueError('PostgreSQL client failed; no automatic retry')
        return result.stdout
    finally:
        environment.pop('PGPASSWORD', None)


def b2b_backup(config, directory, target):
    plan, _ = b2b_plan(config, target)
    b2b.transport(config)
    directory = b2b.private_directory(config, directory, existing=False)
    if directory.exists():
        raise ValueError('Backup bundle already exists; never overwrite')
    b2b_confirm('BACKUP-B2B', plan)
    directory.mkdir(parents=False)  # private evidence parent and its ACL must preexist
    engine = b2b_engine(config)
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with connection.begin():
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                b2b_identity(connection, config, expected_revision=REVISION)
                before = b2b_snapshot(connection)
                exported = connection.exec_driver_sql('SELECT pg_export_snapshot()').scalar_one()
                archive = directory / 'before-b2b.dump'
                b2b_pgtool(config, 'pg_dump', ['--dbname=industrial_predict_dev', '--format=custom',
                                              '--snapshot=' + exported, '--file=' + str(archive)])
                toc = b2b_pgtool(config, 'pg_restore', ['--list', str(archive)])
                (directory / 'archive-toc.txt').write_bytes(toc)
                b2b_pgtool(config, 'pg_restore', ['--file=' + str(directory / 'archive-readback.sql'), str(archive)])
                if before != b2b_snapshot(connection):
                    raise ValueError('Source snapshot changed during backup')
        return b2b_receipt(directory, 'backup', plan, archive_sha256=b2b.file_digest(archive), snapshot=before)
    finally:
        engine.dispose()


def b2b_restore_config(config):
    # Separate preapproved, existing, empty database; no CREATE DATABASE/Docker operation.
    filename = Path(config['_directory']) / 'b2b-restore.json'
    restore = b2b.read_json(filename)
    if set(restore) != {'database', 'database_oid', 'instance_id', 'cluster_identifier'}:
        raise ValueError('Restore inventory invalid')
    if (restore['database'] != b2b.policy()['restore_database'] or
            type(restore['database_oid']) is not int or restore['database_oid'] <= 0 or
            restore['database_oid'] == config['database_oid'] or
            restore['instance_id'] == config['instance_id'] or
            not re.fullmatch(r'[0-9a-f-]{36}', restore['instance_id']) or
            restore['cluster_identifier'] != config['cluster_identifier']):
        raise ValueError('Restore destination overlaps DEV or mismatches inventory')
    return {**config, **restore}


def b2b_rehearse(config, directory, target):
    plan, _ = b2b_plan(config, target)
    directory = b2b.private_directory(config, directory)
    if (directory / 'restore.json').exists():
        raise ValueError('Restoration proof already exists; never repeat automatically')
    backup = b2b.read_json(directory / 'backup.json')
    archive = directory / 'before-b2b.dump'
    if backup['plan_sha256'] != b2b.digest(b2b.canonical(plan)) or backup['archive_sha256'] != b2b.file_digest(archive):
        raise ValueError('Backup does not match release/archive')
    instant = datetime.fromisoformat(backup['created_at'])
    from datetime import timedelta
    if (backup['format'] != 'dev-b2b-evidence-v1' or backup['stage'] != 'backup' or
            instant.tzinfo is None or not timedelta(0) <= datetime.now(timezone.utc) - instant <= timedelta(hours=24)):
        raise ValueError('Backup evidence invalid or expired')
    destination = b2b_restore_config(config)
    b2b.transport(destination)
    b2b_confirm('RESTORE-ISOLATED-B2B', plan, archive_hash=backup['archive_sha256'])
    engine = b2b_engine(destination)
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                b2b_identity(connection, destination, expected_revision=None, empty=True)
        # Explicit database argument; never --clean, --create or active DEV.
        b2b_pgtool(destination, 'pg_restore', ['--dbname=' + destination['database'],
                                            '--exit-on-error', '--single-transaction', str(archive)])
        with engine.connect() as connection:
            with connection.begin():
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                b2b_identity(connection, destination, expected_revision=REVISION)
                restored = b2b_snapshot(connection)
                if restored != backup['snapshot']:
                    raise ValueError('Restoration verification failed')
        if b2b.file_digest(archive) != backup['archive_sha256']:
            raise ValueError('Archive changed during rehearsal')
        return b2b_receipt(directory, 'restore', plan, archive_sha256=backup['archive_sha256'],
                           restored_snapshot=restored, verified=True,
                           database=destination['database'], database_oid=destination['database_oid'],
                           instance_id=destination['instance_id'])
    finally:
        engine.dispose()


def b2b_apply_release(connection, plan, bodies):
    """Alembic's own steps/version maintenance, with immutable reviewed bytes.

    Only called by migrate_b2b after live guards and the operator boundary.
    Generic env.py/INI remain disabled; no physical revision loader is installed.
    """
    policy = b2b.policy()
    if (plan['initial'] != REVISION or plan['target'] != policy['target'] or
            plan['sequence'] != policy['sequence'] or
            tuple(item[0] for item in bodies) != tuple(policy['sequence'])):
        raise ValueError('Execution sequence is not the approved B2B sequence')
    for revision, path, source in bodies:
        expected_path = next(p for p in policy['sources']
                             if p.startswith('general_migrations/versions/' + revision) and p.endswith('.py'))
        if path != expected_path or b2b.digest(source.encode()) != policy['sources'][path]:
            raise ValueError('Execution source is not the approved immutable publication')
    from types import ModuleType
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext, MigrationStep
    from alembic.script.base import Script
    from alembic.script.revision import RevisionMap
    root = ModuleType('dev_b2b_historical_marker')
    root.revision, root.down_revision, root.branch_labels, root.depends_on = REVISION, None, None, None
    scripts = [Script(root, REVISION, '<historical-marker-never-executed>')]
    for revision, path, source in bodies:
        module = ModuleType('dev_b2b_' + revision)
        exec(compile(source, '<approved:' + path + '>', 'exec'), module.__dict__)
        scripts.append(Script(module, revision, '<approved:' + path + '>'))
    revision_map = RevisionMap(lambda: iter(scripts))
    # RevisionMap is lazy: resolve the target before handing Script objects to
    # MigrationStep, which requires the graph's normalized dependency metadata.
    revision_map.get_revision(plan['target'])
    def steps(heads, context):
        if heads != (REVISION,):
            raise ValueError('Alembic starting heads changed')
        return [MigrationStep.upgrade_from_script(revision_map, s) for s in scripts[1:]]
    context = MigrationContext.configure(connection, opts={
        'fn': steps, 'target_metadata': None, 'transactional_ddl': True,
        'transaction_per_migration': False, 'version_table_schema': 'public'})
    with Operations.context(context):
        context.run_migrations()


def b2b_installed_shape(connection, plan):
    # Validate structure before commit. Reviewed sources plus no enabled event
    # triggers are essential: counts alone are not a schema equivalence proof.
    names = {n.split('.')[1] for n in plan['scope']}
    params = {'names': sorted(names)}
    constraints = connection.execute(text("""SELECT k.contype,count(*) AS amount,bool_and(k.convalidated) AS valid
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
        WHERE c.relnamespace='public'::regnamespace AND c.relname=ANY(:names)
        GROUP BY k.contype"""), params).all()
    if {kind: amount for kind, amount, valid in constraints if valid} != {'p': 6, 'u': 5, 'f': 7, 'c': 27}:
        raise ValueError('B2B constraint set invalid')
    indexes = connection.execute(text("""SELECT count(*),bool_and(i.indisvalid AND i.indisready)
        FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid
        WHERE c.relnamespace='public'::regnamespace AND c.relname=ANY(:names)"""), params).one()
    if tuple(indexes) != (16, True):
        raise ValueError('B2B index set invalid')
    columns = dict(connection.execute(text("""SELECT c.relname,count(*)
        FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
        WHERE c.relnamespace='public'::regnamespace AND c.relname=ANY(:names)
        AND a.attnum>0 AND NOT a.attisdropped GROUP BY c.relname"""), params).all())
    if columns != {'local_users': 2, 'external_identities': 4, 'company_memberships': 5,
                   'membership_permissions': 3, 'application_sessions': 13, 'oidc_transactions': 13}:
        raise ValueError('B2B column set invalid')
    for name in plan['scope']:
        if connection.exec_driver_sql('SELECT count(*) FROM ' + name).scalar_one() != 0:
            raise ValueError('Unexpected B2B provisioning')
        for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','TRIGGER','REFERENCES'):
            if connection.execute(text("SELECT has_table_privilege('ui47_app',:name,:privilege)"),
                                  {'name': name, 'privilege': privilege}).scalar_one():
                raise ValueError('Unexpected B2B runtime grant; provisioning is separate')


def b2b_verify_restore(config, backup, restored):
    """Receipts are claims: independently reread the isolated restoration now."""
    destination = b2b_restore_config(config)
    if any(destination[k] != restored[k] for k in ('database', 'database_oid', 'instance_id')):
        raise ValueError('Restore inventory changed')
    engine = b2b_engine(destination)
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with connection.begin():
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                b2b_identity(connection, destination, expected_revision=REVISION)
                if b2b_snapshot(connection) != backup['snapshot']:
                    raise ValueError('Isolated restore is no longer verified')
    finally:
        engine.dispose()


def migrate_b2b(config, directory, target):
    plan, bodies = b2b_plan(config, target)
    backup, restored = b2b.evidence(config, directory, plan)
    destination = b2b_restore_config(config)
    if any(destination[k] != restored[k] for k in ('database', 'database_oid', 'instance_id')):
        raise ValueError('Restore inventory changed')
    b2b.transport(config)
    b2b_confirm('MIGRATE-B2B', plan, archive_hash=backup['archive_sha256'])
    b2b_verify_restore(config, backup, restored)
    engine = b2b_engine(config)
    committed = False
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                connection.exec_driver_sql("SET LOCAL statement_timeout='60s'")
                connection.exec_driver_sql('SET LOCAL search_path=public')
                connection.exec_driver_sql("SET LOCAL timezone='UTC'")
                if not connection.exec_driver_sql('SELECT pg_try_advisory_xact_lock(474702,2)').scalar_one():
                    raise ValueError('Another DEV B2B operation is running')
                b2b_identity(connection, config, expected_revision=REVISION)
                connection.exec_driver_sql('LOCK TABLE ' + ','.join('public.' + t for t in (*TABLES, 'alembic_version')) + ' IN SHARE MODE')
                if b2b_snapshot(connection) != backup['snapshot']:
                    raise ValueError('DEV differs from restored backup; take a new backup')
                # Re-evaluate receipts immediately before invoking any DDL.
                b2b.evidence(config, directory, plan)
                b2b_apply_release(connection, plan, bodies)
                b2b_identity(connection, config, expected_revision=target)
                b2b_installed_shape(connection, plan)
                if b2b_snapshot(connection) != backup['snapshot']:
                    raise ValueError('Industrial preservation check failed')
            except BaseException:
                transaction.rollback()
                raise
            try:
                transaction.commit()
                committed = True
            except BaseException:
                raise b2b.CommitUncertain('B2B_COMMIT_UNCERTAIN; no retry or automatic restore') from None
        with engine.connect() as connection:
            with connection.begin():
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                b2b_identity(connection, config, expected_revision=target)
                b2b_installed_shape(connection, plan)
                if b2b_snapshot(connection) != backup['snapshot']:
                    raise ValueError('Post-commit preservation check failed')
        return {'stage': 'installed', 'revision': target, 'commit_confirmed': True}
    except Exception:
        if committed:
            raise b2b.PostcheckFailed('B2B_COMMIT_CONFIRMED_POSTCHECK_FAILED; keep DEV closed') from None
        raise
    finally:
        engine.dispose()


def prepare_runtime_app(config, *, profile=RUNTIME_MODE):
    """Prepare the existing SqlRuntime over one TLS engine, without DB/Google I/O.

    Do not import app.main/core.database: their legacy CRUD assembly and .env
    discovery are outside this preparation phase. Only diagnostics are mounted.
    """
    activation.require_preparation(config, profile)
    from fastapi import FastAPI
    from sqlalchemy.orm import sessionmaker
    sys.path.insert(0, str(REPO/'backend'))
    from app.core.database_runtime import SqlRuntime
    engine = runtime_engine(config)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.sql_runtime = SqlRuntime(engine, sessionmaker(bind=engine, autoflush=False, autocommit=False))
    from starlette.concurrency import run_in_threadpool
    from starlette.responses import JSONResponse

    def identity():
        with engine.connect() as connection:
            proof = inspect_runtime_connection(connection, config)
        return {'mode':'local-development',**proof}

    @app.middleware('http')
    async def enforce_target(request, call_next):
        try:
            await run_in_threadpool(identity)
        except Exception:
            return JSONResponse({'detail':'Development identity unavailable; request blocked'},status_code=503)
        response = await call_next(request)
        response.headers['X-Industrial-Predict-Environment'] = 'local-development'
        return response

    app.add_api_route('/__dev/identity', identity, methods=['GET'], include_in_schema=False)
    @app.get('/health')
    def health():
        return {'environment': config['mode'], 'status': 'healthy', 'runtime_mode': RUNTIME_MODE}
    return app


def api(config):
    activation.require_preparation(config)
    inspect_db(config)
    free_port(config['api_port'])
    app = prepare_runtime_app(config)
    import uvicorn
    try:
        uvicorn.run(app, host='127.0.0.1', port=config['api_port'], log_level='warning', access_log=False)
    finally:
        app.state.sql_runtime.dispose()


def frontend(config):
    activation.require_preparation(config)
    inspect_db(config)
    check_api(config)
    free_port(config['frontend_port'])
    environment = {**os.environ,'INDUSTRIAL_PREDICT_DEV_CONFIG':config['_path'],'CI':'1','NG_CLI_ANALYTICS':'false'}
    command = ['node','node_modules/@angular/cli/bin/ng.js','serve','--configuration=development',
               '--host=127.0.0.1',f"--port={config['frontend_port']}",'--open=false',
               '--proxy-config='+str(REPO/'infra/development/angular-proxy.cjs')]
    raise SystemExit(subprocess.call(command,cwd=REPO/'frontend',env=environment,stdin=subprocess.DEVNULL))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['check-db','check','migrate','api','frontend','db-start','db-stop',
                                        'b2b-preflight','b2b-backup','b2b-rehearse','b2b-migrate','b2b-auth-plan'])
    parser.add_argument('--config',required=True)
    parser.add_argument('--target', default='b2b_0002_analyze')
    parser.add_argument('--current-revision')
    parser.add_argument('--role', default='ui47_migrator')
    parser.add_argument('--bundle')
    parser.add_argument('--runtime-profile', choices=(activation.PREPARATION, activation.CANDIDATE),
                        default=activation.PREPARATION)
    args = parser.parse_args()
    if args.action == 'b2b-auth-plan':
        # Offline only: do not open the private profile, password, CA or engine.
        if args.role != activation.ROLE:
            parser.error('B2B auth plan requires explicit --role ui47_app')
        if args.target != RUNTIME_REVISION or args.current_revision not in (None, RUNTIME_REVISION) or args.bundle:
            parser.error('B2B auth plan accepts only the installed revision and no migration bundle')
        policy = b2b.policy()
        if Path(args.config).resolve() != Path(policy['profile']).resolve():
            parser.error('Activation plan requires the approved private profile path')
        report = activation.plan(profile=args.runtime_profile)
        report['destination'] = policy['destination']
        report['live_checks_performed'] = False
        report['plan_sha256'] = b2b.digest(b2b.canonical(report))
        print(json.dumps(report))
        return
    if args.runtime_profile != activation.PREPARATION:
        parser.error('Candidate profile cannot launch, migrate or access services')
    config = load_config(args.config)
    if args.action == 'b2b-preflight':
        if not args.current_revision:
            parser.error('b2b-preflight requires --current-revision (untrusted declaration)')
        print(json.dumps(b2b.report(config, current=args.current_revision, role=args.role, target=args.target)))
    elif args.action in ('b2b-backup','b2b-rehearse','b2b-migrate'):
        if args.role != 'ui47_migrator' or args.current_revision not in (None, REVISION) or not args.bundle:
            parser.error('B2B requires exact migrator, initial revision and explicit --bundle')
        operation = {'b2b-backup': b2b_backup, 'b2b-rehearse': b2b_rehearse, 'b2b-migrate': migrate_b2b}[args.action]
        result = operation(config, args.bundle, args.target)
        print(json.dumps({'stage': result['stage'], 'completed': True}))
    elif args.action == 'check-db': print(json.dumps(inspect_db(config)))
    elif args.action == 'check': print(json.dumps({'database':inspect_db(config),'api':check_api(config)}))
    elif args.action == 'migrate': migrate(config); print('Development migrations and runtime grants verified')
    elif args.action == 'api': api(config)
    elif args.action == 'frontend': frontend(config)
    elif args.action == 'db-start':
        verify_container(config)
        verify_volume(config)
        # Start the existing resource only. Provisioning/recreation is explicit maintenance.
        subprocess.run(compose_command(config,'start','--wait','--wait-timeout','60','postgres-ui47'),check=True)
        inspect_db(config)
    elif args.action == 'db-stop':
        verify_container(config)
        verify_volume(config)
        subprocess.run(compose_command(config,'stop','postgres-ui47'),check=True)


def cli():
    try:
        main()
        return 0
    except KeyboardInterrupt:
        return 0
    except b2b.CommitUncertain:
        print('Development STOP: B2B_COMMIT_UNCERTAIN. No retry or automatic restore.', file=sys.stderr)
        return 3
    except b2b.PostcheckFailed:
        print('Development STOP: B2B_COMMIT_CONFIRMED_POSTCHECK_FAILED. Keep DEV closed.', file=sys.stderr)
        return 4
    except Exception as error:
        print(f'Development STOP: {type(error).__name__}; configuration/identity check failed. No fallback.',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(cli())
