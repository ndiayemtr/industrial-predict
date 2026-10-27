"""Synthetic, pure policy tests; no routes, database, tokens or authentication."""

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.authorization import (
    POLICY_VERSION, AccountState, AuthorizationDecision, AuthorizationEffect,
    CompanyMembership, MembershipState, Permission, Role, VerifiedIdentity,
    decide_authorization,
)


def identity():
    return VerifiedIdentity(17, "https://identity.example.invalid", "synthetic-subject", AccountState.ACTIVE)


def membership(company=7, permission=Permission.COMPANIES_READ, role=Role.READER):
    return CompanyMembership(17, company, MembershipState.ACTIVE, role, frozenset((permission,)))


class AuthorizationTests(unittest.TestCase):
    def decide(self, **changes):
        args = dict(identity=identity(), memberships=(membership(),), company_id=7,
                    permission=Permission.COMPANIES_READ)
        args.update(changes)
        return decide_authorization(**args)

    def assert_denied(self, **changes):
        result = self.decide(**changes)
        self.assertIs(result.effect, AuthorizationEffect.DENY)
        self.assertEqual(result.policy_version, POLICY_VERSION)
        return result

    def test_active_identity_and_explicit_permission_are_allowed(self):
        result = self.decide()
        self.assertEqual(result, AuthorizationDecision(AuthorizationEffect.ALLOW, 7, Permission.COMPANIES_READ))

    def test_absent_and_client_supplied_identity_are_denied(self):
        for value in (None, True, 17, "subject", {"user_id": 17}, object()):
            with self.subTest(kind=type(value).__name__):
                self.assert_denied(identity=value)

    def test_malformed_identity_fields_are_denied(self):
        for field, values in {
            "user_id": (True, 0, -1, "17", None),
            "issuer": (None, "", " issuer ", "issuer\nprivate", "x" * 2049),
            "subject": (False, "", " subject", "private\x00", "x" * 2049),
            "account_state": (True, None, "active"),
        }.items():
            for value in values:
                with self.subTest(field=field, kind=type(value).__name__):
                    self.assert_denied(identity=replace(identity(), **{field: value}))

    def test_suspended_account_is_denied_even_with_admin_permissions(self):
        self.assert_denied(identity=replace(identity(), account_state=AccountState.SUSPENDED),
                           memberships=(membership(role=Role.COMPANY_ADMIN),))

    def test_inactive_membership_is_denied(self):
        self.assert_denied(memberships=(replace(membership(), state=MembershipState.INACTIVE),))

    def test_missing_permission_and_role_alone_are_denied(self):
        self.assert_denied(memberships=(replace(membership(role=Role.COMPANY_ADMIN), permissions=frozenset()),))
        self.assert_denied(permission=Permission.PREDICTIONS_READ)
        self.assert_denied(memberships=())

    def test_foreign_company_and_foreign_user_are_denied(self):
        self.assert_denied(company_id=8)
        self.assert_denied(memberships=(replace(membership(), user_id=18),))

    def test_multiple_memberships_do_not_pool_permissions(self):
        members = (membership(), membership(8, Permission.PREDICTIONS_READ))
        self.assertIs(self.decide(memberships=members).effect, AuthorizationEffect.ALLOW)
        self.assertIs(self.decide(memberships=members, company_id=8,
                                 permission=Permission.PREDICTIONS_READ).effect, AuthorizationEffect.ALLOW)
        self.assert_denied(memberships=members, company_id=7, permission=Permission.PREDICTIONS_READ)
        self.assert_denied(memberships=members, company_id=8, permission=Permission.COMPANIES_READ)
        self.assert_denied(memberships=members, company_id=9)

    def test_decisions_are_isolated_and_order_independent(self):
        members = (membership(), membership(8, Permission.PREDICTIONS_READ))
        allowed = self.decide(memberships=members)
        denied = self.decide(memberships=members, company_id=8)
        self.assertNotEqual(allowed, denied)
        self.assertEqual(allowed, self.decide(memberships=tuple(reversed(members))))
        self.assertEqual(members, (membership(), membership(8, Permission.PREDICTIONS_READ)))
        self.assertIsNot(allowed, self.decide(memberships=members))

    def test_malformed_targets_and_unknown_permissions_are_denied(self):
        for value in (True, False, None, "7", 0, -1, [], {}):
            with self.subTest(target=type(value).__name__):
                self.assertIsNone(self.assert_denied(company_id=value).company_id)
        for value in (True, None, "companies:read", "future:permission", [], {}):
            with self.subTest(permission=type(value).__name__):
                self.assertIsNone(self.assert_denied(permission=value).permission)

    def test_malformed_membership_snapshot_is_denied(self):
        for value in (None, True, membership(), [membership()], {7: membership()}, (True,), (None,)):
            with self.subTest(kind=type(value).__name__):
                self.assert_denied(memberships=value)
        for field, values in {
            "user_id": (True, None, 0, "17"),
            "company_id": (True, None, 0, "7"),
            "state": (True, None, "active"),
            "role": (True, None, "reader"),
            "permissions": (None, True, {Permission.COMPANIES_READ}, (Permission.COMPANIES_READ,),
                            frozenset(("companies:read",)), frozenset((True,))),
        }.items():
            for value in values:
                with self.subTest(field=field, kind=type(value).__name__):
                    self.assert_denied(memberships=(replace(membership(), **{field: value}),))

    def test_duplicate_or_poisoned_snapshot_is_denied(self):
        self.assert_denied(memberships=(membership(), membership()))
        self.assert_denied(memberships=(membership(), replace(membership(), state=MembershipState.INACTIVE)))
        self.assert_denied(memberships=(membership(), replace(membership(8), user_id=18)))
        self.assert_denied(memberships=(membership(), object()))

    def test_role_caps_explicit_grants_without_implicit_escalation(self):
        self.assert_denied(memberships=(membership(permission=Permission.MEMBERSHIPS_MANAGE),),
                           permission=Permission.MEMBERSHIPS_MANAGE)
        self.assert_denied(memberships=(membership(permission=Permission.MEMBERSHIPS_MANAGE,
                                                   role=Role.TECHNICIAN),),
                           permission=Permission.MEMBERSHIPS_MANAGE)
        for role, permission in ((Role.TECHNICIAN, Permission.MAINTENANCE_WRITE),
                                 (Role.COMPANY_ADMIN, Permission.MEMBERSHIPS_MANAGE)):
            self.assertIs(self.decide(memberships=(membership(permission=permission, role=role),),
                                     permission=permission).effect, AuthorizationEffect.ALLOW)

    def test_default_is_explicit_denial(self):
        self.assertEqual(decide_authorization(), AuthorizationDecision(AuthorizationEffect.DENY, None, None))
        self.assertIs(decide_authorization(company_id=7).effect, AuthorizationEffect.DENY)

    def test_incompletely_constructed_objects_are_denied(self):
        self.assert_denied(identity=object.__new__(VerifiedIdentity))
        self.assert_denied(memberships=(object.__new__(CompanyMembership),))

    def test_contracts_and_permission_collections_are_immutable(self):
        for obj, field, value in ((identity(), "user_id", 18), (membership(), "company_id", 8),
                                  (self.decide(), "effect", AuthorizationEffect.DENY)):
            with self.subTest(kind=type(obj).__name__), self.assertRaises(FrozenInstanceError):
                setattr(obj, field, value)
            self.assertFalse(hasattr(obj, "__dict__"))
        with self.assertRaises(AttributeError):
            membership().permissions.add(Permission.MEMBERSHIPS_MANAGE)

    def test_decisions_and_representations_do_not_expose_identity_inputs(self):
        private = replace(identity(), subject="SYNTHETIC-PRIVATE-SUBJECT")
        result = self.decide(identity=replace(private, account_state=AccountState.SUSPENDED))
        self.assertEqual(set(result.__dataclass_fields__), {"effect", "company_id", "permission", "policy_version"})
        for obj in (private, membership(), result):
            self.assertNotIn(private.subject, repr(obj))
            self.assertNotIn(private.issuer, repr(obj))

    def test_module_has_only_standard_library_dependencies_and_no_io(self):
        path = ROOT / "backend/app/core/authorization.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertEqual(imports, ["dataclasses", "enum"])
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))
        script = '''
            import importlib.abc, sys
            from unittest.mock import patch
            sys.path.insert(0, sys.argv[1])
            class BlockRuntime(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.startswith(('sqlalchemy', 'fastapi', 'psycopg', 'dotenv',
                                            'pydantic_settings', 'app.core.config',
                                            'app.core.database', 'app.main')):
                        raise AssertionError('Runtime import forbidden')
            sys.meta_path.insert(0, BlockRuntime())
            with patch('socket.create_connection', side_effect=AssertionError('Network forbidden')), \\
                 patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')):
                from app.core.authorization import decide_authorization, AuthorizationEffect
                assert decide_authorization().effect is AuthorizationEffect.DENY
        '''
        result = subprocess.run([sys.executable, "-B", "-I", "-c", textwrap.dedent(script),
                                 str(ROOT / "backend")], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
