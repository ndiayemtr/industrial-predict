"""Opt-in guarded general revisions on an explicitly supplied owner connection."""

from alembic import context
from app.p101_postgres.administration import AdminAction, run_migration_environment


run_migration_environment(context, AdminAction.CORE)
