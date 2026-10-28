"""Offline adapter tests: simulations/SQL compilation, never PostgreSQL proof."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone, tzinfo
import logging
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql.dml import Delete, Insert
from sqlalchemy.sql.elements import BindParameter

from app.core.database_runtime import SqlRuntime
from app.core.oidc_transactions import (
    ConsumptionCondition, ConsumeStatus, InsertStatus,
    OidcTransaction, TransactionCommitUncertain, TransactionStoreUnavailable,
)
from app.models.oidc_transaction import OidcTransactionRecord
from app.oidc_transaction_store import PostgresTransactionStore


NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
SECRET = "SYNTHETIC-DRIVER-DETAIL-NEVER-EXPOSE"
TABLE = OidcTransactionRecord.__table__


class SensitiveTimezone(tzinfo):
    def __init__(self):
        self.calls = 0

    def utcoffset(self, dt):
        self.calls += 1
        raise RuntimeError(SECRET)


def transaction(**changes):
    return replace(OidcTransaction(
        "a" * 64, "b" * 64, "c" * 64, "A" * 43, "E" * 42 + "A",
        "https://issuer.example.invalid", "synthetic-client",
        "https://app.example.invalid/callback", "d" * 64, "dashboard",
        NOW, NOW + timedelta(seconds=300)), **changes)


def condition(**changes):
    return replace(ConsumptionCondition("b" * 64, "c" * 64, "d" * 64,
                                        NOW + timedelta(seconds=1)), **changes)


def integrity(constraint="pk_oidc_transactions", state="23505"):
    original = RuntimeError(SECRET)
    original.sqlstate = state
    original.diag = SimpleNamespace(constraint_name=constraint)
    return IntegrityError(SECRET, {"secret": SECRET}, original)


class Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def mappings(self):
        return self

    def one_or_none(self):
        return self.value


class SimulatedSession:
    """Deterministic statement interpreter, not a concurrency/locking emulator."""

    def __init__(self, harness):
        self.h = harness
        self.rows = dict(harness.rows)
        self.commit_count = self.rollback_count = self.close_count = 0
        self.statements = []

    def connection(self, *, execution_options):
        self.h.events.append(("isolation", execution_options))
        if self.h.failure == "acquire":
            raise RuntimeError(SECRET)

    def matches(self, statement, row):
        for predicate in statement._where_criteria:
            left, right = predicate.left, predicate.right
            value = right.value if isinstance(right, BindParameter) else row[right.name]
            if not predicate.operator(row[left.name], value):
                return False
        return True

    def execute(self, statement):
        self.statements.append(statement)
        if self.h.failure == "execute":
            raise RuntimeError(SECRET)
        if not hasattr(statement, "selected_columns") and not isinstance(statement, (Insert, Delete)):
            self.h.events.append(str(statement))
            return Result()
        if isinstance(statement, Insert):
            self.h.events.append("insert")
            if self.h.insert_error:
                raise self.h.insert_error
            row = {key: value.value for key, value in statement._values.items()}
            for existing in self.rows.values():
                if existing["transaction_id"] == row["transaction_id"]:
                    raise integrity()
                if existing["state_digest"] == row["state_digest"]:
                    raise integrity("uq_oidc_transactions_state_digest")
            self.rows[row["transaction_id"]] = row
            return Result()
        if isinstance(statement, Delete):
            self.h.events.append("delete")
            for key, row in tuple(self.rows.items()):
                if self.matches(statement, row):
                    del self.rows[key]
                    return Result(dict(row))
            return Result()
        if "clock_timestamp" in str(statement):
            self.h.events.append("decision")
            return Result(self.h.decision)
        self.h.events.append("lock")
        found = next((r["transaction_id"] for r in self.rows.values() if self.matches(statement, r)), None)
        if found is not None and self.h.after_lock:
            self.h.after_lock()
        return Result(found)

    def commit(self):
        self.h.events.append("commit")
        self.commit_count += 1
        if self.h.commit_entered:
            self.h.commit_entered.set()
            if not self.h.release_commit.wait(5):
                raise RuntimeError("Test synchronization timed out")
        if self.h.failure == "commit_before_apply":
            raise RuntimeError(SECRET)
        self.h.rows = dict(self.rows)
        if self.h.failure == "commit_after_apply":
            raise RuntimeError(SECRET)

    def rollback(self):
        self.h.events.append("rollback")
        self.rollback_count += 1
        if self.h.rollback_error:
            raise RuntimeError(SECRET)

    def close(self):
        self.h.events.append("close")
        self.close_count += 1
        if self.h.close_error:
            raise RuntimeError(SECRET)


class Harness:
    def __init__(self, *rows):
        self.rows = {row.transaction_id: asdict(row) for row in rows}
        self.sessions = []
        self.events = []
        self.decision = NOW + timedelta(seconds=2)
        self.failure = self.insert_error = self.after_lock = None
        self.rollback_error = self.close_error = False
        self.commit_entered = self.release_commit = None
        engine = Mock(echo=False, hide_parameters=True)
        engine.logger.isEnabledFor.return_value = False
        self.runtime = SqlRuntime(engine, self.factory)
        self.store = PostgresTransactionStore(self.runtime)

    def factory(self):
        session = SimulatedSession(self)
        self.sessions.append(session)
        return session


class AdapterTests(unittest.TestCase):
    def setUp(self):
        # Any accidental real database/network use fails before doing I/O.
        for name in ("sqlalchemy.create_engine", "app.core.database_runtime.create_engine",
                     "sqlalchemy.engine.Engine.connect", "sqlalchemy.engine.Engine.raw_connection",
                     "psycopg.connect", "socket.create_connection", "socket.socket.connect",
                     "socket.socket.connect_ex", "socket.getaddrinfo"):
            guard = patch(name, side_effect=AssertionError("Real SQL/network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def assert_sanitized(self, error):
        self.assertNotIn(SECRET, str(error))
        self.assertNotIn(SECRET, repr(error))
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)

    def assert_closed(self, h):
        for db in h.sessions:
            self.assertEqual(db.close_count, 1)

    def test_mapping_and_postgresql_constraints(self):
        self.assertEqual(TABLE.schema, "public")
        self.assertEqual(set(TABLE.c.keys()), set(asdict(transaction())))
        self.assertTrue(all(not column.nullable for column in TABLE.c))
        self.assertEqual([c.name for c in TABLE.primary_key], ["transaction_id"])
        self.assertEqual(TABLE.primary_key.name, "pk_oidc_transactions")
        self.assertEqual(len(TABLE.foreign_keys), 0)
        self.assertEqual({i.name for i in TABLE.indexes}, {"ix_oidc_transactions_expires_at"})
        self.assertTrue(TABLE.c.created_at.type.timezone)
        self.assertTrue(TABLE.c.expires_at.type.timezone)
        ddl = str(CreateTable(TABLE).compile(dialect=postgresql.dialect()))
        for column in ("transaction_id", "state_digest", "browser_binding_digest", "policy_digest"):
            self.assertIn(f"{column} ~ '^[0-9a-f]{{64}}$'", ddl)
        self.assertIn("CONSTRAINT uq_oidc_transactions_state_digest UNIQUE (state_digest)", ddl)
        self.assertIn("CHECK (expires_at > created_at)", ddl)
        for name in ("nonce", "code_verifier"):
            self.assertEqual(TABLE.c[name].type.length, 43)
        self.assertTrue(all(c.default is None and c.server_default is None for c in TABLE.c))

    def test_insert_confirmed_without_pre_read_and_separate_sessions(self):
        h = Harness()
        self.assertIs(h.store.insert_new(transaction()), InsertStatus.CONFIRMED)
        self.assertIs(h.store.insert_new(transaction(transaction_id="e" * 64, state_digest="f" * 64)), InsertStatus.CONFIRMED)
        self.assertEqual(len(h.sessions), 2)
        self.assertIsNot(h.sessions[0], h.sessions[1])
        self.assertEqual(h.events.count("insert"), 2)
        self.assertNotIn("lock", h.events)
        for db in h.sessions:
            self.assertEqual(db.commit_count, 1)
            self.assertEqual(db.rollback_count, 0)
        self.assert_closed(h)

    def test_unique_collisions_never_overwrite_or_retry(self):
        for tx in (transaction(state_digest="f" * 64), transaction(transaction_id="f" * 64)):
            with self.subTest(tx_id=tx.transaction_id):
                original = transaction()
                h = Harness(original)
                self.assertIs(h.store.insert_new(tx), InsertStatus.COLLISION)
                self.assertEqual(h.rows, {original.transaction_id: asdict(original)})
                self.assertEqual(h.events.count("insert"), 1)
                self.assertEqual(h.sessions[0].rollback_count, 1)
                self.assertEqual(h.sessions[0].commit_count, 0)
                self.assert_closed(h)

    def test_unexpected_integrity_errors_are_not_collisions(self):
        for error in (integrity("other_unique"), integrity(state="23514"), RuntimeError(SECRET)):
            h = Harness()
            h.insert_error = error
            with self.assertRaises(TransactionStoreUnavailable) as caught:
                h.store.insert_new(transaction())
            self.assert_sanitized(caught.exception)
            self.assertEqual(h.events.count("insert"), 1)
            self.assert_closed(h)

    def test_precommit_connection_and_execution_failure(self):
        for failure in ("acquire", "execute"):
            h = Harness(transaction())
            h.failure = failure
            with self.assertRaises(TransactionStoreUnavailable) as caught:
                h.store.consume(condition())
            self.assert_sanitized(caught.exception)
            self.assertEqual(h.sessions[0].rollback_count, 1)
            self.assertEqual(h.sessions[0].commit_count, 0)
            self.assertEqual(len(h.rows), 1)
            self.assert_closed(h)

    def test_commit_uncertainty_in_both_methods_never_retries(self):
        for insert_operation in (True, False):
            for failure in ("commit_before_apply", "commit_after_apply"):
                h = Harness(*(() if insert_operation else (transaction(),)))
                h.failure = failure
                h.rollback_error = True
                with self.assertRaises(TransactionCommitUncertain) as caught:
                    if insert_operation:
                        h.store.insert_new(transaction())
                    else:
                        h.store.consume(condition())
                self.assert_sanitized(caught.exception)
                self.assertEqual(h.sessions[0].commit_count, 1)
                self.assertEqual(h.sessions[0].rollback_count, 1)
                self.assertEqual(h.events.count("insert" if insert_operation else "delete"), 1)
                self.assert_closed(h)

    def test_consumption_confirmed_then_replay_rejected(self):
        h = Harness(transaction())
        receipt = h.store.consume(condition())
        self.assertIs(receipt.status, ConsumeStatus.CONFIRMED)
        self.assertEqual(receipt.transaction, transaction())
        self.assertEqual(h.rows, {})
        replay = h.store.consume(condition())
        self.assertIs(replay.status, ConsumeStatus.REJECTED)
        self.assertIsNone(replay.transaction)
        self.assert_closed(h)

    def test_mismatches_are_non_destructive(self):
        for changes in ({"state_digest": "e" * 64}, {"browser_binding_digest": "e" * 64},
                        {"policy_digest": "e" * 64}, {"contract_version": "other-version"}):
            h = Harness(transaction())
            receipt = h.store.consume(condition(**changes))
            self.assertIs(receipt.status, ConsumeStatus.REJECTED)
            self.assertIsNone(receipt.transaction)
            self.assertNotIn("delete", h.events)
            self.assertNotIn("decision", h.events)
            self.assertEqual(len(h.rows), 1)
            self.assertIs(h.store.consume(condition()).status, ConsumeStatus.CONFIRMED)
            self.assert_closed(h)

    def test_both_temporal_intervals_and_exact_expiry(self):
        expires = transaction().expires_at
        for caller_now, decision, expected in (
            (NOW, NOW, ConsumeStatus.CONFIRMED),
            (NOW - timedelta(microseconds=1), NOW, ConsumeStatus.REJECTED),
            (expires, NOW, ConsumeStatus.REJECTED),
            (NOW, NOW - timedelta(microseconds=1), ConsumeStatus.REJECTED),
            (NOW, expires, ConsumeStatus.REJECTED),
            (NOW, expires + timedelta(microseconds=1), ConsumeStatus.REJECTED),
            (expires - timedelta(microseconds=1), expires - timedelta(microseconds=1), ConsumeStatus.CONFIRMED),
        ):
            with self.subTest(caller_now=caller_now, decision=decision):
                h = Harness(transaction())
                h.decision = decision
                receipt = h.store.consume(condition(now=caller_now))
                self.assertIs(receipt.status, expected)
                self.assertEqual(bool(h.rows), expected is ConsumeStatus.REJECTED)

    def test_decision_after_simulated_lock_wait(self):
        h = Harness(transaction())
        h.after_lock = lambda: setattr(h, "decision", transaction().expires_at)
        receipt = h.store.consume(condition())
        self.assertIs(receipt.status, ConsumeStatus.REJECTED)
        self.assertEqual(len(h.rows), 1)
        self.assertLess(h.events.index("lock"), h.events.index("decision"))
        self.assertLess(h.events.index("decision"), h.events.index("delete"))
        self.assert_closed(h)

    def test_lock_timeout_is_failure_not_rejection(self):
        h = Harness(transaction())
        h.after_lock = Mock(side_effect=RuntimeError(SECRET))
        with self.assertRaises(TransactionStoreUnavailable) as caught:
            h.store.consume(condition())
        self.assert_sanitized(caught.exception)
        self.assertNotIn("decision", h.events)
        self.assertNotIn("delete", h.events)
        self.assertNotIn("commit", h.events)
        self.assert_closed(h)

    def test_sql_has_all_guards_and_is_parameterized(self):
        h = Harness(transaction())
        h.store.consume(condition())
        lock, clock, removal = h.sessions[0].statements[2:]
        lock_sql = str(lock.compile(dialect=postgresql.dialect()))
        self.assertTrue(lock_sql.endswith("FOR UPDATE"))
        self.assertEqual(str(clock.compile(dialect=postgresql.dialect())), "SELECT clock_timestamp() AS clock_timestamp_1")
        sql = str(removal.compile(dialect=postgresql.dialect()))
        self.assertIn("DELETE FROM public.oidc_transactions", sql)
        self.assertIn("RETURNING", sql)
        for name in ("state_digest", "browser_binding_digest", "policy_digest", "contract_version", "transaction_id"):
            self.assertIn(f"oidc_transactions.{name} = %(", sql)
        self.assertEqual(sql.count("oidc_transactions.created_at <= %("), 2)
        self.assertEqual(sql.count("oidc_transactions.expires_at > %("), 2)
        self.assertNotIn("b" * 64, sql)
        self.assertEqual(h.events[0], ("isolation", {"isolation_level": "READ COMMITTED"}))
        self.assertIn("SET LOCAL lock_timeout = '5s'", h.events)
        self.assertIn("SET LOCAL statement_timeout = '15s'", h.events)
        self.assertEqual(h.runtime.engine.mock_calls, [unittest.mock.call.logger.isEnabledFor(logging.DEBUG)])

    def test_no_return_before_commit_acknowledgement(self):
        for inserting in (True, False):
            h = Harness(*(() if inserting else (transaction(),)))
            h.commit_entered, h.release_commit = Event(), Event()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(h.store.insert_new, transaction()) if inserting else executor.submit(h.store.consume, condition())
                try:
                    self.assertTrue(h.commit_entered.wait(3))
                    self.assertFalse(future.done())
                    # Expiration after the recorded decision is admissible.
                    h.decision = NOW + timedelta(days=1)
                finally:
                    h.release_commit.set()
                result = future.result(timeout=3)
            self.assertIs(result if inserting else result.status,
                          InsertStatus.CONFIRMED if inserting else ConsumeStatus.CONFIRMED)
            self.assert_closed(h)

    def test_close_failure_does_not_undo_acknowledged_commit(self):
        h = Harness()
        h.close_error = True
        self.assertIs(h.store.insert_new(transaction()), InsertStatus.CONFIRMED)
        self.assert_closed(h)

    def test_invalid_inputs_and_unsafe_logging_never_acquire_session(self):
        for tx in (transaction(transaction_id="invalid"), transaction(nonce="secret"),
                   transaction(created_at=NOW.replace(tzinfo=None))):
            h = Harness()
            with self.assertRaises(TransactionStoreUnavailable):
                h.store.insert_new(tx)
            self.assertEqual(h.sessions, [])
        for field, value in (("echo", True), ("hide_parameters", False), ("debug", True)):
            h = Harness()
            if field == "debug":
                h.runtime.engine.logger.isEnabledFor.return_value = True
            else:
                setattr(h.runtime.engine, field, value)
            with self.assertRaises(TransactionStoreUnavailable):
                h.store.consume(condition())
            self.assertEqual(h.sessions, [])

    def test_insert_validation_exception_is_sanitized_before_session(self):
        h = Harness()
        zone = SensitiveTimezone()
        tx = transaction(created_at=NOW.replace(tzinfo=zone))
        with patch.object(h.runtime, "session", wraps=h.runtime.session) as acquire:
            with self.assertRaises(TransactionStoreUnavailable) as caught:
                h.store.insert_new(tx)
            acquire.assert_not_called()
        self.assertEqual(zone.calls, 1)
        self.assert_sanitized(caught.exception)
        self.assertEqual(str(caught.exception), "OIDC_TRANSACTION_STORE_UNAVAILABLE")
        self.assertEqual(caught.exception.args, ("OIDC_TRANSACTION_STORE_UNAVAILABLE",))
        self.assertNotIn(SECRET, "".join(traceback.format_exception(caught.exception)))
        self.assertEqual(h.sessions, [])
        self.assertEqual(h.events, [])
        self.assertEqual(h.rows, {})

    def test_consume_validation_exception_is_sanitized_before_session(self):
        original = transaction()
        h = Harness(original)
        zone = SensitiveTimezone()
        invalid = condition(now=NOW.replace(tzinfo=zone))
        with patch.object(h.runtime, "session", wraps=h.runtime.session) as acquire:
            with self.assertRaises(TransactionStoreUnavailable) as caught:
                h.store.consume(invalid)
            acquire.assert_not_called()
        self.assertEqual(zone.calls, 1)
        self.assert_sanitized(caught.exception)
        self.assertEqual(str(caught.exception), "OIDC_TRANSACTION_STORE_UNAVAILABLE")
        self.assertEqual(caught.exception.args, ("OIDC_TRANSACTION_STORE_UNAVAILABLE",))
        self.assertNotIn(SECRET, "".join(traceback.format_exception(caught.exception)))
        self.assertEqual(h.sessions, [])
        self.assertEqual(h.events, [])
        self.assertEqual(h.rows, {original.transaction_id: asdict(original)})

    def test_database_timezone_normalizes_to_utc(self):
        offset = timezone(timedelta(hours=2))
        row = transaction(created_at=NOW.astimezone(offset),
                          expires_at=transaction().expires_at.astimezone(offset))
        h = Harness(row)
        h.decision = h.decision.astimezone(offset)
        receipt = h.store.consume(condition())
        self.assertEqual(receipt.transaction, transaction())
        self.assertIs(receipt.transaction.created_at.tzinfo, timezone.utc)

    def test_naive_database_clock_rolls_back_without_delete(self):
        h = Harness(transaction())
        h.decision = NOW.replace(tzinfo=None)
        with self.assertRaises(TransactionStoreUnavailable) as caught:
            h.store.consume(condition())
        self.assert_sanitized(caught.exception)
        self.assertNotIn("delete", h.events)
        self.assertEqual(len(h.rows), 1)
        self.assert_closed(h)

    def test_materialization_failure_rolls_back_delete_before_commit(self):
        h = Harness(transaction())
        h.rows[transaction().transaction_id]["nonce"] = "invalid-stored-secret"
        original = dict(h.rows[transaction().transaction_id])
        with self.assertRaises(TransactionStoreUnavailable) as caught:
            h.store.consume(condition())
        self.assert_sanitized(caught.exception)
        self.assertNotIn("invalid-stored-secret", repr(caught.exception))
        self.assertIn("delete", h.events)
        self.assertNotIn("commit", h.events)
        self.assertEqual(h.sessions[0].rollback_count, 1)
        self.assertEqual(h.rows[transaction().transaction_id], original)
        self.assert_closed(h)

    def test_session_factory_failure_and_closed_runtime_are_sanitized(self):
        h = Harness()
        factory = Mock(side_effect=RuntimeError(SECRET))
        store = PostgresTransactionStore(SqlRuntime(h.runtime.engine, factory))
        with self.assertRaises(TransactionStoreUnavailable) as caught:
            store.insert_new(transaction())
        self.assert_sanitized(caught.exception)
        factory.assert_called_once_with()
        h.runtime.dispose()
        with self.assertRaises(TransactionStoreUnavailable) as caught:
            h.store.consume(condition())
        self.assert_sanitized(caught.exception)
        self.assertEqual(h.sessions, [])

    def test_inert_import_in_fresh_process(self):
        root = Path(__file__).resolve().parents[2]
        script = r'''
import importlib.abc, sys
from contextlib import ExitStack
from unittest.mock import patch
import sqlalchemy, sqlalchemy.orm, psycopg
sys.path.insert(0, sys.argv[1])
def forbidden(*args, **kwargs): raise AssertionError('Implicit I/O forbidden')
class BlockLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('app.core.database','app.core.config','app.main','dotenv','pydantic_settings'):
            forbidden()
sys.meta_path.insert(0, BlockLegacy())
with ExitStack() as guards:
    for name in ('sqlalchemy.create_engine','sqlalchemy.engine_from_config',
                 'sqlalchemy.orm.sessionmaker','sqlalchemy.orm.Session',
                 'sqlalchemy.engine.Engine.connect','psycopg.connect',
                 'socket.create_connection','socket.socket.connect','socket.getaddrinfo'):
        guards.enter_context(patch(name, side_effect=forbidden))
    from app.oidc_transaction_store import PostgresTransactionStore
    from app.core.database_runtime import SqlRuntime
    from unittest.mock import Mock
    store = PostgresTransactionStore(SqlRuntime(Mock(), Mock(side_effect=forbidden)))
    assert 'app.core.database' not in sys.modules
    assert 'fastapi' not in sys.modules
'''
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if key in os.environ}
        env.update(DATABASE_URL="invalid://ambient", PGHOST="ambient.invalid")
        result = subprocess.run([sys.executable, "-B", "-I", "-c", script, str(root / "backend")],
                                cwd=root, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
