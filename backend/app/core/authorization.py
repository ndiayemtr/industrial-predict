"""Pure authorization policy v1; these data objects do not authenticate anyone.

Only a future trusted server component may supply identity and memberships after
verification. Client ids, roles or booleans are never evidence. No I/O or runtime
binding is performed here; membership freshness/revocation remain server duties.
"""

from dataclasses import dataclass
from enum import Enum


POLICY_VERSION = "company-authorization-v1"


class AccountState(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class MembershipState(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Permission(str, Enum):
    COMPANIES_READ = "companies:read"
    ASSETS_READ = "assets:read"
    MEASUREMENTS_READ = "measurements:read"
    PREDICTIONS_READ = "predictions:read"
    MAINTENANCE_WRITE = "maintenance:write"
    MEMBERSHIPS_MANAGE = "memberships:manage"


class Role(str, Enum):
    READER = "reader"
    TECHNICIAN = "technician"
    COMPANY_ADMIN = "company_admin"


class AuthorizationEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedIdentity:
    """Server-asserted identity, not a signed credential or authentication result."""

    user_id: int
    issuer: str
    subject: str
    account_state: AccountState


@dataclass(frozen=True, slots=True, repr=False)
class CompanyMembership:
    user_id: int
    company_id: int
    state: MembershipState
    role: Role
    permissions: frozenset[Permission]


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Minimal scoped outcome; never contains identity data or diagnostic inputs."""

    effect: AuthorizationEffect
    company_id: int | None
    permission: Permission | None
    policy_version: str = POLICY_VERSION


def _positive_id(value: object) -> bool:
    return type(value) is int and value > 0


def _identity_text(value: object) -> bool:
    return (type(value) is str and 0 < len(value) <= 2048
            and value == value.strip()
            and not any(ord(char) < 32 or ord(char) == 127 for char in value))


def _role_permissions(role: Role) -> frozenset[Permission]:
    # Roles cap explicit grants; a role alone never grants a permission.
    read = frozenset((Permission.COMPANIES_READ, Permission.ASSETS_READ,
                      Permission.MEASUREMENTS_READ, Permission.PREDICTIONS_READ))
    if role is Role.READER:
        return read
    if role is Role.TECHNICIAN:
        return read | frozenset((Permission.MAINTENANCE_WRITE,))
    return frozenset(Permission)  # Called only after exact Role validation.


def decide_authorization(
    *,
    identity: VerifiedIdentity | None = None,
    memberships: tuple[CompanyMembership, ...] = (),
    company_id: int | None = None,
    permission: Permission | None = None,
) -> AuthorizationDecision:
    """Deny unless every input is coherent and one exact active grant exists.

    Memberships must be the trusted snapshot for this user. Duplicate companies,
    foreign-user entries or malformed entries invalidate the entire snapshot.
    Unknown permissions/roles are denied; extensions require a reviewed policy.
    No aggregation of permissions across companies is permitted.
    """
    target = company_id if _positive_id(company_id) else None
    requested = permission if type(permission) is Permission else None
    denied = AuthorizationDecision(AuthorizationEffect.DENY, target, requested)
    if target is None or requested is None or type(identity) is not VerifiedIdentity:
        return denied
    try:
        if (not _positive_id(identity.user_id) or not _identity_text(identity.issuer)
                or not _identity_text(identity.subject)
                or type(identity.account_state) is not AccountState
                or identity.account_state is not AccountState.ACTIVE
                or type(memberships) is not tuple):
            return denied
        seen = set()
        selected = None
        for member in memberships:
            if (type(member) is not CompanyMembership or not _positive_id(member.user_id)
                    or member.user_id != identity.user_id or not _positive_id(member.company_id)
                    or member.company_id in seen or type(member.state) is not MembershipState
                    or type(member.role) is not Role or type(member.permissions) is not frozenset
                    or any(type(item) is not Permission for item in member.permissions)
                    or not member.permissions <= _role_permissions(member.role)):
                return denied
            seen.add(member.company_id)
            if member.company_id == target:
                selected = member
        if (selected is not None and selected.state is MembershipState.ACTIVE
                and requested in selected.permissions):
            return AuthorizationDecision(AuthorizationEffect.ALLOW, target, requested)
    except (AttributeError, TypeError):
        # Also reject incompletely constructed dataclasses without leaking values.
        return denied
    return denied
