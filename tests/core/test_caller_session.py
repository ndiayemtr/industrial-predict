"""Synthetic pure-contract tests; no real credentials, storage or OIDC calls."""

import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.authorization import (
    POLICY_VERSION, AccountState, AuthorizationEffect, CompanyMembership,
    MembershipState, Permission, Role, VerifiedIdentity, decide_authorization,
)
from app.core.identity import LocalIdentityLink, LocalIdentityLookup, VerifiedExternalIdentity
from app.core.caller_session import (
    AdmissionDecision, CallerForbidden, CallerProviderUnavailable, CallerStateIncoherent,
    CallerUnauthenticated, CurrentCaller, CurrentCallerProvider, IdentityAssurance,
    IdentityEvidence, Outcome, Reason, SessionContractError, SessionPolicy,
    SessionRecord, SessionReference, TrustedIdentityProvider, admit_caller,
    evaluate_session, record_activity, revoke_session, rotate_session,
)


NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
MICROSECOND = timedelta(microseconds=1)
EXTERNAL = VerifiedExternalIdentity("https://identity.example.invalid", "synthetic-subject")
IDENTITY = VerifiedIdentity(17, EXTERNAL.issuer, EXTERNAL.subject, AccountState.ACTIVE)
REFERENCE = SessionReference("a" * 64)
OTHER = SessionReference("b" * 64)


def session(**changes):
    record = SessionRecord(REFERENCE, IDENTITY, NOW, NOW, NOW, NOW + timedelta(hours=8))
    return replace(record, **changes)


def member(company=7, permission=Permission.PREDICTIONS_READ, role=Role.READER):
    return CompanyMembership(17, company, MembershipState.ACTIVE, role, frozenset((permission,)))


def caller(**changes):
    values = dict(session_reference=REFERENCE, identity=IDENTITY,
                  memberships=(member(),), refreshed_at=NOW)
    values.update(changes)
    return CurrentCaller(**values)


def evidence_provider(value=IdentityEvidence(EXTERNAL, IdentityAssurance.PROFESSIONAL_VERIFIED)):
    provider = Mock(spec=TrustedIdentityProvider)
    provider.verified_identity.return_value = value
    return provider


def lookup(*links):
    provider = Mock(spec=LocalIdentityLookup)
    provider.find_by_external_identity.return_value = tuple(links)
    return provider


def link(**changes):
    return replace(LocalIdentityLink(EXTERNAL.issuer, EXTERNAL.subject, 17, AccountState.ACTIVE), **changes)


class SessionTests(unittest.TestCase):
    def evaluate(self, record=None, now=NOW, reference=REFERENCE):
        return evaluate_session(session() if record is None else record, reference=reference, now=now)

    def test_defaults_and_valid_session_are_deterministic(self):
        self.assertEqual(SessionPolicy(), SessionPolicy(timedelta(minutes=30), timedelta(hours=8)))
        result = self.evaluate()
        self.assertEqual((result.outcome, result.reason), (Outcome.READY, Reason.VALID))
        self.assertEqual(result, self.evaluate())

    def test_idle_expiration_is_exclusive(self):
        boundary = NOW + timedelta(minutes=30)
        self.assertIs(self.evaluate(now=boundary - MICROSECOND).outcome, Outcome.READY)
        for now in (boundary, boundary + MICROSECOND):
            with self.subTest(now=now):
                self.assertIs(self.evaluate(now=now).reason, Reason.IDLE_EXPIRED)

    def test_absolute_expiration_is_exclusive_even_after_activity(self):
        end = NOW + timedelta(hours=8)
        record = session(last_activity_at=end - timedelta(minutes=1))
        self.assertIs(self.evaluate(record, now=end - MICROSECOND).outcome, Outcome.READY)
        for now in (end, end + MICROSECOND):
            self.assertIs(self.evaluate(record, now=now).reason, Reason.ABSOLUTE_EXPIRED)

    def test_activity_never_extends_absolute_lifetime_or_revives_expired_session(self):
        original = session()
        updated = record_activity(original, now=NOW + timedelta(minutes=29))
        self.assertEqual(updated.absolute_expires_at, original.absolute_expires_at)
        self.assertEqual(original.last_activity_at, NOW)
        self.assertIs(self.evaluate(updated, now=NOW + timedelta(minutes=58)).outcome, Outcome.READY)
        with self.assertRaises(SessionContractError):
            record_activity(original, now=NOW + timedelta(minutes=30))

    def test_revocation_transition_refuses_all_future_use(self):
        original = session()
        revoked = revoke_session(original, now=NOW + timedelta(minutes=1))
        self.assertIsNone(original.revoked_at)
        self.assertEqual(revoked.revoked_at, NOW + timedelta(minutes=1))
        self.assertIs(self.evaluate(revoked, now=revoked.revoked_at).reason, Reason.REVOKED)
        with self.assertRaises(SessionContractError):
            record_activity(revoked, now=revoked.revoked_at)

    def test_rotation_invalidates_old_reference_without_extending_lifetime(self):
        original = session()
        now = NOW + timedelta(minutes=1)
        plan = rotate_session(original, replacement=OTHER, now=now)
        self.assertIs(self.evaluate(plan.invalidated, now=now).reason, Reason.ROTATED)
        self.assertIs(self.evaluate(plan.replacement, reference=OTHER, now=now).outcome, Outcome.READY)
        self.assertIs(self.evaluate(plan.replacement, reference=REFERENCE, now=now).reason, Reason.SESSION_MISMATCH)
        self.assertEqual(plan.replacement.authenticated_at, original.authenticated_at)
        self.assertEqual(plan.replacement.absolute_expires_at, original.absolute_expires_at)
        # A plan does not mutate a stored record: atomic invalidation remains an adapter duty.
        self.assertIs(self.evaluate(original, now=now).outcome, Outcome.READY)
        for reference in (REFERENCE, None, "b" * 64):
            with self.assertRaises(SessionContractError):
                rotate_session(original, replacement=reference, now=now)

    def test_utc_required_and_future_activity_rejected(self):
        for now in (NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=1))),
                    NOW - MICROSECOND, None, True, "2026-01-01"):
            with self.subTest(now=now):
                self.assertIs(self.evaluate(now=now).outcome, Outcome.INCOHERENT)
        self.assertIs(self.evaluate(now=NOW.astimezone(timezone(timedelta(0)))).outcome, Outcome.READY)

    def test_invalid_policy_and_reference_rejected(self):
        for idle, absolute in ((0, timedelta(hours=8)), (timedelta(0), timedelta(hours=8)),
                               (timedelta(hours=9), timedelta(hours=8))):
            with self.assertRaises(SessionContractError):
                SessionPolicy(idle, absolute)
        for value in (None, True, "", "a" * 63, "A" * 64, "g" * 64):
            with self.assertRaises(SessionContractError):
                SessionReference(value)

    def test_record_time_and_rotation_invariants(self):
        for changes in ({"authenticated_at": NOW + MICROSECOND},
                        {"created_at": NOW + MICROSECOND},
                        {"last_activity_at": NOW + timedelta(hours=8)},
                        {"absolute_expires_at": NOW + timedelta(hours=9)},
                        {"revoked_at": NOW - MICROSECOND}, {"replaced_by": OTHER},
                        {"revoked_at": NOW, "replaced_by": REFERENCE},
                        {"created_at": NOW.replace(tzinfo=None)}):
            with self.subTest(changes=changes), self.assertRaises(SessionContractError):
                session(**changes)

    def test_suspended_account_is_forbidden_not_unauthenticated(self):
        result = self.evaluate(session(identity=replace(IDENTITY, account_state=AccountState.SUSPENDED)))
        self.assertEqual((result.outcome, result.reason), (Outcome.FORBIDDEN, Reason.ACCOUNT_INACTIVE))

    def test_bypassed_or_malformed_records_fail_closed(self):
        for record in (object.__new__(SessionRecord), {}, True):
            self.assertIs(evaluate_session(record, reference=REFERENCE, now=NOW).outcome, Outcome.INCOHERENT)
        damaged = session()
        object.__setattr__(damaged, "identity", object.__new__(VerifiedIdentity))
        self.assertIs(self.evaluate(damaged).outcome, Outcome.INCOHERENT)
        damaged = session()
        object.__setattr__(damaged, "policy", object.__new__(SessionPolicy))
        self.assertIs(self.evaluate(damaged).outcome, Outcome.INCOHERENT)

    def test_reference_mismatch_and_future_revocation_fail_closed(self):
        self.assertIs(self.evaluate(reference=OTHER).reason, Reason.SESSION_MISMATCH)
        future = session(revoked_at=NOW + MICROSECOND)
        self.assertIs(self.evaluate(future).outcome, Outcome.INCOHERENT)


class AdmissionTests(unittest.TestCase):
    def test_active_link_admitted_without_permission_or_provisioning(self):
        provider, local = evidence_provider(), lookup(link())
        result = admit_caller(provider=provider, lookup=local)
        self.assertEqual(result, AdmissionDecision(Outcome.READY, Reason.VALID, IDENTITY))
        provider.verified_identity.assert_called_once_with()
        local.find_by_external_identity.assert_called_once_with(issuer=EXTERNAL.issuer, subject=EXTERNAL.subject)
        self.assertEqual(len(local.mock_calls), 1)
        self.assertIs(decide_authorization(identity=result.identity, company_id=7,
                                           permission=Permission.PREDICTIONS_ANALYZE).effect,
                      AuthorizationEffect.DENY)

    def test_unknown_ambiguous_and_suspended_are_distinct(self):
        for links, expected in (((), (Outcome.FORBIDDEN, Reason.UNKNOWN_IDENTITY)),
                                ((link(), link()), (Outcome.INCOHERENT, Reason.AMBIGUOUS_IDENTITY)),
                                ((link(account_state=AccountState.SUSPENDED),),
                                 (Outcome.FORBIDDEN, Reason.ACCOUNT_INACTIVE))):
            with self.subTest(expected=expected):
                result = admit_caller(provider=evidence_provider(), lookup=lookup(*links))
                self.assertEqual((result.outcome, result.reason), expected)
                self.assertIsNone(result.identity)

    def test_pending_assurance_and_absence_never_reach_local_lookup(self):
        for value, expected in ((None, Outcome.UNAUTHENTICATED),
                               (IdentityEvidence(EXTERNAL, IdentityAssurance.INDEPENDENT_VERIFICATION_REQUIRED),
                                Outcome.FORBIDDEN)):
            local = lookup(link())
            self.assertIs(admit_caller(provider=evidence_provider(value), lookup=local).outcome, expected)
            local.find_by_external_identity.assert_not_called()

    def test_email_domain_and_declared_verified_flag_cannot_admit(self):
        for value in (True, EXTERNAL, IDENTITY, {"verified": True, "email": "admin@company.invalid"},
                      IdentityEvidence(EXTERNAL, True), object.__new__(IdentityEvidence)):
            local = lookup(link())
            self.assertIs(admit_caller(provider=evidence_provider(value), lookup=local).outcome, Outcome.INCOHERENT)
            local.find_by_external_identity.assert_not_called()
        result = admit_caller(provider=evidence_provider(), lookup=lookup(link(subject="admin@company.invalid")))
        self.assertIs(result.outcome, Outcome.INCOHERENT)

    def test_technical_failures_are_not_denials_and_are_not_retried(self):
        provider = evidence_provider()
        provider.verified_identity.side_effect = TimeoutError("private")
        local = lookup(link())
        result = admit_caller(provider=provider, lookup=local)
        self.assertIs(result.outcome, Outcome.UNAVAILABLE)
        self.assertNotIn("private", repr(result))
        provider.verified_identity.assert_called_once()
        local.find_by_external_identity.assert_not_called()
        local.find_by_external_identity.side_effect = RuntimeError("private")
        self.assertIs(admit_caller(provider=evidence_provider(), lookup=local).outcome, Outcome.UNAVAILABLE)
        local.find_by_external_identity.assert_called_once()

    def test_invalid_provider_lookup_and_external_state_fail_closed(self):
        for provider, local in ((None, lookup(link())), (evidence_provider(), None),
                                (evidence_provider(IdentityEvidence({}, IdentityAssurance.PROFESSIONAL_VERIFIED)),
                                 lookup(link()))):
            self.assertIs(admit_caller(provider=provider, lookup=local).outcome, Outcome.INCOHERENT)
        local = lookup(link())
        local.find_by_external_identity.return_value = [link()]
        self.assertIs(admit_caller(provider=evidence_provider(), lookup=local).outcome, Outcome.INCOHERENT)

    def test_admission_is_deterministic_and_decisions_require_explicit_inspection(self):
        self.assertEqual(admit_caller(provider=evidence_provider(), lookup=lookup(link())),
                         admit_caller(provider=evidence_provider(), lookup=lookup(link())))
        for decision in (admit_caller(provider=evidence_provider(None), lookup=lookup()),
                         evaluate_session(session(), reference=REFERENCE, now=NOW)):
            with self.assertRaises(TypeError):
                bool(decision)


class CurrentCallerTests(unittest.TestCase):
    def test_snapshot_reuses_existing_contracts_and_policy(self):
        result = caller()
        self.assertIs(result.identity, IDENTITY)
        self.assertEqual(result.policy_version, POLICY_VERSION)
        self.assertEqual(result.refreshed_at, NOW)
        self.assertTrue(callable(Mock(spec=CurrentCallerProvider).current_caller))

    def test_company_isolation_and_no_implicit_analysis(self):
        snapshot = caller(memberships=(member(role=Role.COMPANY_ADMIN), member(company=8)))
        for company, permission, expected in (
                (7, Permission.PREDICTIONS_READ, AuthorizationEffect.ALLOW),
                (8, Permission.PREDICTIONS_READ, AuthorizationEffect.ALLOW),
                (9, Permission.PREDICTIONS_READ, AuthorizationEffect.DENY),
                (7, Permission.PREDICTIONS_ANALYZE, AuthorizationEffect.DENY)):
            self.assertIs(decide_authorization(identity=snapshot.identity, memberships=snapshot.memberships,
                                               company_id=company, permission=permission).effect, expected)
        analysis = member(company=8, permission=Permission.PREDICTIONS_ANALYZE, role=Role.COMPANY_ADMIN)
        snapshot = caller(memberships=(member(), analysis))
        self.assertIs(decide_authorization(identity=snapshot.identity, memberships=snapshot.memberships,
                                           company_id=7, permission=Permission.PREDICTIONS_ANALYZE).effect,
                      AuthorizationEffect.DENY)
        self.assertIs(decide_authorization(identity=snapshot.identity, memberships=snapshot.memberships,
                                           company_id=8, permission=Permission.PREDICTIONS_ANALYZE).effect,
                      AuthorizationEffect.ALLOW)

    def test_inactive_membership_has_no_grants(self):
        inactive = replace(member(), state=MembershipState.INACTIVE, permissions=frozenset())
        self.assertEqual(caller(memberships=(inactive,)).memberships, (inactive,))
        with self.assertRaises(SessionContractError):
            caller(memberships=(replace(member(), state=MembershipState.INACTIVE),))

    def test_invalid_snapshot_rejected(self):
        for members in ([member()], (member(), member()), (object.__new__(CompanyMembership),),
                        (replace(member(), user_id=18),),
                        (replace(member(), company_id=True),), (replace(member(), role="reader"),),
                        (replace(member(), permissions=frozenset(("predictions:read",))),),
                        (member(permission=Permission.PREDICTIONS_ANALYZE),)):
            with self.subTest(members=members), self.assertRaises(SessionContractError):
                caller(memberships=members)
        for changes in ({"identity": replace(IDENTITY, account_state=AccountState.SUSPENDED)},
                        {"identity": object.__new__(VerifiedIdentity)},
                        {"refreshed_at": NOW.replace(tzinfo=None)}, {"policy_version": "unknown"}):
            with self.assertRaises(SessionContractError):
                caller(**changes)

    def test_no_permissions_in_session_and_immutable_opaque_objects(self):
        self.assertNotIn("memberships", {f.name for f in fields(SessionRecord)})
        self.assertNotIn("permissions", {f.name for f in fields(SessionRecord)})
        for value in (session(), REFERENCE, caller(), evidence_provider().verified_identity(),
                      rotate_session(session(), replacement=OTHER, now=NOW)):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
            self.assertFalse(hasattr(value, "__dict__"))
            for sensitive in (EXTERNAL.subject, EXTERNAL.issuer, REFERENCE.digest):
                self.assertNotIn(sensitive, repr(value))

    def test_error_categories_are_constant_and_distinct(self):
        errors = (CallerUnauthenticated, CallerForbidden, CallerStateIncoherent, CallerProviderUnavailable)
        self.assertEqual(len({str(error()) for error in errors}), 4)
        for error in errors:
            with self.assertRaises(TypeError):
                error("private")

    def test_module_has_only_pure_dependencies_and_no_runtime_side_effects(self):
        source = ROOT / "backend/app/core/caller_session.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {"dataclasses", "datetime", "enum", "typing",
                                   "app.core.identity", "app.core.authorization"})
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))
        script = '''
            import importlib.abc, sys
            from unittest.mock import patch
            sys.path.insert(0, sys.argv[1])
            class BlockRuntime(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.startswith(('sqlalchemy', 'fastapi', 'psycopg', 'httpx',
                                            'app.models', 'app.core.config', 'app.core.oidc',
                                            'app.core.database', 'app.main')):
                        raise AssertionError('Runtime import forbidden')
            sys.meta_path.insert(0, BlockRuntime())
            with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')), \\
                 patch('builtins.open', side_effect=AssertionError('File read forbidden')):
                from app.core.caller_session import SessionPolicy
                assert SessionPolicy().idle_timeout.total_seconds() == 1800
        '''
        result = subprocess.run([sys.executable, "-B", "-I", "-c", textwrap.dedent(script),
                                 str(ROOT / "backend")], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
