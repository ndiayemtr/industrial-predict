"""Explicit future setup operations. Importing this module does not open a connection."""

from contextlib import contextmanager
import os

from sqlalchemy import URL, create_engine, text

from app.p101_local_demo.contracts import DATABASE, PURPOSE
from app.p101_local_demo.setup_config import (
    CLUSTER, CORE_FILES, REVISION, ROOT, ROLES, SetupError, read_secret,
)


IDENTITY = text("""
SELECT current_database() AS database, session_user::text AS session_role,
 current_user::text AS effective_role, host(inet_server_addr()) AS server_address,
 inet_server_port() AS server_port, current_setting('cluster_name') AS cluster,
 current_setting('server_encoding') AS encoding,
 current_setting('transaction_isolation') AS isolation,
 to_regnamespace('p101_pilot') IS NULL AS no_protected_schema,
 NOT EXISTS (SELECT 1 FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.member
             WHERE r.rolname=current_user) AS no_memberships,
 r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolbypassrls
FROM pg_roles r WHERE r.rolname=current_user
""")
BUSINESS = ('companies', 'sites', 'equipments', 'sensors', 'measurements',
            'maintenance_records', 'prediction_records', 'maintenance_recommendations')
LOCK = 1010053


def require_execution(settings, execute, instance):
    settings.validate()
    if execute is not True or instance != settings.instance_uuid:
        raise SetupError("Explicit execution and matching instance acknowledgement required")


def validate_connection(connection, settings, role):
    """Checks a supplied connection before any DDL/DML. SELECT identity only."""
    settings.validate()
    if role not in ROLES or any(k.startswith('PG') for k in os.environ):
        raise SetupError("Explicit local transport required")
    try:
        url = connection.engine.url
        driver = connection.connection.driver_connection
        if (url.drivername != 'postgresql+psycopg' or url.host != settings.host
                or url.port != settings.port or url.database != DATABASE or url.username != role
                or driver.info.host != settings.host or driver.info.port != settings.port
                or driver.info.dbname != DATABASE or driver.info.user != role
                or driver.info.get_parameters().get('sslmode') != 'disable'
                or driver.pgconn.ssl_in_use is not False or not connection.in_transaction()):
            raise SetupError("Wrong local transport")
        row = connection.execute(IDENTITY).mappings().one()
        expected = dict(database=DATABASE, session_role=role, effective_role=role,
            server_address=settings.server_address, server_port=5432, cluster=CLUSTER,
            encoding='UTF8', isolation='read committed', no_protected_schema=True, no_memberships=True)
        if role != ROLES[0]:
            expected.update({k: False for k in ('rolsuper', 'rolcreatedb', 'rolcreaterole', 'rolreplication', 'rolbypassrls')})
        else:
            expected['rolsuper'] = True  # Dedicated new-cluster bootstrap administrator only.
        if any(type(row.get(k)) is not type(v) or row.get(k) != v for k, v in expected.items()):
            raise SetupError("Wrong local instance or role")
    except Exception:
        raise SetupError("Local destination verification failed") from None


@contextmanager
def transaction(settings, role, *, execute=False, instance=None):
    require_execution(settings, execute, instance)
    if role not in ROLES or any(k.startswith('PG') for k in os.environ):
        raise SetupError("Implicit libpq configuration forbidden")
    # No URL/.env/settings lookup. URL.create also avoids interpolation of passwords.
    engine = create_engine(URL.create('postgresql+psycopg', username=role,
        password=read_secret(settings, role), host=settings.host, port=settings.port, database=DATABASE),
        connect_args={'sslmode': 'disable', 'connect_timeout': 5,
                      'options': '-c timezone=UTC -c search_path=pg_catalog'},
        isolation_level='READ COMMITTED', hide_parameters=True, echo=False)
    try:
        with engine.connect() as connection:
            with connection.begin():
                validate_connection(connection, settings, role)
                yield connection
    except Exception:
        # A failure during COMMIT may be uncertain: never retry or claim rollback certainty.
        raise SetupError("Operation failed; inspect instance before retry (commit may be uncertain)") from None
    finally:
        engine.dispose()


def lock(connection):
    connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': LOCK})


def marker(connection, settings):
    rows = connection.execute(text('SELECT * FROM local_demo.environment FOR UPDATE')).mappings().all()
    if len(rows) != 1:
        raise SetupError("One local instance marker required")
    row = rows[0]
    expected = dict(instance_uuid=settings.instance_uuid, purpose=PURPOSE,
                    database_name=DATABASE, schema_revision=REVISION)
    if row.get('singleton') is not True or any(str(row.get(k)) != v for k, v in expected.items()):
        raise SetupError("Local marker mismatch")
    version = connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars().all()
    if version != [REVISION]:
        raise SetupError("Local revision mismatch")
    return row


def require_empty_database(connection):
    if connection.execute(text("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')""")).scalar_one() != 0:
        raise SetupError("Fresh public schema required; existing objects cannot be adopted")
    if connection.execute(text("SELECT to_regnamespace('local_demo') IS NOT NULL")).scalar_one():
        raise SetupError("Unexpected local schema")


def create_roles(connection, settings):
    """Future admin-only operation, atomic roles/grants, no adoption or password reset."""
    validate_connection(connection, settings, ROLES[0])
    lock(connection)
    require_empty_database(connection)
    existing = connection.execute(text('SELECT rolname FROM pg_roles WHERE rolname IN (:o,:w,:r)'),
        dict(o=ROLES[1], w=ROLES[2], r=ROLES[3])).scalars().all()
    if existing:
        raise SetupError("Local roles already exist; inspect rather than overwrite")
    secrets = {r: read_secret(settings, r) for r in ROLES}
    if len(set(secrets.values())) != 4:
        raise SetupError("Four distinct private secrets required")
    # PostgreSQL utility statements do not accept ordinary bind parameters for role names/passwords.
    # psycopg composition safely quotes both; no SQL or exception text is printed.
    from psycopg import sql
    with connection.connection.driver_connection.cursor() as cursor:
        for role in ROLES[1:]:
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                'NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}').format(
                    sql.Identifier(role), sql.Literal(secrets[role])))
    connection.execute(text(f'ALTER DATABASE {DATABASE} OWNER TO {ROLES[1]}'))
    connection.execute(text(f'REVOKE ALL ON DATABASE {DATABASE} FROM PUBLIC'))
    connection.execute(text(f'GRANT CONNECT ON DATABASE {DATABASE} TO ' + ','.join(ROLES)))
    connection.execute(text('REVOKE ALL ON SCHEMA public FROM PUBLIC'))
    connection.execute(text(f'GRANT USAGE,CREATE ON SCHEMA public TO {ROLES[1]}'))


def alembic_config(connection, settings):
    from alembic.config import Config
    versions = ROOT / 'backend/migrations/versions'
    if {p.name for p in versions.glob('*.py')} != set(CORE_FILES):
        raise SetupError("Unexpected business migration set")
    config = Config(str(ROOT / 'backend/local_demo_migrations/alembic.ini'))
    config.set_main_option('version_locations', os.pathsep.join((str(versions),
        str(ROOT / 'backend/local_demo_migrations/versions'))))
    config.attributes.update(connection=connection, local_settings=settings)
    return config


def migrate(connection, settings):
    from alembic import command
    validate_connection(connection, settings, ROLES[1])
    lock(connection)
    if connection.execute(text("SELECT to_regnamespace('local_demo') IS NOT NULL")).scalar_one():
        marker(connection, settings)
    else:
        require_empty_database(connection)
    command.upgrade(alembic_config(connection, settings), REVISION)


def runtime_grants(connection):
    connection.execute(text('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC'))
    connection.execute(text('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC'))
    connection.execute(text('REVOKE ALL ON SCHEMA local_demo FROM PUBLIC'))
    for role in ROLES[2:]:
        connection.execute(text(f'GRANT USAGE ON SCHEMA public,local_demo TO {role}'))
        for table in BUSINESS[:5] + ('prediction_records', 'alembic_version'):
            connection.execute(text(f'GRANT SELECT ON public.{table} TO {role}'))
        connection.execute(text(f'GRANT SELECT ON local_demo.environment TO {role}'))
    connection.execute(text(f'GRANT INSERT ON public.prediction_records TO {ROLES[2]}'))
    connection.execute(text(f'GRANT USAGE ON SEQUENCE public.prediction_records_id_seq TO {ROLES[2]}'))


def seal(connection, settings):
    validate_connection(connection, settings, ROLES[0])
    lock(connection)
    row = marker(connection, settings)
    if row['bootstrap_closed'] is not True or not row['bootstrap_sha256']:
        raise SetupError("Validated closed bootstrap required before disabling owner login")
    connection.execute(text(f'ALTER ROLE {ROLES[1]} NOLOGIN'))
