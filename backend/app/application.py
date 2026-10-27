"""Explicit, route-free FastAPI assembly, independent of the historical backend."""

from fastapi import FastAPI

from app.core.application_config import ApplicationConfig
from app.core.database_lifespan import create_sql_lifespan
from app.core.database_runtime import SqlRuntime


class ApplicationFactoryError(ValueError):
    """Application assembly/binding error containing a constant diagnostic only."""


def create_app(
    *,
    config: ApplicationConfig | None = None,
    runtime: SqlRuntime | None = None,
    title: str = "Industrial Predict AI API",
    version: str = "0.1.0",
    description: str = "API de maintenance prédictive industrielle",
) -> FastAPI:
    """Prepare an independent application; SQL resources start only in its lifespan."""
    if (type(title) is not str or not title.strip()
            or type(version) is not str or not version.strip()
            or type(description) is not str):
        raise ApplicationFactoryError("INVALID_API_METADATA")
    # Input exclusivity, SQL validation, ownership and cleanup belong to the
    # existing lifespan. Do not create a second runtime or duplicate its rules.
    lifespan = create_sql_lifespan(config=config, runtime=runtime)
    return FastAPI(
        title=title,
        version=version,
        description=description,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )


def assert_sql_runtime_binding(app: FastAPI, *, expected_runtime: SqlRuntime) -> None:
    """Compare object identity with an independently retained expected reference.

    Callers must not obtain the expected reference from the slot being checked.
    This checks wiring only, not availability, SQL destination, identity or TLS.
    """
    matches = False
    try:
        if isinstance(app, FastAPI) and type(expected_runtime) is SqlRuntime:
            actual = app.state.sql_runtime
            matches = type(actual) is SqlRuntime and actual is expected_runtime
    except Exception:
        matches = False
    if not matches:
        raise ApplicationFactoryError("SQL_RUNTIME_BINDING_MISMATCH") from None
