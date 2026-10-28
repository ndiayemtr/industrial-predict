"""Pure local identity resolution, not OIDC/JWT verification or authentication.

External identities and local snapshots must come from trusted server adapters.
Constructing a Python object cannot attest their provenance or freshness. No
normalization, automatic registration, membership or permission grant occurs.
"""

from dataclasses import dataclass
from typing import Protocol

from app.core.authorization import AccountState, VerifiedIdentity


class IdentityResolutionError(ValueError):
    """Base for constant, non-sensitive resolution diagnostics."""


class InvalidExternalIdentity(IdentityResolutionError):
    def __init__(self):
        super().__init__("EXTERNAL_IDENTITY_INVALID")


class IdentityLinkNotFound(IdentityResolutionError):
    def __init__(self):
        super().__init__("LOCAL_IDENTITY_NOT_FOUND")


class AmbiguousIdentityLink(IdentityResolutionError):
    def __init__(self):
        super().__init__("LOCAL_IDENTITY_AMBIGUOUS")


class InvalidIdentityLink(IdentityResolutionError):
    def __init__(self):
        super().__init__("LOCAL_IDENTITY_INCOHERENT")


class InactiveLocalAccount(IdentityResolutionError):
    def __init__(self):
        super().__init__("LOCAL_ACCOUNT_INACTIVE")


class InvalidIdentityLookup(IdentityResolutionError):
    def __init__(self):
        super().__init__("LOCAL_IDENTITY_LOOKUP_INVALID")


class IdentityLookupUnavailable(IdentityResolutionError):
    """Operational failure, never an absent account or an authorization denial."""

    def __init__(self):
        super().__init__("LOCAL_IDENTITY_LOOKUP_UNAVAILABLE")


def _identifier(value: object) -> bool:
    # Structural bounds consistent with VerifiedIdentity, not an OIDC profile.
    return (type(value) is str and 0 < len(value) <= 2048
            and value == value.strip()
            and not any(ord(char) < 32 or ord(char) == 127 for char in value))


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedExternalIdentity:
    """Server-asserted external key; values are preserved exactly, never decoded."""

    issuer: str
    subject: str

    def __post_init__(self):
        if not _identifier(self.issuer) or not _identifier(self.subject):
            raise InvalidExternalIdentity()


@dataclass(frozen=True, slots=True, repr=False)
class LocalIdentityLink:
    """Read-only lookup snapshot including the associated local account state.

    The provider must return every exact match, without choosing one duplicate,
    and obtain the account state from the associated user, not token claims.
    """

    issuer: str
    subject: str
    user_id: int
    account_state: AccountState


class LocalIdentityLookup(Protocol):
    """Injected read-only port. Exceptions mean lookup unavailable, not no match."""

    def find_by_external_identity(
        self, *, issuer: str, subject: str,
    ) -> tuple[LocalIdentityLink, ...]:
        ...


def resolve_local_identity(
    external: VerifiedExternalIdentity, *, lookup: LocalIdentityLookup,
) -> VerifiedIdentity:
    """Resolve one exact link to an active user, with no retries or side effects.

    The injected provider performs the lookup; this function performs no I/O.
    Even a single returned link is checked against both external key components.
    A malformed provider response fails closed. No email/name fallback exists.
    """
    valid = False
    if type(external) is VerifiedExternalIdentity:
        try:
            valid = _identifier(external.issuer) and _identifier(external.subject)
        except AttributeError:
            pass
    if not valid:
        raise InvalidExternalIdentity()

    find = None
    try:
        find = getattr(lookup, "find_by_external_identity", None)
    except Exception:
        pass
    if not callable(find):
        raise InvalidIdentityLookup()

    available = False
    links = None
    try:
        links = find(issuer=external.issuer, subject=external.subject)
        available = True
    except Exception:
        pass
    # Raise outside the except block: do not retain a sensitive provider cause.
    if not available:
        raise IdentityLookupUnavailable() from None
    if type(links) is not tuple:
        raise InvalidIdentityLink()
    if not links:
        raise IdentityLinkNotFound()
    if len(links) != 1:
        raise AmbiguousIdentityLink()

    link = links[0]
    coherent = False
    if type(link) is LocalIdentityLink:
        try:
            coherent = (
                _identifier(link.issuer) and _identifier(link.subject)
                and link.issuer == external.issuer and link.subject == external.subject
                and type(link.user_id) is int and link.user_id > 0
                and type(link.account_state) is AccountState
            )
        except AttributeError:
            pass
    if not coherent:
        raise InvalidIdentityLink()
    if link.account_state is not AccountState.ACTIVE:
        raise InactiveLocalAccount()
    return VerifiedIdentity(link.user_id, external.issuer, external.subject, link.account_state)
