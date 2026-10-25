"""Opt-in sandbox migration entry. No engine, URL fallback or offline execution."""

from alembic import context
from sqlalchemy import text

from app.p101_postgres.runtime import CORE_REVISION, SandboxConfig, GuardRejected


def run():
    if context.is_offline_mode():
        raise GuardRejected("Offline migration execution is disabled")
    cfg = context.config
    connection = cfg.attributes.get("p101_connection")
    policy = cfg.attributes.get("p101_config")
    approve = cfg.attributes.get("p101_authorize_migration")
    if connection is None or type(policy) is not SandboxConfig or not callable(approve):
        raise GuardRejected("Explicit connection, policy and independent migration verifier required")
    policy.validate()
    if connection.in_transaction():
        raise GuardRejected("Migration requires a fresh dedicated connection")
    with connection.begin():
        identity = connection.execute(text("""
          SELECT current_database() AS database, session_user::text AS session_role,
            current_user::text AS effective_role,inet_server_addr()::text AS address,
            inet_server_port() AS port,
            (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS ssl,
            (SELECT version_num FROM public.alembic_version) AS core_revision
        """)).mappings().one()
        url = connection.engine.url
        if (identity["database"] != policy.destination.database
                or identity["session_role"] != policy.owner_role or identity["effective_role"] != policy.owner_role
                or identity["address"] != policy.server_address or identity["port"] != policy.server_port
                or identity["ssl"] is not True or identity["core_revision"] != CORE_REVISION
                or url.host != policy.destination.host or url.port != policy.destination.port
                or url.database != policy.destination.database):
            raise GuardRejected("Effective migration destination rejected")
        # This verifier must authenticate a separate ADMIN migration permission,
        # never an offline preparation or the ordinary pair-write approval.
        if approve(connection, policy) is not True:
            raise GuardRejected("Migration not independently authorized")
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS p101_pilot"))
        context.configure(connection=connection, target_metadata=None,
                          version_table="alembic_version", version_table_schema="p101_pilot")
        with context.begin_transaction():
            context.run_migrations()


run()
