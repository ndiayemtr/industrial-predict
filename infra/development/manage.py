"""Explicit local development tooling, separate from normal API/Angular startup."""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from urllib.request import urlopen

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

REPO = Path(__file__).resolve().parents[2]
REVISION = '09ac8101e9fe'
SOURCE_CLUSTER = '7673083456081215526'
TABLES = ('companies', 'sites', 'equipments', 'sensors', 'measurements',
          'maintenance_records', 'prediction_records', 'maintenance_recommendations')


def load_config(filename):
    path = Path(filename).resolve(strict=True)
    if path.is_relative_to(REPO):
        raise ValueError('Private configuration must be outside Git')
    config = json.loads(path.read_text(encoding='utf-8'))
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


def inspect_connection(connection, config, role='app', revision=True):
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
        if proof['revision'] != REVISION:
            raise ValueError('Development migration mismatch')
    return proof


def inspect_db(config):
    engine = create_engine(db_url(config, 'app'), connect_args={'connect_timeout': 3}, echo=False)
    try:
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.exec_driver_sql('BEGIN TRANSACTION READ ONLY')
            try:
                result = inspect_connection(connection, config)
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
                sequences = connection.execute(text("SELECT sequencename FROM pg_sequences WHERE schemaname='public'")).scalars().all()
                result['sequence_usage_only'] = len(sequences) == len(TABLES) and all(
                    connection.execute(text("SELECT has_sequence_privilege(current_user,:name,'USAGE') AND NOT has_sequence_privilege(current_user,:name,'SELECT') AND NOT has_sequence_privilege(current_user,:name,'UPDATE')"),
                                       {'name':'public.'+name}).scalar_one() for name in sequences)
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
    if proof.get('mode') != config['mode'] or proof.get('database') != config['database'] or proof.get('instance_id') != config['instance_id'] or proof.get('role') != 'ui47_app' or proof.get('revision') != REVISION or proof.get('superuser') is not False:
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


def api(config):
    inspect_db(config)
    free_port(config['api_port'])
    os.environ['DATABASE_URL'] = db_url(config, 'app').render_as_string(hide_password=False)
    os.environ['APP_ENV'] = 'local-development'
    os.environ['DEBUG'] = 'false'
    sys.path.insert(0, str(REPO/'backend'))
    os.chdir(REPO/'backend')
    from app.main import app
    from app.core.database import engine
    if engine.url != db_url(config, 'app'):
        raise ValueError('API engine differs from development configuration')
    from starlette.concurrency import run_in_threadpool
    from starlette.responses import JSONResponse
    import uvicorn

    def identity():
        with engine.connect() as connection:
            proof = inspect_connection(connection, config)
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
    uvicorn.run(app, host='127.0.0.1', port=config['api_port'], log_level='warning', access_log=False)


def frontend(config):
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
    parser.add_argument('action',choices=['check-db','check','migrate','api','frontend','db-start','db-stop'])
    parser.add_argument('--config',required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.action == 'check-db': print(json.dumps(inspect_db(config)))
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


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f'Development STOP: {type(error).__name__}; configuration/identity check failed. No fallback.',file=sys.stderr)
        raise SystemExit(2)
