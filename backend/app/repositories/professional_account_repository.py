"""Explicit caller-owned Session. No engine, commit, email lookup or auto-grant.

require_link_authorization is a trusted server policy callback: it must return
None only after authorizing this exact external key/target user, otherwise raise.
It is not an approval supplied by a browser. No authority implementation is
installed here; a Python callback cannot attest its own authenticity.
"""

from functools import wraps

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.authorization import AccountState, CompanyMembership, MembershipState, Permission, Role, _role_permissions
from app.core.identity import LocalIdentityLink, VerifiedExternalIdentity, _identifier
from app.models.professional_account import (
    ExternalIdentityRecord, LocalUserRecord, MembershipPermissionRecord, MembershipRecord,
)


class AccountRepositoryRejected(ValueError):
    def __init__(self):
        super().__init__("ACCOUNT_REPOSITORY_REJECTED")


class AccountRepositoryConflict(AccountRepositoryRejected):
    def __init__(self):
        ValueError.__init__(self, "ACCOUNT_REPOSITORY_CONFLICT")


class AccountRepositoryUnavailable(AccountRepositoryRejected):
    def __init__(self):
        ValueError.__init__(self, "ACCOUNT_REPOSITORY_UNAVAILABLE")


def _raise(kind):
    try:
        raise kind() from None
    except AccountRepositoryRejected as error:
        error.__context__ = error.__cause__ = None
        error.__suppress_context__ = True
        raise


def _safe(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        kind = AccountRepositoryRejected
        try:
            return function(*args, **kwargs)
        except IntegrityError:
            kind = AccountRepositoryConflict
        except SQLAlchemyError:
            kind = AccountRepositoryUnavailable
        except Exception:
            pass
        _raise(kind)
    return guarded


def _require(condition):
    if not condition:
        raise AccountRepositoryRejected()


def _id(value):
    return type(value) is int and value > 0


def _key(issuer, subject):
    _require(_identifier(issuer) and _identifier(subject)
             and len(issuer.encode('utf-8')) + len(subject.encode('utf-8')) <= 2048)


class ProfessionalAccountRepository:
    @_safe
    def __init__(self, session, *, require_link_authorization=None):
        self._session = session
        _require(require_link_authorization is None or callable(require_link_authorization))
        self._authorize_link = require_link_authorization

    @_safe
    def find_by_external_identity(self, *, issuer, subject) -> tuple[LocalIdentityLink, ...]:
        """LocalIdentityLookup adapter. Return account state; core rejects suspended."""
        _key(issuer, subject)
        rows = self._session.execute(select(
            ExternalIdentityRecord.issuer, ExternalIdentityRecord.subject,
            LocalUserRecord.id, LocalUserRecord.state,
        ).join(LocalUserRecord, ExternalIdentityRecord.user_id == LocalUserRecord.id).where(
            ExternalIdentityRecord.issuer == issuer, ExternalIdentityRecord.subject == subject,
        )).all()
        links = []
        for found_issuer, found_subject, user_id, state in rows:
            _require((found_issuer, found_subject) == (issuer, subject) and _id(user_id))
            links.append(LocalIdentityLink(issuer, subject, user_id, AccountState(state)))
        return tuple(links)

    @_safe
    def memberships_for_user(self, *, user_id) -> tuple[CompanyMembership, ...]:
        _require(_id(user_id))
        state = self._session.scalar(select(LocalUserRecord.state).where(LocalUserRecord.id == user_id))
        _require(state == AccountState.ACTIVE.value)
        rows = self._session.scalars(select(MembershipRecord).where(
            MembershipRecord.user_id == user_id).order_by(MembershipRecord.company_id)
            .execution_options(populate_existing=True)).all()
        result = []
        seen = set()
        for row in rows:
            _require(_id(row.company_id) and row.company_id not in seen and row.user_id == user_id)
            seen.add(row.company_id)
            role, state = Role(row.role), MembershipState(row.state)
            grants = self._session.execute(select(MembershipPermissionRecord.role, MembershipPermissionRecord.permission).where(
                MembershipPermissionRecord.membership_id == row.id)).all()
            _require(all(grant_role == role.value for grant_role, _ in grants))
            permissions = frozenset(Permission(permission) for _, permission in grants)
            _require(permissions <= _role_permissions(role))
            if state is MembershipState.INACTIVE:
                permissions = frozenset()
            result.append(CompanyMembership(user_id, row.company_id, state, role, permissions))
        return tuple(result)

    @_safe
    def link_identity(self, *, external: VerifiedExternalIdentity, user_id) -> None:
        """Flush only. Caller must own transaction, commit/rollback and uncertainty.

        There is deliberately no create-user/create-membership operation here.
        A duplicate is a conflict, never an upsert, reassignment or silent merge.
        """
        _require(type(external) is VerifiedExternalIdentity and _id(user_id))
        _key(external.issuer, external.subject)
        _require(self._authorize_link is not None)
        _require(self._authorize_link(external=external, user_id=user_id) is None)
        state = self._session.scalar(select(LocalUserRecord.state).where(
            LocalUserRecord.id == user_id).with_for_update())
        _require(state == AccountState.ACTIVE.value)
        self._session.add(ExternalIdentityRecord(user_id=user_id, issuer=external.issuer, subject=external.subject))
        self._session.flush()
