"""Opt-in session factory: no configuration discovery and no import-time engine."""

import os
import json
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

from app.p101_postgres.runtime import SandboxConfig


def create_session_factory(config: SandboxConfig):
    """Does not connect. Calling the returned factory is an operational action.

    Never called with a real engine by the B-1 tests. verify-full is mandatory;
    no DATABASE_URL, .env, passfile or service name is accepted as configuration.
    """
    config.validate()
    if any(name.startswith("PG") for name in os.environ):
        raise ValueError("Implicit libpq environment configuration is forbidden")
    url = URL.create("postgresql+psycopg", username=config.destination.role,
        password=config.password, host=config.destination.host, port=config.destination.port,
        database=config.destination.database)
    engine = create_engine(url, isolation_level="READ COMMITTED", pool_pre_ping=True,
        hide_parameters=True, echo=False,
        json_serializer=lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        connect_args={"sslmode": "verify-full", "sslrootcert": config.tls_root_certificate,
                      "connect_timeout": 3, "application_name": "p101-persistence", "client_encoding": "UTF8",
                      "options": "-c search_path=pg_catalog -c timezone=UTC -c lock_timeout=5000 -c statement_timeout=15000"})
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
