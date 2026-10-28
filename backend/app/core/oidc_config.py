"""Explicit OIDC policy data only; no discovery, client or cryptographic checks.

Only trusted server configuration may supply this model. An accepted URL is an
approved configuration value, not evidence of server identity or reachability.
Future consumers must revalidate data: Pydantic model_construct/model_copy can
bypass validation. No secret or provider-specific business policy belongs here.
"""

from ipaddress import ip_address
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


# Deliberately conservative v1 profile; additions require explicit review.
ACCEPTED_SIGNATURE_ALGORITHMS = ("RS256", "PS256", "ES256")
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


def _url_parts(raw: str):
    """Reject ambiguous URL spellings instead of normalizing identity values."""
    if (not raw or len(raw) > 2048 or not raw.isascii()
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in raw)
            or re.search(r"[^A-Za-z0-9:/\[\]._~!$&'()+,=\-]", raw)):
        raise ValueError("Invalid OIDC URL")
    parts = urlsplit(raw)
    if (not raw.startswith(parts.scheme + "://") or parts.scheme not in ("https", "http")
            or not parts.netloc or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment):
        raise ValueError("Invalid OIDC URL")
    host = parts.hostname
    try:
        ip_address(host)
    except ValueError:
        if (len(host) > 253 or host.endswith(".") or re.fullmatch(r"[0-9.]+", host)
                or not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                           for label in host.split("."))):
            raise ValueError("Invalid OIDC host")
    # Explicit ports use canonical decimal syntax; no empty, signed or zero port.
    authority = parts.netloc
    if authority.startswith("["):
        if ":" not in host:
            raise ValueError("Only IPv6 bracketed hosts are supported")
        suffix = authority[authority.index("]") + 1:]
    else:
        suffix = ":" + authority.split(":", 1)[1] if ":" in authority else ""
    if suffix and (not re.fullmatch(r":[1-9][0-9]{0,4}", suffix)
                   or parts.port is None or not 1 <= parts.port <= 65535):
        raise ValueError("Invalid OIDC port")
    if (parts.path and not parts.path.startswith("/")) or "//" in parts.path:
        raise ValueError("Invalid OIDC path")
    if any(segment in (".", "..") for segment in parts.path.split("/")):
        raise ValueError("Invalid OIDC path")
    return parts


class OidcConfig(BaseModel):
    """Immutable configuration, independent of environment and SQL runtime.

    HTTPS issuer is mandatory in every mode. HTTP callback is allowed only in
    development, with a separate explicit opt-in, exact loopback host and port.
    Query/fragment, percent encodings and ambiguous paths are outside v1 scope.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    issuer: str = Field(repr=False)
    client_id: str = Field(repr=False)
    callback_url: str = Field(repr=False)
    signature_algorithms: tuple[str, ...]
    deployment_mode: Literal["production", "development"]
    allow_http_loopback_callback: bool = False
    transaction_ttl_seconds: int = Field(ge=60, le=600)
    clock_skew_seconds: int = Field(ge=0, le=120)
    max_id_token_age_seconds: int = Field(ge=60, le=3600)

    def __setattr__(self, name, value):
        raise TypeError("OIDC configuration is immutable")

    def __delattr__(self, name):
        raise TypeError("OIDC configuration is immutable")

    @model_validator(mode="wrap")
    @classmethod
    def _redact_errors(cls, data, handler):
        try:
            return handler(data)
        except (ValidationError, ValueError):
            pass
        # Discard raw values, unknown field names and original exception context.
        raise ValidationError.from_exception_data(
            cls.__name__,
            [{"type": "value_error", "loc": (), "input": "[redacted]",
              "ctx": {"error": ValueError("Invalid explicit OIDC configuration")}}],
            hide_input=True,
        ) from None

    @field_validator("issuer")
    @classmethod
    def _issuer(cls, value: str) -> str:
        if _url_parts(value).scheme != "https":
            raise ValueError("HTTPS issuer required")
        return value

    @field_validator("callback_url")
    @classmethod
    def _callback(cls, value: str) -> str:
        _url_parts(value)
        return value

    @field_validator("client_id")
    @classmethod
    def _client(cls, value: str) -> str:
        if (not value or len(value) > 512 or value != value.strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise ValueError("Explicit client id required")
        return value

    @field_validator("signature_algorithms")
    @classmethod
    def _algorithms(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if (not values or len(set(values)) != len(values)
                or any(value not in ACCEPTED_SIGNATURE_ALGORITHMS for value in values)):
            raise ValueError("Explicit allowed signature algorithms required")
        return values

    @model_validator(mode="after")
    def _policy(self):
        callback = _url_parts(self.callback_url)
        if self.allow_http_loopback_callback and self.deployment_mode != "development":
            raise ValueError("Development opt-in forbidden in production")
        if callback.scheme == "http" and not (
            self.deployment_mode == "development" and self.allow_http_loopback_callback
            and callback.hostname in LOOPBACK_HOSTS and callback.port is not None
        ):
            raise ValueError("HTTPS callback required outside explicit loopback development")
        if self.clock_skew_seconds >= min(self.transaction_ttl_seconds, self.max_id_token_age_seconds):
            raise ValueError("Incoherent OIDC timing policy")
        return self
