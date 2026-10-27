"""Explicit FastAPI session dependency; no historical configuration or runtime."""

from collections.abc import Iterator
from contextlib import ExitStack

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database_runtime import SqlRuntime


def get_db(request: Request) -> Iterator[Session]:
    """Borrow this application's runtime; close its operation session, never its engine."""
    with ExitStack() as sessions:
        try:
            runtime = request.app.state.sql_runtime
            if type(runtime) is not SqlRuntime:
                raise TypeError("Explicit SqlRuntime required")
            db = sessions.enter_context(runtime.session())
        except Exception:
            pass
        else:
            # Outside the acquisition try: handler/cleanup exceptions propagate
            # unchanged through the session context manager, never as HTTP 503.
            yield db
            return
        # Outside the except block: do not retain a sensitive acquisition cause.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SQL_RUNTIME_UNAVAILABLE",
        ) from None
