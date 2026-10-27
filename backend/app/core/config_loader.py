"""Validate caller-supplied data; no file, environment or connection discovery."""

from pydantic import ValidationError

from app.core.application_config import ApplicationConfig


class ConfigurationError(ValueError):
    """Sanitized configuration failure, without supplied values or driver errors."""


def load_application_config(source: dict[str, object]) -> ApplicationConfig:
    """Accept one explicit plain dictionary, never a path, DSN string or callable.

    No secret file is opened. The caller must supply the destination itself;
    historical settings, ambient environment and defaults are never consulted.
    """
    if type(source) is not dict:
        raise ConfigurationError("Explicit configuration dictionary required")
    try:
        return ApplicationConfig.model_validate(source)
    except ValidationError:
        pass
    raise ConfigurationError("Invalid explicit application configuration") from None
