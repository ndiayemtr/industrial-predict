"""Pure B2B session contracts; no HTTP, persistence, randomness or authentication.

Only trusted server adapters may supply evidence, session records and fresh local
snapshots. Typed objects (including VerifiedExternalIdentity) cannot prove their
cryptographic provenance. Browser ids, roles, email and domains are not evidence.
Rotation/revocation below describe transitions, not atomic storage operations.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol

from app.core.authorization import (
    POLICY_VERSION, AccountState, CompanyMembership, MembershipState, Permission,
    Role, VerifiedIdentity, _role_permissions,
)
from app.core.identity import (
    AmbiguousIdentityLink, IdentityLinkNotFound, IdentityLookupUnavailable,
    InactiveLocalAccount, InvalidExternalIdentity, InvalidIdentityLink,
    InvalidIdentityLookup, LocalIdentityLookup, VerifiedExternalIdentity,
    resolve_local_identity,
)


class Outcome(str, Enum):
    READY = "ready"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    INCOHERENT = "incoherent"
    UNAVAILABLE = "unavailable"


class Reason(str, Enum):
    VALID = "valid"
    NO_IDENTITY = "no_identity"
    ASSURANCE_REQUIRED = "assurance_required"
    UNKNOWN_IDENTITY = "unknown_identity"
    AMBIGUOUS_IDENTITY = "ambiguous_identity"
    ACCOUNT_INACTIVE = "account_inactive"
    INVALID_STATE = "invalid_state"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    SESSION_MISMATCH = "session_mismatch"
    IDLE_EXPIRED = "idle_expired"
    ABSOLUTE_EXPIRED = "absolute_expired"
    REVOKED = "revoked"
    ROTATED = "rotated"


class SessionContractError(ValueError):
    def __init__(self):
        super().__init__("CALLER_SESSION_CONTRACT_INVALID")


def _require(condition):
    if not condition:
        raise SessionContractError()


def _utc(value):
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() == timedelta(0)


def _identity(value):
    _require(type(value) is VerifiedIdentity)
    _require(type(getattr(value, "user_id", None)) is int and value.user_id > 0)
    _require(type(getattr(value, "account_state", None)) is AccountState)
    valid = False
    try:
        VerifiedExternalIdentity(value.issuer, value.subject)
        valid = True
    except (InvalidExternalIdentity, AttributeError):
        pass
    _require(valid)


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    idle_timeout: timedelta = timedelta(minutes=30)
    absolute_timeout: timedelta = timedelta(hours=8)

    def __post_init__(self):
        _require(type(self.idle_timeout) is timedelta and type(self.absolute_timeout) is timedelta)
        _require(timedelta(0) < self.idle_timeout <= self.absolute_timeout)


@dataclass(frozen=True, slots=True, repr=False)
class SessionReference:
    """Internal digest/reference supplied by storage; never a raw cookie value."""

    digest: str

    def __post_init__(self):
        _require(type(self.digest) is str and len(self.digest) == 64
                 and all(c in "0123456789abcdef" for c in self.digest))


@dataclass(frozen=True, slots=True, repr=False)
class SessionRecord:
    reference: SessionReference
    identity: VerifiedIdentity
    authenticated_at: datetime
    created_at: datetime
    last_activity_at: datetime
    absolute_expires_at: datetime
    policy: SessionPolicy = SessionPolicy()
    revoked_at: datetime | None = None
    replaced_by: SessionReference | None = None

    def __post_init__(self):
        valid = False
        try:
            self._validate()
            valid = True
        except (SessionContractError, AttributeError, TypeError, ValueError, OverflowError):
            pass
        _require(valid)

    def _validate(self):
        _require(type(self.reference) is SessionReference and type(self.policy) is SessionPolicy)
        self.reference.__post_init__()
        self.policy.__post_init__()
        _identity(self.identity)
        _require(all(_utc(t) for t in (self.authenticated_at, self.created_at,
                                       self.last_activity_at, self.absolute_expires_at)))
        _require(self.authenticated_at <= self.created_at <= self.last_activity_at < self.absolute_expires_at)
        _require(self.absolute_expires_at == self.authenticated_at + self.policy.absolute_timeout)
        if self.revoked_at is not None:
            _require(_utc(self.revoked_at) and self.last_activity_at <= self.revoked_at)
        if self.replaced_by is not None:
            _require(type(self.replaced_by) is SessionReference and self.revoked_at is not None)
            self.replaced_by.__post_init__()
            _require(self.replaced_by != self.reference)


@dataclass(frozen=True, slots=True)
class SessionDecision:
    outcome: Outcome
    reason: Reason

    def __bool__(self):
        raise TypeError("Inspect session outcome explicitly")


def evaluate_session(record: SessionRecord, *, reference: SessionReference, now: datetime) -> SessionDecision:
    """Exclusive expiry boundaries, UTC only, deterministic and fail closed."""
    try:
        _require(type(record) is SessionRecord and type(reference) is SessionReference and _utc(now))
        record.__post_init__()
        reference.__post_init__()
        _require(record.last_activity_at <= now)
        if record.reference != reference:
            return SessionDecision(Outcome.UNAUTHENTICATED, Reason.SESSION_MISMATCH)
        if record.revoked_at is not None:
            _require(record.revoked_at <= now)
            return SessionDecision(Outcome.UNAUTHENTICATED,
                                   Reason.ROTATED if record.replaced_by is not None else Reason.REVOKED)
        if now >= record.absolute_expires_at:
            return SessionDecision(Outcome.UNAUTHENTICATED, Reason.ABSOLUTE_EXPIRED)
        if now - record.last_activity_at >= record.policy.idle_timeout:
            return SessionDecision(Outcome.UNAUTHENTICATED, Reason.IDLE_EXPIRED)
        if record.identity.account_state is not AccountState.ACTIVE:
            return SessionDecision(Outcome.FORBIDDEN, Reason.ACCOUNT_INACTIVE)
        return SessionDecision(Outcome.READY, Reason.VALID)
    except (SessionContractError, AttributeError, TypeError, OverflowError, ValueError):
        return SessionDecision(Outcome.INCOHERENT, Reason.INVALID_STATE)


def _live(record, now):
    _require(type(record) is SessionRecord)
    _require(evaluate_session(record, reference=getattr(record, "reference", None), now=now).outcome is Outcome.READY)


def record_activity(record: SessionRecord, *, now: datetime) -> SessionRecord:
    _live(record, now)
    return replace(record, last_activity_at=now)


def revoke_session(record: SessionRecord, *, now: datetime) -> SessionRecord:
    """Transition proposal only; a storage adapter must durably apply it."""
    _live(record, now)
    return replace(record, revoked_at=now)


@dataclass(frozen=True, slots=True, repr=False)
class RotationPlan:
    invalidated: SessionRecord
    replacement: SessionRecord


def rotate_session(record: SessionRecord, *, replacement: SessionReference, now: datetime) -> RotationPlan:
    """No grace period or lifetime extension. Adapter must commit BOTH records.

    Never issue the new credential before commit confirmation. This function
    neither reserves uniqueness nor invalidates a stored/cached copy itself.
    """
    _live(record, now)
    _require(type(replacement) is SessionReference and replacement != record.reference)
    replacement.__post_init__()
    return RotationPlan(replace(record, revoked_at=now, replaced_by=replacement),
                        replace(record, reference=replacement, created_at=now, last_activity_at=now))


class IdentityAssurance(str, Enum):
    PROFESSIONAL_VERIFIED = "professional_verified"
    INDEPENDENT_VERIFICATION_REQUIRED = "independent_verification_required"


@dataclass(frozen=True, slots=True, repr=False)
class IdentityEvidence:
    """Trusted adapter assertion, not cryptographic proof or a client DTO.

    Google PROFESSIONAL_VERIFIED requires professional_email_verified, not just
    email_verified. Pending results must remain pending; no email fallback.
    """

    external: VerifiedExternalIdentity
    assurance: IdentityAssurance


class TrustedIdentityProvider(Protocol):
    def verified_identity(self) -> IdentityEvidence | None:
        """Return evidence only after verification; exceptions mean unavailable."""
        ...


@dataclass(frozen=True, slots=True, repr=False)
class AdmissionDecision:
    outcome: Outcome
    reason: Reason
    identity: VerifiedIdentity | None = None

    def __bool__(self):
        raise TypeError("Inspect admission outcome explicitly")


def admit_caller(*, provider: TrustedIdentityProvider, lookup: LocalIdentityLookup) -> AdmissionDecision:
    """Admission grants no company permission and creates/links no account."""
    try:
        method = getattr(provider, "verified_identity", None)
        _require(callable(method))
    except Exception:
        return AdmissionDecision(Outcome.INCOHERENT, Reason.INVALID_STATE)
    evidence = None
    available = False
    try:
        evidence = method()
        available = True
    except Exception:
        pass
    if not available:
        return AdmissionDecision(Outcome.UNAVAILABLE, Reason.PROVIDER_UNAVAILABLE)
    if evidence is None:
        return AdmissionDecision(Outcome.UNAUTHENTICATED, Reason.NO_IDENTITY)
    try:
        _require(type(evidence) is IdentityEvidence and type(evidence.assurance) is IdentityAssurance)
        if evidence.assurance is not IdentityAssurance.PROFESSIONAL_VERIFIED:
            return AdmissionDecision(Outcome.FORBIDDEN, Reason.ASSURANCE_REQUIRED)
        identity = resolve_local_identity(evidence.external, lookup=lookup)
        return AdmissionDecision(Outcome.READY, Reason.VALID, identity)
    except IdentityLinkNotFound:
        return AdmissionDecision(Outcome.FORBIDDEN, Reason.UNKNOWN_IDENTITY)
    except AmbiguousIdentityLink:
        return AdmissionDecision(Outcome.INCOHERENT, Reason.AMBIGUOUS_IDENTITY)
    except InactiveLocalAccount:
        return AdmissionDecision(Outcome.FORBIDDEN, Reason.ACCOUNT_INACTIVE)
    except IdentityLookupUnavailable:
        return AdmissionDecision(Outcome.UNAVAILABLE, Reason.PROVIDER_UNAVAILABLE)
    except (SessionContractError, InvalidExternalIdentity, InvalidIdentityLink,
            InvalidIdentityLookup, AttributeError, TypeError):
        return AdmissionDecision(Outcome.INCOHERENT, Reason.INVALID_STATE)


@dataclass(frozen=True, slots=True, repr=False)
class CurrentCaller:
    """Request-local server snapshot; never persist memberships in the session.

    A trusted producer must verify the live session, re-resolve its exact external
    link and reload account/memberships in a coherent snapshot at refreshed_at.
    This constructor validates structure only, not freshness or provenance.
    Business access still requires decide_authorization() for the target company.
    """

    session_reference: SessionReference
    identity: VerifiedIdentity
    memberships: tuple[CompanyMembership, ...]
    refreshed_at: datetime
    policy_version: str = POLICY_VERSION

    def __post_init__(self):
        valid = False
        try:
            self._validate()
            valid = True
        except (SessionContractError, AttributeError, TypeError, ValueError):
            pass
        _require(valid)

    def _validate(self):
        _require(type(self.session_reference) is SessionReference)
        self.session_reference.__post_init__()
        _identity(self.identity)
        _require(self.identity.account_state is AccountState.ACTIVE)
        _require(_utc(self.refreshed_at) and type(self.policy_version) is str
                 and self.policy_version == POLICY_VERSION)
        _require(type(self.memberships) is tuple)
        seen = set()
        for member in self.memberships:
            _require(type(member) is CompanyMembership and type(member.user_id) is int
                     and member.user_id == self.identity.user_id)
            _require(type(member.company_id) is int and member.company_id > 0 and member.company_id not in seen)
            _require(type(member.state) is MembershipState and type(member.role) is Role)
            _require(type(member.permissions) is frozenset
                     and all(type(p) is Permission for p in member.permissions))
            # Share the existing ceiling; do not introduce another permission policy.
            _require(member.permissions <= _role_permissions(member.role))
            _require(member.state is MembershipState.ACTIVE or not member.permissions)
            seen.add(member.company_id)


class CurrentCallerProvider(Protocol):
    def current_caller(self, *, reference: SessionReference, now: datetime) -> CurrentCaller:
        """Verify stored session and reload local state; no client identity fields.

        Must reject expiry/revocation, require refreshed_at == now, and never
        fall back to stale data. Raise the typed errors below, without raw causes.
        No implementation, cache or default provider is installed here.
        """
        ...


class CallerUnauthenticated(ValueError):
    def __init__(self):
        super().__init__("CALLER_UNAUTHENTICATED")


class CallerForbidden(ValueError):
    def __init__(self):
        super().__init__("CALLER_FORBIDDEN")


class CallerStateIncoherent(ValueError):
    def __init__(self):
        super().__init__("CALLER_STATE_INCOHERENT")


class CallerProviderUnavailable(ValueError):
    def __init__(self):
        super().__init__("CALLER_PROVIDER_UNAVAILABLE")
