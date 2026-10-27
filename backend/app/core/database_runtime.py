"""Opt-in synchronous SQL runtime; importing this module creates no resources."""

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.application_config import ApplicationConfig
from app.core.config_loader import ConfigurationError, load_application_config


class SqlRuntimeError(RuntimeError):
    """Runtime lifecycle failure without connection inputs or driver exceptions."""


class SqlRuntime:
    """Own one engine and create a fresh session for each explicit operation.

    Use ``with runtime.session() as db`` and commit explicitly if appropriate.
    Dispose after operations finish: SQLAlchemy disposal does not forcibly close
    checked-out connections. Neither construction nor session creation connects.
    This component does not authorize a destination or verify server identity/TLS.
    """

    def __init__(self, engine: Engine, factory: sessionmaker[Session]):
        self._engine = engine
        self._factory = factory
        self._closed = False

    @property
    def engine(self) -> Engine:
        return self._engine

    @contextmanager
    def session(self) -> Iterator[Session]:
        if self._closed:
            raise SqlRuntimeError("SQL runtime is closed")
        db = self._factory()
        try:
            yield db
        finally:
            db.close()  # No commit, including on successful exit.

    def dispose(self) -> None:
        # Block new sessions even if engine disposal fails. A caller may retry
        # disposal explicitly; no automatic reconnect or resource recreation.
        self._closed = True
        try:
            self._engine.dispose()
            return
        except Exception:
            pass
        raise SqlRuntimeError("SQL engine disposal failed") from None


def create_sql_runtime(config: ApplicationConfig) -> SqlRuntime:
    """Explicitly create an engine/pool and session factory, without checking out a connection."""
    if type(config) is not ApplicationConfig:
        raise ConfigurationError("Validated ApplicationConfig required")
    # model_construct()/model_copy(update=...) can bypass Pydantic validation.
    # Revalidate fields explicitly; model_dump() deliberately excludes the URL.
    validated = load_application_config(dict(config))
    url = make_url(validated.database_url.get_secret_value())
    engine = None
    try:
        engine = create_engine(url, pool_pre_ping=True, echo=False, hide_parameters=True)
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        return SqlRuntime(engine, factory)
    except Exception:
        pass
    cleanup_failed = False
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            cleanup_failed = True
    if cleanup_failed:
        raise SqlRuntimeError("SQL runtime construction and cleanup failed") from None
    raise SqlRuntimeError("SQL runtime construction failed") from None
