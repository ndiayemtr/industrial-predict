"""SQLite constraints and injected policy only, no PostgreSQL or migration execution."""

from dataclasses import replace
from unittest.mock import Mock
import traceback

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import (
    AccountState, AuthorizationEffect, MembershipState, Permission, decide_authorization,
)
from app.core.identity import VerifiedExternalIdentity, resolve_local_identity, InactiveLocalAccount, IdentityLinkNotFound
from app.core.orm import Base
from app.models.company import Company
from app.models.professional_account import LocalUserRecord, ExternalIdentityRecord, MembershipRecord, MembershipPermissionRecord
from app.repositories.professional_account_repository import (
    ProfessionalAccountRepository, AccountRepositoryRejected, AccountRepositoryConflict, AccountRepositoryUnavailable,
)


TABLES=[c.__table__ for c in (LocalUserRecord,ExternalIdentityRecord,MembershipRecord,MembershipPermissionRecord)]
KEY=VerifiedExternalIdentity('https://identity.example.invalid','exact-subject')
MARKER='SYNTHETIC-PRIVATE-ACCOUNT-DETAIL'


@pytest.fixture
def db():
    engine=create_engine('sqlite+pysqlite:///:memory:')
    @event.listens_for(engine,'connect')
    def configure(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.create_function('octet_length',1,lambda v: len(v.encode('utf-8')))
    Base.metadata.create_all(engine,tables=[Company.__table__,*TABLES])
    with Session(engine) as seed:
        seed.add_all([Company(id=1,name='A',code='A'),Company(id=2,name='B',code='B')])
        seed.add_all([LocalUserRecord(id=i,state='suspended' if i==3 else 'active') for i in (1,2,3)])
        seed.flush()
        seed.add(ExternalIdentityRecord(user_id=1,issuer=KEY.issuer,subject=KEY.subject))
        seed.add_all([MembershipRecord(id=1,user_id=1,company_id=1,state='active',role='reader'),
                      MembershipRecord(id=2,user_id=1,company_id=2,state='inactive',role='technician')])
        seed.flush()
        seed.add_all([MembershipPermissionRecord(membership_id=1,role='reader',permission='companies:read'),
                      MembershipPermissionRecord(membership_id=2,role='technician',permission='maintenance:write')])
        seed.commit()
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_exact_identity_lookup_and_no_domain_or_email_fallback(db):
    repo=ProfessionalAccountRepository(db)
    identity=resolve_local_identity(KEY,lookup=repo)
    assert identity.user_id==1 and identity.account_state is AccountState.ACTIVE
    for external in (replace(KEY,subject='another-subject'),replace(KEY,issuer=KEY.issuer+'/other')):
        with pytest.raises(IdentityLinkNotFound): resolve_local_identity(external,lookup=repo)
    assert all('email' not in t.c for t in TABLES)


def test_memberships_are_explicit_inactive_grants_empty_and_scoped(db):
    repo=ProfessionalAccountRepository(db)
    identity=resolve_local_identity(KEY,lookup=repo)
    memberships=repo.memberships_for_user(user_id=1)
    assert memberships[0].permissions==frozenset([Permission.COMPANIES_READ])
    assert memberships[1].state is MembershipState.INACTIVE
    assert memberships[1].permissions==frozenset()
    for company,permission,effect in [(1,Permission.COMPANIES_READ,AuthorizationEffect.ALLOW),
                                      (1,Permission.ASSETS_READ,AuthorizationEffect.DENY),
                                      (2,Permission.MAINTENANCE_WRITE,AuthorizationEffect.DENY)]:
        assert decide_authorization(identity=identity,memberships=memberships,company_id=company,permission=permission).effect is effect


def test_suspended_account_rejected_by_core_and_membership_adapter(db):
    db.add(ExternalIdentityRecord(user_id=3,issuer=KEY.issuer,subject='suspended'))
    db.flush()
    repo=ProfessionalAccountRepository(db)
    with pytest.raises(InactiveLocalAccount): resolve_local_identity(replace(KEY,subject='suspended'),lookup=repo)
    with pytest.raises(AccountRepositoryRejected): repo.memberships_for_user(user_id=3)


def test_authorized_link_flushes_only_and_never_grants_access(db):
    authority=Mock(return_value=None)
    repo=ProfessionalAccountRepository(db,require_link_authorization=authority)
    external=replace(KEY,subject='second-external-key')
    repo.link_identity(external=external,user_id=2)
    authority.assert_called_once_with(external=external,user_id=2)
    assert resolve_local_identity(external,lookup=repo).user_id==2
    assert repo.memberships_for_user(user_id=2)==()
    assert db.in_transaction()
    db.rollback()
    assert repo.find_by_external_identity(issuer=external.issuer,subject=external.subject)==()


@pytest.mark.parametrize('policy', ['missing','reject','boolean'])
def test_link_denial_before_any_sql(policy):
    session=Mock()
    def reject(**kw): raise RuntimeError(MARKER)
    authority=None if policy=='missing' else reject if policy=='reject' else lambda **kw: True
    repo=ProfessionalAccountRepository(session,require_link_authorization=authority)
    with pytest.raises(AccountRepositoryRejected) as caught: repo.link_identity(external=KEY,user_id=1)
    assert session.mock_calls==[]
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert MARKER not in ''.join(traceback.format_exception(caught.value))


@pytest.mark.parametrize('user_id', [3,999])
def test_link_requires_existing_active_user(db,user_id):
    repo=ProfessionalAccountRepository(db,require_link_authorization=lambda **kw: None)
    with pytest.raises(AccountRepositoryRejected): repo.link_identity(external=replace(KEY,subject='new'),user_id=user_id)
    assert repo.find_by_external_identity(issuer=KEY.issuer,subject='new')==()


def test_duplicate_identity_conflict_never_reassigns(db):
    repo=ProfessionalAccountRepository(db,require_link_authorization=lambda **kw: None)
    with pytest.raises(AccountRepositoryConflict): repo.link_identity(external=KEY,user_id=2)
    db.rollback()
    assert resolve_local_identity(KEY,lookup=repo).user_id==1


def test_sql_rejects_membership_for_existing_negative_company(db):
    # The historical Company schema permits this id: the FK alone is insufficient.
    db.add(Company(id=-1,name='Synthetic negative company',code='NEGATIVE'))
    db.flush()
    assert db.get(Company,-1) is not None
    db.add(MembershipRecord(user_id=2,company_id=-1,state='active',role='reader'))
    with pytest.raises(IntegrityError) as caught:
        db.flush()
    assert 'ck_company_memberships_positive_company_id' in str(caught.value.orig)
    db.rollback()


@pytest.mark.parametrize('record', [
    lambda: MembershipRecord(user_id=1,company_id=1,state='active',role='reader'),
    lambda: MembershipRecord(user_id=999,company_id=1,state='active',role='reader'),
    lambda: MembershipRecord(user_id=2,company_id=999,state='active',role='reader'),
    lambda: MembershipRecord(user_id=2,company_id=1,state='unknown',role='reader'),
    lambda: MembershipRecord(user_id=2,company_id=1,state='active',role='root'),
    lambda: LocalUserRecord(id=-1,state='active'),
    lambda: LocalUserRecord(id=7,state='unknown'),
    lambda: ExternalIdentityRecord(user_id=999,issuer=KEY.issuer,subject='new'),
    lambda: ExternalIdentityRecord(user_id=2,issuer='',subject='new'),
    lambda: ExternalIdentityRecord(user_id=2,issuer='x'*2048,subject='too-long'),
    lambda: MembershipPermissionRecord(membership_id=1,role='reader',permission='memberships:manage'),
    lambda: MembershipPermissionRecord(membership_id=1,role='company_admin',permission='memberships:manage'),
    lambda: MembershipPermissionRecord(membership_id=1,role='reader',permission='unknown'),
    lambda: MembershipPermissionRecord(membership_id=1,role='reader',permission='companies:read'),
])
def test_sql_constraints_reject_inconsistent_records(db,record):
    db.add(record())
    with pytest.raises(IntegrityError): db.flush()
    db.rollback()


def test_repository_errors_sanitized_inside_active_handler():
    from sqlalchemy.exc import OperationalError
    session=Mock(); session.execute.side_effect=OperationalError(MARKER,{},RuntimeError(MARKER))
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        with pytest.raises(AccountRepositoryUnavailable) as caught:
            ProfessionalAccountRepository(session).find_by_external_identity(issuer=KEY.issuer,subject=KEY.subject)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert caught.value.__suppress_context__
    assert MARKER not in ''.join(traceback.format_exception(caught.value))


@pytest.mark.parametrize('value', [True,0,-1,'1',None])
def test_invalid_user_ids_rejected_before_sql(value):
    session=Mock()
    with pytest.raises(AccountRepositoryRejected): ProfessionalAccountRepository(session).memberships_for_user(user_id=value)
    assert session.mock_calls==[]
