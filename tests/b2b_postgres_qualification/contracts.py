"""Immutable offline data only. Constructors do not validate or grant authority."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class Rejected(ValueError):
    def __init__(self):
        super().__init__("B2B_QUALIFICATION_REJECTED")


class ExecutionDisabled(RuntimeError):
    def __init__(self):
        super().__init__("B2B_QUALIFICATION_EXECUTION_DISABLED")


def deny(error_type):
    try:
        raise error_type() from None
    except (Rejected, ExecutionDisabled) as error:
        error.__context__ = error.__cause__ = None
        error.__suppress_context__ = True
        raise


class Offline:
    __slots__ = ()

    def __repr__(self):
        return f"<{type(self).__name__}: offline-unattested>"

    def __bool__(self):
        deny(ExecutionDisabled)

    @property
    def execution_authorized(self):
        return False

    @property
    def real_attested(self):
        return False

    @property
    def authenticated(self):
        return False


@dataclass(frozen=True, slots=True, repr=False)
class Campaign(Offline):
    campaign_id: str
    instance_id: str
    engine_id: str
    container_id: str
    runner_id: str
    network_id: str
    container_name: str
    network_name: str
    volume_name: str
    database: str
    host: str
    port: int
    subnet: str
    server_address: str
    cluster_name: str
    roles: tuple[str, ...]
    image_sha256: str
    ca_sha256: str
    server_version_num: int


@dataclass(frozen=True, slots=True, repr=False)
class Publication(Offline):
    revision: str
    parent: str | None
    path: str
    sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class MigrationPlan(Offline):
    operation: str
    initial_revision: str | None
    final_revision: str
    publications: tuple[Publication, ...]


@dataclass(frozen=True, slots=True, repr=False)
class Approval(Offline):
    authority_id: str
    campaign_id: str
    operation: str
    destination_sha256: str
    plan_sha256: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True, repr=False)
class AuthorityClaim(Offline):
    """An injected assertion, never a cryptographic authentication result."""

    authority_id: str
    envelope_sha256: str
    claimed_authenticated: bool


class IndependentAuthority(Protocol):
    def authenticate(self, *, authority_id: str, envelope_sha256: str) -> AuthorityClaim:
        """Future trust boundary. No operational implementation is supplied."""
        ...


@dataclass(frozen=True, slots=True, repr=False)
class Observation(Offline):
    """Injected facts. 'unverified_external' is not proof of real collection."""

    kind: str
    campaign_id: str
    destination_sha256: str
    provenance: str
    source_id: str
    started_at: datetime
    observed_at: datetime
    connection_id: str
    facts: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True, repr=False)
class Review(Offline):
    stage: str


@dataclass(frozen=True, slots=True, repr=False)
class Effect(Offline):
    operation: str
    outcome: str
    at: datetime
    evidence_sha256: str | None


@dataclass(frozen=True, slots=True, repr=False)
class EffectJournal(Offline):
    """Append-only *declarations*. Confirmed outcomes are not independently proved."""

    campaign_id: str
    destination_sha256: str
    entries: tuple[Effect, ...] = ()


@dataclass(frozen=True, slots=True)
class Scenario:
    identifier: str
    category: str
    precondition: str
    action: str
    expected: str
    evidence: str
    stop: str
