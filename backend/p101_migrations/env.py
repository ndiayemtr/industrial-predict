"""Opt-in pilot migration, with typed independent administrative approval."""

from alembic import context
from app.p101_postgres.administration import AdminAction, run_migration_environment


run_migration_environment(context, AdminAction.PILOT)
