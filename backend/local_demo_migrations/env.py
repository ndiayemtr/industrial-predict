"""Online only, externally supplied owner transaction; never loads DEV settings."""

from alembic import context
from sqlalchemy import text

from app.p101_local_demo.provisioning import validate_connection
from app.p101_local_demo.setup_config import ROLES, SetupError, SetupSettings


def run():
    config = context.config
    settings = config.attributes.get('local_settings')
    connection = config.attributes.get('connection')
    if context.is_offline_mode() or type(settings) is not SetupSettings or connection is None:
        raise SetupError('Explicit online owner transaction required')
    if context.get_x_argument() or config.get_main_option('sqlalchemy.url'):
        raise SetupError('Alternate migration configuration forbidden')
    validate_connection(connection, settings, ROLES[1])
    connection.execute(text('SET LOCAL search_path TO public,pg_catalog'))
    context.configure(connection=connection, target_metadata=None, version_table='alembic_version',
                      version_table_schema='public', transaction_per_migration=False,
                      transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()


run()
