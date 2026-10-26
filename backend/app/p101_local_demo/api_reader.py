"""Explicit reader connection only. No engine, secret lookup or connection on import."""

from contextlib import contextmanager
import os

from app.p101_local_demo.setup_config import ROLES, REVISION, SetupSettings, read_secret


class ApiReadError(ValueError):
    pass


class ApiQueryError(ValueError):
    pass


class ApiReferenceNotFound(LookupError):
    pass


def validate_api_settings(settings, role=ROLES[3]):
    if type(settings) is not SetupSettings or role != ROLES[3]:
        raise ApiReadError('EXPLICIT_P101_READER_REQUIRED')
    settings.validate()
    destination = settings.destination(role)
    destination.validate()
    if destination.schema_revision != REVISION or any(k.startswith('PG') for k in os.environ):
        raise ApiReadError('IMPLICIT_CONFIGURATION_REJECTED')
    return destination


@contextmanager
def reader_connection(settings, role=ROLES[3]):
    destination = validate_api_settings(settings, role)
    # Imports are deferred until after explicit settings validation. No ORM or DEV module.
    from sqlalchemy import URL, create_engine, text
    from sqlalchemy.pool import NullPool
    from app.p101_local_demo.provisioning import validate_connection
    from app.p101_local_demo.reader import IDENTITY_SQL, validate_identity, validate_transport
    from app.p101_persistence.contracts import FIXTURE_SHA256

    engine = create_engine(URL.create('postgresql+psycopg', username=role,
        password=read_secret(settings, role), host=settings.host, port=settings.port, database=settings.database),
        connect_args={'sslmode':'disable', 'connect_timeout':5,
            'options':'-c timezone=UTC -c search_path=pg_catalog -c default_transaction_read_only=on'},
        isolation_level='READ COMMITTED', poolclass=NullPool, hide_parameters=True, echo=False)
    try:
        with engine.connect() as connection:
            tx = connection.begin()
            try:
                validate_connection(connection, settings, role)
                validate_transport(connection, destination)
                validate_identity(destination, connection.execute(IDENTITY_SQL).mappings().one())
                if connection.execute(text('SHOW transaction_read_only')).scalar_one() != 'on':
                    raise ApiReadError('READ_ONLY_TRANSACTION_REQUIRED')
                guard = connection.execute(text("""
                    SELECT fixture_sha256,
                     has_table_privilege(current_user,'public.prediction_records','SELECT')
                     AND NOT has_table_privilege(current_user,'public.prediction_records',
                       'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                     AND NOT has_any_column_privilege(current_user,'public.prediction_records',
                       'INSERT,UPDATE,REFERENCES') AS predictions_read_only,
                     NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='p101_local_owner' AND rolcanlogin) AS owner_closed
                    FROM local_demo.environment WHERE singleton
                """)).mappings().one()
                if (guard['fixture_sha256'] != FIXTURE_SHA256 or guard['predictions_read_only'] is not True
                        or guard['owner_closed'] is not True):
                    raise ApiReadError('READER_PRIVILEGES_OR_MARKER_REJECTED')
                yield connection
            finally:
                if tx.is_active:
                    tx.rollback()  # No commit on GET, including successful responses.
    finally:
        engine.dispose()
