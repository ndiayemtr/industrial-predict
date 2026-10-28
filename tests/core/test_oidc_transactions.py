"""Memory-store simulations only: NOT proof of PostgreSQL atomicity or commits."""

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import textwrap
from threading import Barrier, Lock
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.oidc_config import OidcConfig
from app.core import oidc_transactions as module


NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


def config(**updates):
    data = dict(issuer="https://identity.example.invalid/Realm", client_id="synthetic-client",
                callback_url="https://app.example.invalid/api/v1/auth/callback",
                signature_algorithms=("RS256", "ES256"), deployment_mode="production",
                transaction_ttl_seconds=300, clock_skew_seconds=30, max_id_token_age_seconds=600)
    data.update(updates)
    return OidcConfig(**data)


class SimulatedStore:
    """Lock-serialized conditional removal, confined to tests in one process."""

    def __init__(self):
        self.rows = {}
        self.lock = Lock()
        self.insert_calls = self.consume_calls = 0

    def insert_new(self, transaction):
        with self.lock:
            self.insert_calls += 1
            if (transaction.state_digest in self.rows
                    or any(row.transaction_id == transaction.transaction_id for row in self.rows.values())):
                return module.InsertStatus.COLLISION
            self.rows[transaction.state_digest] = transaction
            return module.InsertStatus.CONFIRMED

    def consume(self, condition):
        with self.lock:
            self.consume_calls += 1
            tx = self.rows.get(condition.state_digest)
            if (tx is None or tx.browser_binding_digest != condition.browser_binding_digest
                    or tx.policy_digest != condition.policy_digest or tx.contract_version != condition.contract_version
                    or not tx.created_at <= condition.now < tx.expires_at):
                return module.ConsumptionReceipt(module.ConsumeStatus.REJECTED)
            del self.rows[condition.state_digest]
            return module.ConsumptionReceipt(module.ConsumeStatus.CONFIRMED, tx)


class OidcTransactionTests(unittest.TestCase):
    def setUp(self):
        self.store = SimulatedStore()
        self.now = NOW
        self.clock = lambda: self.now
        self.manager = self.manager_for()

    def manager_for(self, **updates):
        values = dict(config=config(), store=self.store, clock=self.clock,
                      allowed_return_targets=("predictions", "dashboard"))
        values.update(updates)
        return module.OidcTransactionManager(**values)

    def start(self, **updates):
        return self.manager.create(return_target=updates.get("return_target", "predictions"))

    def consume(self, start, **updates):
        values = dict(state=start.state, browser_binding=start.browser_binding)
        values.update(updates)
        return self.manager.consume(**values)

    def test_creation_format_independent_draws_and_backend_only_storage(self):
        draws = [bytes([value]) * 32 for value in (1, 2, 3, 4)]
        with patch.object(module.secrets, "token_bytes", side_effect=draws) as random:
            start = self.start()
        self.assertEqual(random.call_count, 4)
        self.assertTrue(all(call.args == (32,) for call in random.call_args_list))
        tx = next(iter(self.store.rows.values()))
        values = (start.state, start.nonce, tx.code_verifier, start.browser_binding)
        self.assertEqual(len(set(values)), 4)
        for value in values:
            self.assertRegex(value, r"^[A-Za-z0-9_-]{43}$")
            self.assertEqual(len(base64.urlsafe_b64decode(value + "=")), 32)
        self.assertFalse(hasattr(start, "code_verifier"))
        self.assertEqual(start.code_challenge_method, "S256")
        self.assertEqual(start.code_challenge, module.pkce_s256(tx.code_verifier))
        self.assertEqual(tx.expires_at, NOW + timedelta(seconds=300))
        self.assertEqual(tx.contract_version, "oidc-transaction-v1")
        self.assertNotEqual(tx.state_digest, start.state)
        self.assertNotEqual(tx.browser_binding_digest, start.browser_binding)
        self.assertNotIn("state", {field.name for field in fields(tx)})
        self.assertNotIn("browser_binding", {field.name for field in fields(tx)})

    def test_independent_creations_have_different_secrets_and_identifiers(self):
        first, second = self.start(), self.start()
        self.assertNotEqual(first.transaction_id, second.transaction_id)
        self.assertEqual(len(self.store.rows), 2)
        all_values = [value for tx in self.store.rows.values() for value in (tx.nonce, tx.code_verifier)]
        all_values.extend((first.state, first.browser_binding, second.state, second.browser_binding))
        self.assertEqual(len(set(all_values)), 8)  # Sample sanity check, not proof of randomness.

    def test_pkce_rfc7636_reference_vector_and_strict_input(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        self.assertEqual(module.pkce_s256(verifier), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
        for value in (None, True, "a" * 42, "a" * 129, "é" * 43, "a" * 42 + "="):
            with self.subTest(kind=type(value).__name__), self.assertRaises(module.InvalidTransactionInput):
                module.pkce_s256(value)
        with self.assertRaises(TypeError):
            module.pkce_s256(verifier, method="plain")

    def test_use_before_expiry_and_unique_consumption(self):
        start = self.start()
        self.now += timedelta(seconds=299, microseconds=999999)
        tx = self.consume(start)
        self.assertEqual(tx.nonce, start.nonce)
        self.assertEqual(tx.return_target, "predictions")
        self.assertEqual(self.store.rows, {})
        with self.assertRaises(module.TransactionRejected):
            self.consume(start)
        self.assertEqual(self.store.insert_calls, 1)

    def test_expiration_exact_and_after_and_backward_clock(self):
        for offset in (timedelta(seconds=300), timedelta(seconds=301), timedelta(microseconds=-1)):
            self.now = NOW
            start = self.start()
            self.now = NOW + offset
            with self.subTest(offset=offset), self.assertRaises(module.TransactionRejected):
                self.consume(start)
        self.assertEqual(len(self.store.rows), 3)

    def test_invalid_or_absent_state_and_binding_refused_before_store(self):
        start = self.start()
        for field in ("state", "browser_binding"):
            for value in (None, True, "", "a" * 42, "a" * 44, "=" * 43, "_" * 43):
                with self.subTest(field=field, kind=type(value).__name__), self.assertRaises(module.TransactionRejected):
                    self.consume(start, **{field: value})
        self.assertEqual(self.store.consume_calls, 0)
        self.assertEqual(len(self.store.rows), 1)

    def test_wrong_state_or_browser_does_not_consume_legitimate_transaction(self):
        first, other = self.start(), self.start()
        for updates in (dict(browser_binding=other.browser_binding),
                        dict(state=other.state), dict(state=module._b64(b"z" * 32))):
            with self.assertRaises(module.TransactionRejected):
                self.consume(first, **updates)
        self.assertEqual(len(self.store.rows), 2)
        self.consume(first)
        self.consume(other)

    def test_parallel_transactions_do_not_cross_bind_secrets(self):
        first, other = self.start(), self.start(return_target="dashboard")
        with self.assertRaises(module.TransactionRejected):
            self.consume(first, browser_binding=other.browser_binding)
        self.assertEqual(self.consume(other).return_target, "dashboard")
        self.assertEqual(self.consume(first).return_target, "predictions")

    def test_policy_change_refuses_without_consuming(self):
        start = self.start()
        for changed in (config(client_id="other"), config(issuer="https://other.example.invalid"),
                        config(callback_url="https://app.example.invalid/other"), config(clock_skew_seconds=31)):
            manager = self.manager_for(config=changed)
            with self.assertRaises(module.TransactionRejected):
                manager.consume(state=start.state, browser_binding=start.browser_binding)
        with self.assertRaises(module.TransactionRejected):
            self.manager_for(allowed_return_targets=("predictions",)).consume(
                state=start.state, browser_binding=start.browser_binding)
        self.consume(start)

    def test_provider_error_terminates_once_without_returning_confidential_context(self):
        start = self.start()
        self.assertIsNone(self.consume(start, callback_outcome="provider_error"))
        with self.assertRaises(module.TransactionRejected):
            self.consume(start)
        self.assertEqual(self.store.rows, {})

    def test_uncorrelated_provider_error_does_not_terminate(self):
        first, other = self.start(), self.start()
        with self.assertRaises(module.TransactionRejected):
            self.consume(first, browser_binding=other.browser_binding, callback_outcome="provider_error")
        self.assertIsNone(self.consume(first, callback_outcome="provider_error"))
        self.consume(other)

    def test_unknown_callback_outcome_is_rejected_without_store_call(self):
        start = self.start()
        for outcome in (None, True, "plain", "success", "error"):
            with self.assertRaises(module.TransactionRejected):
                self.consume(start, callback_outcome=outcome)
        self.assertEqual(self.store.consume_calls, 0)

    def test_canonical_policy_independent_of_dictionary_algorithm_and_target_order(self):
        first = module.transaction_policy_digest(config(), allowed_return_targets=("predictions", "dashboard"))
        data = dict(reversed(list(config().model_dump().items())))
        data["signature_algorithms"] = ("ES256", "RS256")
        other = module.transaction_policy_digest(OidcConfig(**data), allowed_return_targets=("dashboard", "predictions"))
        self.assertEqual(first, other)
        self.assertRegex(first, r"^[0-9a-f]{64}$")

    def test_every_config_field_and_return_allowlist_participate_in_policy(self):
        baseline = module.transaction_policy_digest(config(), allowed_return_targets=("predictions",))
        changes = dict(issuer="https://identity.example.invalid/Other", client_id="Other",
                       callback_url="https://app.example.invalid/callback", signature_algorithms=("PS256",),
                       deployment_mode="development", transaction_ttl_seconds=301,
                       clock_skew_seconds=31, max_id_token_age_seconds=601)
        for field, value in changes.items():
            with self.subTest(field=field):
                self.assertNotEqual(baseline, module.transaction_policy_digest(config(**{field: value}),
                                                                             allowed_return_targets=("predictions",)))
        dev = config(deployment_mode="development")
        self.assertNotEqual(module.transaction_policy_digest(dev, allowed_return_targets=("predictions",)),
                            module.transaction_policy_digest(config(deployment_mode="development",
                                allow_http_loopback_callback=True), allowed_return_targets=("predictions",)))
        self.assertNotEqual(baseline, module.transaction_policy_digest(config(), allowed_return_targets=("dashboard",)))

    def test_invalid_return_destinations_and_config_are_refused(self):
        for target in ("https://other.invalid", "//other.invalid", "/predictions", "../dashboard", "missing", True):
            with self.assertRaises(module.InvalidTransactionInput):
                self.start(return_target=target)
        for targets in ((), ["predictions"], ("predictions", "predictions"), ("/path",), (True,)):
            with self.assertRaises(module.InvalidTransactionInput):
                self.manager_for(allowed_return_targets=targets)
        for cfg in (None, True, {}, config().model_copy(update={"issuer": "http://unsafe.invalid"})):
            with self.assertRaises(module.InvalidTransactionInput):
                self.manager_for(config=cfg)
        self.assertEqual(self.store.insert_calls, 0)

    def test_collision_never_overwrites_or_regenerates_automatically(self):
        draws = [bytes([value]) * 32 for value in (1, 2, 3, 4)] * 2
        with patch.object(module.secrets, "token_bytes", side_effect=draws) as random:
            first = self.start()
            original = next(iter(self.store.rows.values()))
            with self.assertRaises(module.TransactionCollision):
                self.start()
        self.assertEqual(random.call_count, 8)
        self.assertIs(next(iter(self.store.rows.values())), original)
        self.assertEqual(self.consume(first), original)

    def test_store_rejects_separate_identifier_and_state_collisions(self):
        self.start()
        tx = next(iter(self.store.rows.values()))
        self.assertIs(self.store.insert_new(replace(tx, state_digest="1" * 64)), module.InsertStatus.COLLISION)
        self.assertIs(self.store.insert_new(replace(tx, transaction_id="2" * 64)), module.InsertStatus.COLLISION)
        self.assertEqual(len(self.store.rows), 1)

    def test_generation_failures_are_sanitized_and_never_insert(self):
        for behavior in (dict(side_effect=RuntimeError("SYNTHETIC-PRIVATE")),
                         dict(return_value=b"short"), dict(return_value=b"x" * 32)):
            with patch.object(module.secrets, "token_bytes", **behavior):
                with self.assertRaises(module.TransactionGenerationFailed) as caught:
                    self.start()
            self.assertNotIn("SYNTHETIC-PRIVATE", str(caught.exception))
            self.assertIsNone(caught.exception.__context__)
        self.assertEqual(self.store.insert_calls, 0)

    def test_invalid_clock_and_store_are_refused_without_sql(self):
        for clock in (lambda: NOW.replace(tzinfo=None), lambda: None,
                      lambda: datetime.max.replace(tzinfo=timezone.utc), Mock(side_effect=RuntimeError("private"))):
            with self.assertRaises(module.InvalidTransactionInput):
                self.manager_for(clock=clock).create(return_target="predictions")
        for kwargs in (dict(clock=None), dict(store=None), dict(store=True)):
            with self.assertRaises(module.InvalidTransactionInput):
                self.manager_for(**kwargs)

    def test_insert_failure_uncertainty_and_invalid_confirmation_return_no_start(self):
        for result, error in ((module.InsertStatus.UNCERTAIN, module.TransactionCommitUncertain),
                              (None, module.TransactionStoreInvalid), (True, module.TransactionStoreInvalid)):
            store = Mock(spec=module.TransactionStore)
            store.insert_new.return_value = result
            with self.assertRaises(error):
                self.manager_for(store=store).create(return_target="predictions")
            store.insert_new.assert_called_once()
        for failure, error in ((RuntimeError("SYNTHETIC-PRIVATE"), module.TransactionStoreUnavailable),
                               (module.TransactionCommitUncertain(), module.TransactionCommitUncertain)):
            store = Mock(spec=module.TransactionStore)
            store.insert_new.side_effect = failure
            with self.assertRaises(error) as caught:
                self.manager_for(store=store).create(return_target="predictions")
            self.assertIsNone(caught.exception.__context__)
            store.insert_new.assert_called_once()

    def test_consumption_failures_and_uncertainty_never_release_context_or_retry(self):
        start = self.start()
        tx = next(iter(self.store.rows.values()))
        cases = ((module.ConsumptionReceipt(module.ConsumeStatus.UNCERTAIN, tx), module.TransactionCommitUncertain),
                 (module.ConsumptionReceipt(module.ConsumeStatus.CONFIRMED), module.TransactionStoreInvalid),
                 (module.ConsumptionReceipt(module.ConsumeStatus.REJECTED, tx), module.TransactionStoreInvalid),
                 (None, module.TransactionStoreInvalid), (True, module.TransactionStoreInvalid),
                 (object.__new__(module.ConsumptionReceipt), module.TransactionStoreInvalid))
        for receipt, error in cases:
            store = Mock(spec=module.TransactionStore)
            store.consume.return_value = receipt
            with self.assertRaises(error):
                self.manager_for(store=store).consume(state=start.state, browser_binding=start.browser_binding)
            store.consume.assert_called_once()
            store.insert_new.assert_not_called()
        for failure, error in ((RuntimeError(start.state), module.TransactionStoreUnavailable),
                               (module.TransactionCommitUncertain(), module.TransactionCommitUncertain)):
            store = Mock(spec=module.TransactionStore)
            store.consume.side_effect = failure
            with self.assertRaises(error) as caught:
                self.manager_for(store=store).consume(state=start.state, browser_binding=start.browser_binding)
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn(start.state, str(caught.exception))
            store.consume.assert_called_once()

    def test_uncertain_commit_can_remove_record_without_reactivation(self):
        start = self.start()
        underlying = self.store.consume

        def uncertain(condition):
            underlying(condition)  # Simulate commit succeeded but its acknowledgement was lost.
            return module.ConsumptionReceipt(module.ConsumeStatus.UNCERTAIN)

        with patch.object(self.store, "consume", side_effect=uncertain) as consume:
            with self.assertRaises(module.TransactionCommitUncertain):
                self.consume(start)
            consume.assert_called_once()
        self.assertEqual(self.store.rows, {})
        with self.assertRaises(module.TransactionRejected):
            self.consume(start)
        self.assertEqual(self.store.insert_calls, 1)

    def test_malformed_confirmed_records_are_never_returned(self):
        start = self.start()
        tx = next(iter(self.store.rows.values()))
        changes = dict(transaction_id="0" * 64, state_digest="0" * 64, browser_binding_digest="0" * 64,
                       policy_digest="0" * 64, nonce="bad", code_verifier="bad", issuer="other",
                       client_id="other", callback_url="other", return_target="https://other.invalid",
                       created_at=NOW.replace(tzinfo=None), expires_at=NOW, contract_version="other")
        for field, value in changes.items():
            store = Mock(spec=module.TransactionStore)
            store.consume.return_value = module.ConsumptionReceipt(module.ConsumeStatus.CONFIRMED,
                                                                    replace(tx, **{field: value}))
            with self.subTest(field=field), self.assertRaises(module.TransactionStoreInvalid):
                self.manager_for(store=store).consume(state=start.state, browser_binding=start.browser_binding)

    def test_two_concurrent_simulated_consumptions_have_exactly_one_winner(self):
        start = self.start()
        barrier = Barrier(2)

        def attempt(_):
            barrier.wait(timeout=5)
            try:
                return self.consume(start)
            except module.TransactionRejected:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(type(result) is module.OidcTransaction for result in results), 1)
        self.assertEqual(self.store.consume_calls, 2)
        self.assertEqual(self.store.rows, {})
        self.assertEqual(self.store.insert_calls, 1)

    def test_records_are_immutable_and_representations_hide_secrets(self):
        start = self.start()
        tx = next(iter(self.store.rows.values()))
        condition = module.ConsumptionCondition(tx.state_digest, tx.browser_binding_digest, tx.policy_digest, NOW)
        receipt = module.ConsumptionReceipt(module.ConsumeStatus.CONFIRMED, tx)
        for value in (tx, start, condition, receipt):
            for secret in (start.state, start.browser_binding, start.nonce, tx.code_verifier):
                self.assertNotIn(secret, repr(value))
            field = fields(value)[0].name
            with self.assertRaises(FrozenInstanceError):
                setattr(value, field, "private")
            self.assertFalse(hasattr(value, "__dict__"))
        names = {field.name for field in fields(tx)}
        self.assertFalse(names & {"access_token", "refresh_token", "id_token", "code", "user_id", "company_id",
                                 "role", "permission"})

    def test_import_and_construction_have_no_runtime_network_or_random_side_effects(self):
        script = '''
            import importlib.abc, sys, pydantic
            from unittest.mock import patch
            sys.path.insert(0, sys.argv[1])
            class BlockRuntime(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.startswith(('fastapi', 'sqlalchemy', 'psycopg', 'httpx', 'authlib', 'redis',
                                            'dotenv', 'pydantic_settings', 'app.core.config',
                                            'app.core.database', 'app.main', 'app.models', 'app.core.identity',
                                            'app.core.authorization')):
                        raise AssertionError('Forbidden dependency')
            sys.meta_path.insert(0, BlockRuntime())
            with patch('secrets.token_bytes', side_effect=AssertionError('Randomness at import')), \\
                 patch('socket.create_connection', side_effect=AssertionError('Network forbidden')), \\
                 patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')), \\
                 patch('builtins.open', side_effect=AssertionError('Implicit file access forbidden')):
                from app.core.oidc_transactions import OidcTransactionManager
                from app.core.oidc_config import OidcConfig
                from datetime import datetime, timezone
                class Store:
                    def insert_new(self, tx): raise AssertionError('Store at construction')
                    def consume(self, condition): raise AssertionError('Store at construction')
                OidcTransactionManager(config=OidcConfig(
                    issuer='https://identity.example.invalid', client_id='synthetic',
                    callback_url='https://app.example.invalid/callback', signature_algorithms=('RS256',),
                    deployment_mode='production', transaction_ttl_seconds=300, clock_skew_seconds=30,
                    max_id_token_age_seconds=600), store=Store(), clock=lambda: datetime.now(timezone.utc),
                    allowed_return_targets=('predictions',))
        '''
        result = subprocess.run([sys.executable, "-B", "-I", "-c", textwrap.dedent(script),
                                 str(ROOT / "backend")], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
