"""Opt-in FastAPI lifecycle for an explicitly owned or borrowed SQL runtime."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from app.core.application_config import ApplicationConfig
from app.core.config_loader import load_application_config
from app.core.database_runtime import SqlRuntime, create_sql_runtime


_MARKER = "_sql_runtime_lifespan_token"
_MISSING = object()


class SqlLifespanError(RuntimeError):
    """Lifecycle errors contain constant codes only, never configuration/driver data."""


def _runtime_is_open(runtime: SqlRuntime) -> bool:
    # Temporary coupling: SqlRuntime has no public closed indicator yet.
    # Never modify _closed or open a probe session to determine availability.
    return type(runtime) is SqlRuntime and getattr(runtime, "_closed", None) is False


def _cleanup(app, token, current, owned, installed) -> tuple[str, ...]:
    problems = []
    try:
        observed = getattr(app.state, "sql_runtime", _MISSING)
        if current is not None and observed is current:
            del app.state.sql_runtime
        elif observed is not _MISSING or installed:
            # Never remove or dispose a replacement installed by another component.
            problems.append("SQL_LIFESPAN_STATE_CONFLICT")
    except Exception:
        problems.append("SQL_LIFESPAN_STATE_CLEANUP_FAILED")
    if owned and type(current) is SqlRuntime:
        try:
            current.dispose()  # Exactly one attempt, after detachment.
        except Exception:
            problems.append("SQL_RUNTIME_DISPOSE_FAILED")
    try:
        if getattr(app.state, _MARKER, _MISSING) is token:
            delattr(app.state, _MARKER)
        else:
            problems.append("SQL_LIFESPAN_ACTIVATION_CONFLICT")
    except Exception:
        problems.append("SQL_LIFESPAN_MARKER_CLEANUP_FAILED")
    return tuple(problems)


def create_sql_lifespan(
    *,
    config: ApplicationConfig | None = None,
    runtime: SqlRuntime | None = None,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Prepare a lifespan without creating any SQL resource.

    Exactly one input is required. Config selects ownership; a supplied runtime
    remains the caller's property and must stay open throughout the loan. A
    lifespan cannot be active concurrently, even for two different applications.
    Separate lifespans support independent applications. Shutdown assumes active
    requests have drained; dispose does not forcibly terminate their sessions.
    """
    if (config is None) == (runtime is None):
        raise SqlLifespanError("SQL_LIFESPAN_EXACTLY_ONE_INPUT_REQUIRED")
    owned = config is not None
    if owned:
        if type(config) is not ApplicationConfig:
            raise SqlLifespanError("SQL_LIFESPAN_INVALID_CONFIG_TYPE")
        config = load_application_config(dict(config))
    elif type(runtime) is not SqlRuntime:
        raise SqlLifespanError("SQL_LIFESPAN_INVALID_RUNTIME_TYPE")
    active = False

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal active
        if active:
            raise SqlLifespanError("SQL_LIFESPAN_ALREADY_ACTIVE")
        if hasattr(app.state, "sql_runtime") or hasattr(app.state, _MARKER):
            raise SqlLifespanError("SQL_LIFESPAN_STATE_ALREADY_RESERVED")
        token = object()
        current = None
        installed = False
        primary = None
        active = True
        try:
            # State mutation failures are sanitized, including a setter that
            # installs a value before raising. The finally block still cleans up.
            activation_failed = False
            try:
                setattr(app.state, _MARKER, token)
            except Exception:
                activation_failed = True
            if activation_failed:
                raise SqlLifespanError("SQL_LIFESPAN_ACTIVATION_FAILED")
            if owned:
                creation_failed = False
                try:
                    current = create_sql_runtime(config)
                except Exception:
                    creation_failed = True
                if creation_failed:
                    # The runtime factory owns cleanup of any engine it did not return.
                    raise SqlLifespanError("SQL_LIFESPAN_RUNTIME_CREATION_FAILED")
            else:
                current = runtime
            if not _runtime_is_open(current):
                raise SqlLifespanError("SQL_LIFESPAN_RUNTIME_CLOSED_OR_INVALID")
            if (hasattr(app.state, "sql_runtime")
                    or getattr(app.state, _MARKER, _MISSING) is not token):
                raise SqlLifespanError("SQL_LIFESPAN_STARTUP_STATE_CONFLICT")
            installation_failed = False
            try:
                app.state.sql_runtime = current
                installed = True
            except Exception:
                installation_failed = True
            if installation_failed:
                raise SqlLifespanError("SQL_LIFESPAN_INSTALLATION_FAILED")
            yield
        except BaseException as error:
            primary = error
            raise
        finally:
            problems = _cleanup(app, token, current, owned, installed)
            active = False
            if problems:
                diagnostic = "SQL_LIFESPAN_CLEANUP_FAILED: " + ",".join(problems)
                if primary is not None:
                    primary.add_note(diagnostic)  # Preserve the primary exception and report cleanup too.
                else:
                    raise SqlLifespanError(diagnostic)

    return lifespan
