"""Reserved execution boundary: no configured general approval authority yet.

Even an injected connection or a well-formed declaration cannot enable this
environment. Never configure Alembic, load models or touch a connection here.
"""

from app.general_migrations import MigrationExecutionDisabled


target_metadata = None

raise MigrationExecutionDisabled()
