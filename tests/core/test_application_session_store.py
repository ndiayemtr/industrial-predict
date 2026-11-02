"""Offline simulations and PostgreSQL DDL compilation only; no database proof."""

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from threading import Lock
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql import operators
from sqlalchemy.sql.dml import Insert, Update
from sqlalchemy.sql.elements import BindParameter, Null, TextClause

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.application_session_store import (
    CONTRACT_VERSION, IssuedSession, PostgresApplicationSessionStore,
    SessionAdmissionProvider, SessionStoreCommitUncertain, SessionStoreIncoherent,
    SessionStoreRejected, SessionStoreUnavailable, csrf_fingerprint, session_reference,
)
from app.core.authorization import AccountState, AuthorizationEffect, Permission, VerifiedIdentity, decide_authorization
from app.core.caller_session import AdmissionDecision, Outcome, Reason, SessionPolicy, SessionReference
from app.core.database_runtime import SqlRuntime
from app.models.application_session import ApplicationSessionRecord


NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
PRIVATE = "synthetic-driver-private-detail"
TOKEN = base64.urlsafe_b64encode(b"a" * 32).rstrip(b"=").decode("ascii")
CSRF = base64.urlsafe_b64encode(b"z" * 32).rstrip(b"=").decode("ascii")
REFERENCE = session_reference(TOKEN)
IDENTITY = VerifiedIdentity(17, "https://identity.example.invalid", "synthetic-subject", AccountState.ACTIVE)
TABLE = ApplicationSessionRecord.__table__


def stored(**changes):
    values = dict(secret_digest=REFERENCE.digest, csrf_digest=csrf_fingerprint(CSRF), user_id=17,
                  external_identity_id=31, authenticated_at=NOW, created_at=NOW, last_activity_at=NOW,
                  absolute_expires_at=NOW + timedelta(hours=8), idle_timeout_seconds=1800,
                  absolute_timeout_seconds=28800, revoked_at=None, replaced_by=None,
                  contract_version=CONTRACT_VERSION)
    values.update(changes)
    return values


class Result:
    def __init__(self, rows=(), values=(), rowcount=0):
        self.rows, self.values, self.rowcount, self.as_scalars = list(rows), list(values), rowcount, False

    def scalar_one_or_none(self):
        return self.values[0] if self.values else None

    def scalar_one(self):
        if len(self.values) != 1:
            raise AssertionError("Expected one scalar")
        return self.values[0]

    def mappings(self):
        return self

    def one_or_none(self):
        if len(self.rows) > 1:
            raise AssertionError("Multiple rows")
        return self.rows[0] if self.rows else None

    def scalars(self):
        self.as_scalars = True
        return self

    def all(self):
        return self.values if self.as_scalars else self.rows


class SimulatedSession:
    """Small statement interpreter. Its mutex is NOT PostgreSQL locking proof."""

    def __init__(self, harness):
        self.h, self.locked, self.rows = harness, False, None

    def connection(self, *, execution_options):
        self.h.mutex.acquire()
        self.locked = True
        self.rows = deepcopy(self.h.rows)
        self.h.events.append(("isolation", execution_options))
        if self.h.failure == "acquire":
            raise RuntimeError(PRIVATE)

    def _matches(self, statement, row):
        for predicate in statement._where_criteria:
            left, right = predicate.left, predicate.right
            value = right.value if isinstance(right, BindParameter) else None if isinstance(right, Null) else row[right.name]
            if predicate.operator is operators.is_:
                matches = row[left.name] is value
            else:
                matches = predicate.operator(row[left.name], value)
            if not matches:
                return False
        return True

    def execute(self, statement):
        self.h.statements.append(statement)
        if self.h.failure == "execute":
            raise RuntimeError(PRIVATE)
        if isinstance(statement, TextClause):
            return Result()
        if isinstance(statement, Insert):
            self.h.events.append("insert")
            row = {key: value.value for key, value in statement._values.items()}
            if row["secret_digest"] in self.rows:
                raise RuntimeError(PRIVATE)
            self.rows[row["secret_digest"]] = row
            return Result(rowcount=1)
        if isinstance(statement, Update):
            self.h.events.append("update")
            if self.h.failure == "update":
                raise RuntimeError(PRIVATE)
            matched = [row for row in self.rows.values() if self._matches(statement, row)]
            for row in matched:
                row.update({key: value.value for key, value in statement._values.items()})
            return Result(rowcount=0 if self.h.failure == "lost_update" else len(matched))
        columns = list(statement.selected_columns)
        if columns[0].name == "clock_timestamp":
            self.h.events.append("clock")
            return Result(values=(self.h.server_now,))
        table = statement.get_final_froms()[0].name
        if table == "local_users":
            rows = self.h.users
        elif table == "external_identities":
            rows = self.h.external
        elif table == "application_sessions":
            rows = list(self.rows.values())
        else:
            raise AssertionError("Unexpected SQL table")
        if statement._for_update_arg is not None:
            self.h.events.append("lock:" + table)
        found = sorted((row for row in rows if self._matches(statement, row)),
                       key=lambda row: row.get("secret_digest", ""))
        return Result(rows=found, values=[row[columns[0].name] for row in found])

    def commit(self):
        self.h.events.append("commit")
        if self.h.failure == "commit_before":
            raise RuntimeError(PRIVATE)
        self.h.rows = deepcopy(self.rows)
        if self.h.failure == "commit_after":
            raise RuntimeError(PRIVATE)

    def rollback(self):
        self.h.events.append("rollback")
        if self.h.failure == "rollback":
            raise RuntimeError(PRIVATE)

    def close(self):
        self.h.events.append("close")
        if self.locked:
            self.h.mutex.release()
            self.locked = False
        if self.h.failure == "close":
            raise RuntimeError(PRIVATE)


class Harness:
    def __init__(self, *rows):
        self.rows = {row["secret_digest"]: deepcopy(row) for row in rows}
        self.events, self.statements, self.failure = [], [], None
        self.now = self.server_now = NOW
        self.users = [dict(id=17, state="active"), dict(id=18, state="active")]
        self.external = [dict(id=31, user_id=17, issuer=IDENTITY.issuer, subject=IDENTITY.subject)]
        self.mutex = Lock()
        self.engine = SimpleNamespace(echo=False, hide_parameters=True,
                                      logger=SimpleNamespace(isEnabledFor=lambda level: False))
        self.runtime = SqlRuntime(self.engine, lambda: SimulatedSession(self))
        self.admission = Mock(spec=SessionAdmissionProvider)
        self.admission.admit.return_value = AdmissionDecision(Outcome.READY, Reason.VALID, IDENTITY)
        self.authority = Mock(return_value=None)

    def store(self, **changes):
        options = dict(admission_provider=self.admission, clock=lambda: self.now)
        options.update(changes)
        return PostgresApplicationSessionStore(self.runtime, **options)


class ModelTests(unittest.TestCase):
    def test_fresh_import_cannot_open_a_database_or_load_legacy_configuration(self):
        script = r'''
import importlib.abc, sys
from contextlib import ExitStack
from unittest.mock import Mock, patch
import sqlalchemy, sqlalchemy.orm, psycopg
sys.path.insert(0, sys.argv[1])
def forbidden(*args, **kwargs): raise AssertionError('Implicit I/O forbidden')
class BlockLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('app.core.database', 'app.core.config', 'app.main', 'dotenv', 'pydantic_settings'):
            forbidden()
sys.meta_path.insert(0, BlockLegacy())
with ExitStack() as guards:
    for name in ('sqlalchemy.create_engine', 'sqlalchemy.orm.sessionmaker',
                 'sqlalchemy.engine.Engine.connect', 'sqlalchemy.sql.schema.MetaData.create_all',
                 'psycopg.connect', 'socket.socket.connect', 'socket.getaddrinfo'):
        guards.enter_context(patch(name, side_effect=forbidden))
    from app.application_session_store import PostgresApplicationSessionStore
    from app.core.database_runtime import SqlRuntime
    store = PostgresApplicationSessionStore(SqlRuntime(Mock(), Mock(side_effect=forbidden)),
        admission_provider=Mock(), clock=Mock())
    assert 'app.main' not in sys.modules and 'fastapi' not in sys.modules
'''
        result = subprocess.run([sys.executable, "-B", "-I", "-c", script, str(ROOT / "backend")],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_postgresql_ddl_and_constraints_without_database(self):
        ddl = str(CreateTable(TABLE).compile(dialect=postgresql.dialect()))
        for fragment in ("PRIMARY KEY (secret_digest)", "TIMESTAMP WITH TIME ZONE",
                         "ck_application_sessions_absolute_expiry", "ck_application_sessions_policy",
                         "ck_application_sessions_times", "ck_application_sessions_rotation",
                         "ck_application_sessions_revocation", "ck_application_sessions_contract",
                         "ck_application_sessions_secret_digest_hex", "ck_application_sessions_csrf_digest_hex",
                         "REFERENCES external_identities (id)", "REFERENCES local_users (id)",
                         "REFERENCES application_sessions (secret_digest)", "ON DELETE RESTRICT"):
            self.assertIn(fragment, ddl)
        self.assertEqual({index.name for index in TABLE.indexes},
                         {"ix_application_sessions_user", "ix_application_sessions_expiry"})

    def test_no_persistent_credentials_roles_permissions_or_company(self):
        forbidden = {"secret", "csrf_token", "password", "token", "role", "permissions", "company_id"}
        self.assertFalse(forbidden.intersection(TABLE.c.keys()))
        self.assertEqual(TABLE.c.contract_version.type.length, 32)
        self.assertEqual(TABLE.c.secret_digest.type.length, 64)


class StoreTests(unittest.TestCase):
    def test_fingerprints_are_canonical_domain_separated_and_non_reversible_storage(self):
        self.assertEqual(session_reference(TOKEN), REFERENCE)
        self.assertNotEqual(REFERENCE.digest, csrf_fingerprint(TOKEN))
        self.assertEqual(len(REFERENCE.digest), 64)
        for invalid in (None, True, TOKEN + "=", "a" * 43, "!" * 43):
            with self.subTest(invalid=type(invalid).__name__), self.assertRaises(SessionStoreRejected):
                session_reference(invalid)

    def test_creation_commits_then_returns_only_ephemeral_secrets(self):
        h = Harness()
        issued = h.store().create()
        self.assertIs(type(issued), IssuedSession)
        self.assertEqual(issued.record.reference, session_reference(issued.secret))
        self.assertEqual(issued.record.policy, SessionPolicy())
        row = h.rows[issued.record.reference.digest]
        self.assertEqual(row["csrf_digest"], csrf_fingerprint(issued.csrf_token))
        self.assertNotIn(issued.secret, repr(h.rows))
        self.assertNotIn(issued.csrf_token, repr(h.rows))
        self.assertNotIn(issued.secret, repr(issued))
        self.assertEqual(h.events[-2:], ["commit", "close"])
        self.assertLess(h.events.index("lock:local_users"), h.events.index("clock"))
        self.assertLess(h.events.index("lock:external_identities"), h.events.index("insert"))
        read = h.store().read(issued.record.reference)
        self.assertEqual(read, issued.record)
        self.assertIs(decide_authorization(identity=read.identity, company_id=7,
                                           permission=Permission.PREDICTIONS_ANALYZE).effect, AuthorizationEffect.DENY)

    def test_read_and_touch_use_post_lock_clock_and_preserve_absolute_expiry(self):
        h = Harness(stored())
        h.now = NOW + timedelta(minutes=1)
        h.server_now = NOW + timedelta(minutes=2)
        updated = h.store().touch(REFERENCE)
        self.assertEqual(updated.last_activity_at, h.server_now)
        self.assertEqual(updated.absolute_expires_at, NOW + timedelta(hours=8))
        self.assertEqual(h.rows[REFERENCE.digest]["last_activity_at"], h.server_now)
        self.assertLess(h.events.index("lock:application_sessions"), h.events.index("clock"))

    def test_idle_absolute_and_revoked_sessions_refused_without_writes(self):
        cases = ((stored(), NOW + timedelta(minutes=30), Reason.IDLE_EXPIRED),
                 (stored(last_activity_at=NOW + timedelta(hours=7, minutes=59)),
                  NOW + timedelta(hours=8), Reason.ABSOLUTE_EXPIRED),
                 (stored(revoked_at=NOW), NOW, Reason.REVOKED))
        for row, now, reason in cases:
            for operation in ("read", "touch", "revoke", "rotate"):
                with self.subTest(reason=reason, operation=operation):
                    h = Harness(row)
                    h.now = h.server_now = now
                    with self.assertRaises(SessionStoreRejected) as caught:
                        getattr(h.store(), operation)(REFERENCE)
                    self.assertIs(caught.exception.reason, reason)
                    self.assertEqual(h.rows, {REFERENCE.digest: row})
                    self.assertNotIn("commit", h.events)

    def test_server_expiry_after_wait_is_not_accepted_by_stale_caller_clock(self):
        h = Harness(stored())
        h.now = NOW + timedelta(minutes=29)
        h.server_now = NOW + timedelta(minutes=30)
        with self.assertRaises(SessionStoreRejected):
            h.store().touch(REFERENCE)
        self.assertNotIn("update", h.events)

    def test_revoke_is_durable_in_simulation_and_repeat_is_rejected(self):
        h = Harness(stored())
        result = h.store().revoke(REFERENCE)
        self.assertEqual(result.revoked_at, NOW)
        self.assertEqual(h.rows[REFERENCE.digest]["revoked_at"], NOW)
        with self.assertRaises(SessionStoreRejected):
            h.store().read(REFERENCE)

    def test_rotation_replaces_csrf_and_invalidates_old_reference_in_one_commit(self):
        h = Harness(stored())
        h.now = h.server_now = NOW + timedelta(minutes=1)
        issued = h.store().rotate(REFERENCE)
        self.assertEqual(len(h.rows), 2)
        self.assertEqual(h.rows[REFERENCE.digest]["replaced_by"], issued.record.reference.digest)
        self.assertEqual(issued.record.absolute_expires_at, NOW + timedelta(hours=8))
        self.assertNotEqual(h.rows[REFERENCE.digest]["csrf_digest"], h.rows[issued.record.reference.digest]["csrf_digest"])
        self.assertEqual(h.events.count("commit"), 1)
        self.assertLess(h.events.index("insert"), h.events.index("update"))
        with self.assertRaises(SessionStoreRejected) as caught:
            h.store().read(REFERENCE)
        self.assertIs(caught.exception.reason, Reason.ROTATED)
        self.assertEqual(h.store().read(issued.record.reference), issued.record)

    def test_competing_rotations_simulated_by_mutex_allow_one_success(self):
        h = Harness(stored())
        def attempt():
            try:
                return h.store().rotate(REFERENCE)
            except SessionStoreRejected:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sum(outcome is not None for outcome in outcomes), 1)
        self.assertEqual(len(h.rows), 2)
        self.assertEqual(h.events.count("commit"), 1)

    def test_failed_rotation_rolls_back_successor_and_original_together(self):
        for failure, error in (("update", SessionStoreUnavailable), ("lost_update", SessionStoreIncoherent)):
            h = Harness(stored())
            h.failure = failure
            with self.subTest(failure=failure), self.assertRaises(error):
                h.store().rotate(REFERENCE)
            self.assertEqual(h.rows, {REFERENCE.digest: stored()})
            self.assertIn("rollback", h.events)
            self.assertNotIn("commit", h.events)

    def test_commit_uncertainty_does_not_disclose_secrets_or_retry(self):
        for failure in ("commit_before", "commit_after"):
            h = Harness(stored())
            h.failure = failure
            with self.subTest(failure=failure), self.assertRaises(SessionStoreCommitUncertain) as caught:
                h.store().rotate(REFERENCE)
            self.assertNotIn(PRIVATE, str(caught.exception))
            self.assertIsNone(caught.exception.__context__)
            self.assertIsNone(caught.exception.__cause__)
            self.assertEqual(h.events.count("commit"), 1)
            self.assertEqual(h.events.count("rollback"), 1)
            self.assertEqual(len(h.rows), 1 if failure == "commit_before" else 2)

    def test_acquisition_execution_and_cleanup_failures_are_sanitized(self):
        for failure in ("acquire", "execute"):
            h = Harness(stored())
            h.failure = failure
            with self.assertRaises(SessionStoreUnavailable) as caught:
                h.store().read(REFERENCE)
            self.assertNotIn(PRIVATE, repr(caught.exception))
            self.assertIsNone(caught.exception.__context__)
        h = Harness(stored())
        h.failure = "close"
        self.assertEqual(h.store().read(REFERENCE).identity, IDENTITY)

    def test_unapproved_or_malformed_admission_never_inserts(self):
        for admission in (None, True, {"verified": True, "user_id": 17},
                          AdmissionDecision(Outcome.FORBIDDEN, Reason.UNKNOWN_IDENTITY),
                          AdmissionDecision(Outcome.READY, Reason.VALID),
                          AdmissionDecision(Outcome.READY, Reason.UNKNOWN_IDENTITY, IDENTITY)):
            h = Harness()
            h.admission.admit.return_value = admission
            with self.subTest(admission=type(admission).__name__), self.assertRaises((SessionStoreRejected, SessionStoreIncoherent)):
                h.store().create()
            self.assertNotIn("insert", h.events)

    def test_admission_or_account_unavailability_is_not_success(self):
        for admission, expected in ((AdmissionDecision(Outcome.UNAVAILABLE, Reason.PROVIDER_UNAVAILABLE), SessionStoreUnavailable),
                                    (AdmissionDecision(Outcome.INCOHERENT, Reason.INVALID_STATE), SessionStoreIncoherent)):
            h = Harness()
            h.admission.admit.return_value = admission
            with self.assertRaises(expected):
                h.store().create()
        h = Harness(stored())
        h.users[0]["state"] = "suspended"
        for operation in (lambda: h.store().create(), lambda: h.store().read(REFERENCE)):
            with self.assertRaises(SessionStoreRejected) as caught:
                operation()
            self.assertIs(caught.exception.reason, Reason.ACCOUNT_INACTIVE)

    def test_link_user_pair_is_verified_on_creation_and_read(self):
        for rows in ((), (stored(),)):
            h = Harness(*rows)
            h.external[0]["user_id"] = 18
            with self.assertRaises(SessionStoreIncoherent):
                h.store().read(REFERENCE) if rows else h.store().create()
            self.assertNotIn("commit", h.events)

    def test_corrupt_rows_and_unknown_reference_fail_closed(self):
        for changes in ({"contract_version": "unknown"}, {"csrf_digest": "raw"},
                        {"absolute_expires_at": NOW + timedelta(hours=9)},
                        {"last_activity_at": NOW.replace(tzinfo=None)}, {"idle_timeout_seconds": True}):
            h = Harness(stored(**changes))
            with self.subTest(changes=changes), self.assertRaises(SessionStoreIncoherent):
                h.store().read(REFERENCE)
        with self.assertRaises(SessionStoreRejected):
            Harness().store().read(REFERENCE)

    def test_admin_methods_deny_by_default_and_do_not_trust_user_id_or_bool(self):
        h = Harness(stored())
        for authority in (None, Mock(return_value=True), Mock(side_effect=RuntimeError(PRIVATE))):
            store = h.store(require_user_session_administration=authority)
            for method in (store.sessions_for_user, store.revoke_for_user):
                with self.assertRaises(SessionStoreRejected):
                    method(17)
        self.assertEqual(h.events, [])

    def test_admin_enumeration_and_bulk_revoke_are_user_scoped(self):
        other = stored(secret_digest="d" * 64, user_id=18)
        h = Harness(stored(), other)
        h.users[0]["state"] = "suspended"
        store = h.store(require_user_session_administration=h.authority)
        self.assertEqual(store.sessions_for_user(17), (REFERENCE,))
        self.assertEqual(store.revoke_for_user(17), 1)
        self.assertEqual(h.rows[REFERENCE.digest]["revoked_at"], NOW)
        self.assertIsNone(h.rows["d" * 64]["revoked_at"])
        h.authority.assert_called_with(user_id=17)

    def test_bulk_revoke_rejects_incoherent_future_activity_without_partial_update(self):
        h = Harness(stored(last_activity_at=NOW + timedelta(minutes=1)))
        with self.assertRaises(SessionStoreIncoherent):
            h.store(require_user_session_administration=h.authority).revoke_for_user(17)
        self.assertNotIn("update", h.events)

    def test_unsafe_engine_logging_is_rejected_before_sql(self):
        for field, value in (("echo", True), ("hide_parameters", False),
                             ("logger", SimpleNamespace(isEnabledFor=lambda level: True))):
            h = Harness(stored())
            setattr(h.engine, field, value)
            with self.assertRaises(SessionStoreUnavailable):
                h.store().read(REFERENCE)
            self.assertEqual(h.statements, [])

    def test_csprng_failures_and_collisions_are_not_retried(self):
        for output in ((b"b" * 32, b"b" * 32), (b"short", b"c" * 32)):
            h = Harness()
            with patch("app.application_session_store.secrets.token_bytes", side_effect=output) as draw:
                with self.assertRaises(SessionStoreIncoherent):
                    h.store().create()
                self.assertEqual(draw.call_count, 2)
            self.assertEqual(h.rows, {})
        h = Harness(stored())
        with patch("app.application_session_store.secrets.token_bytes", side_effect=(b"a" * 32, b"c" * 32)):
            with self.assertRaises(SessionStoreUnavailable):
                h.store().create()
        self.assertEqual(h.rows, {REFERENCE.digest: stored()})

    def test_read_sql_is_bounded_locked_and_scoped(self):
        h = Harness(stored())
        h.store().read(REFERENCE)
        sql = [str(statement.compile(dialect=postgresql.dialect())) for statement in h.statements]
        self.assertTrue(any("FOR UPDATE" in query and "local_users" in query for query in sql))
        self.assertTrue(any("FOR UPDATE" in query and "application_sessions" in query for query in sql))
        self.assertTrue(any("FOR SHARE" in query and "external_identities.user_id" in query for query in sql))
        self.assertIn("SET LOCAL lock_timeout = '5s'", sql)
        self.assertIn("SET LOCAL statement_timeout = '15s'", sql)
        self.assertFalse(any(TOKEN in query or CSRF in query for query in sql))

    def test_no_client_company_or_identity_argument_and_no_implicit_runtime(self):
        h = Harness()
        for arguments in ({"user_id": 17}, {"company_id": 7}, {"identity": IDENTITY}):
            with self.assertRaises(TypeError):
                h.store().create(**arguments)
        with self.assertRaises(SessionStoreIncoherent):
            PostgresApplicationSessionStore(None, admission_provider=h.admission, clock=lambda: NOW)
        self.assertEqual(h.events, [])


if __name__ == "__main__":
    unittest.main()
