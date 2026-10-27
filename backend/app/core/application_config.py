"""Explicit SQL destination data only; no environment, files or SQL runtime."""

from ipaddress import ip_address
import re

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator, model_validator
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def _valid_host(host: str) -> bool:
    try:
        ip_address(host)
        return True
    except ValueError:
        labels = host.removesuffix(".").split(".")
        return len(host) <= 253 and all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in labels
        )


class ApplicationConfig(BaseModel):
    """Validated destination, not permission to connect or evidence of server identity.

    Only a complete postgresql+psycopg URL is supported. Query parameters (libpq
    services, alternate hosts, TLS options, etc.) are intentionally unsupported.
    Transport policy belongs to the future runtime, not to an implicit URL option.
    The URL is excluded from exports; deliberate access requires get_secret_value().
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    database_url: SecretStr = Field(repr=False, exclude=True)

    def __setattr__(self, name, value):
        # Frozen-model assignment errors otherwise retain the supplied value.
        raise TypeError("ApplicationConfig is immutable")

    @model_validator(mode="wrap")
    @classmethod
    def _redact_validation_errors(cls, data, handler):
        try:
            return handler(data)
        except ValidationError:
            pass
        # hide_input_in_errors alone does not protect errors() or json(). Discard
        # original inputs, locations (unknown keys can be sensitive), and context.
        # Raise outside the except block to avoid retaining the original exception.
        raise ValidationError.from_exception_data(
            cls.__name__,
            [{"type": "value_error", "loc": (), "input": "[redacted]",
              "ctx": {"error": ValueError("Invalid explicit application configuration")}}],
            hide_input=True,
        ) from None

    @field_validator("database_url")
    @classmethod
    def _complete_postgresql_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        valid = False
        try:
            url = make_url(raw)
            valid = (
                not any(ord(c) < 32 or ord(c) == 127 for c in raw)
                and url.drivername == "postgresql+psycopg"
                and bool(url.host) and _valid_host(url.host)
                and type(url.port) is int and 1 <= url.port <= 65535
                and all(isinstance(part, str) and part and part == part.strip()
                        and len(part.encode("utf-8")) <= 63
                        for part in (url.username, url.database))
                and isinstance(url.password, str) and bool(url.password.strip())
                and not any(ord(c) < 32 or ord(c) == 127
                            for part in (url.username, url.database, url.password) for c in part)
                and not url.query
            )
        except (ArgumentError, ValueError, TypeError, UnicodeError):
            pass
        if not valid:
            raise ValueError("Invalid explicit SQL destination")
        return value
