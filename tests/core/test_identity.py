"""Synthetic identity/provider tests only; no OIDC, SQL or network validation."""

from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.authorization import (
    AccountState, AuthorizationEffect, VerifiedIdentity, decide_authorization,
)
from app.core.identity import (
    AmbiguousIdentityLink, IdentityLinkNotFound, IdentityLookupUnavailable,
    InactiveLocalAccount, InvalidExternalIdentity, InvalidIdentityLink,
    InvalidIdentityLookup, LocalIdentityLink, LocalIdentityLookup,
    VerifiedExternalIdentity, resolve_local_identity,
)


ISSUER = "https://Identity.example.invalid/Realm"
SUBJECT = "SYNTHETIC-PRIVATE-Subject"


def external():
    return VerifiedExternalIdentity(ISSUER, SUBJECT)


def link():
    return LocalIdentityLink(ISSUER, SUBJECT, 17, AccountState.ACTIVE)


def provider(*links):
    result = Mock(spec=LocalIdentityLookup)
    result.find_by_external_identity.return_value = tuple(links)
    return result


class IdentityTests(unittest.TestCase):
    def test_known_identity_resolves_to_existing_verified_identity_contract(self):
        lookup = provider(link())
        result = resolve_local_identity(external(), lookup=lookup)
        self.assertIs(type(result), VerifiedIdentity)
        self.assertEqual(result, VerifiedIdentity(17, ISSUER, SUBJECT, AccountState.ACTIVE))
        lookup.find_by_external_identity.assert_called_once_with(issuer=ISSUER, subject=SUBJECT)
        self.assertEqual([call[0] for call in lookup.mock_calls], ["find_by_external_identity"])

    def test_exact_pair_and_case_are_preserved_without_normalization(self):
        for field, value in (("issuer", ISSUER.lower()), ("issuer", ISSUER + "/"),
                             ("subject", SUBJECT.lower()), ("subject", "other-subject")):
            with self.subTest(field=field, value=value):
                key = replace(external(), **{field: value})
                lookup = provider(link())
                with self.assertRaises(InvalidIdentityLink):
                    resolve_local_identity(key, lookup=lookup)
                lookup.find_by_external_identity.assert_called_once_with(issuer=key.issuer, subject=key.subject)

    def test_structural_contract_does_not_claim_oidc_url_or_subject_validation(self):
        key = VerifiedExternalIdentity("synthetic-issuer", "sujet-é")
        self.assertEqual((key.issuer, key.subject), ("synthetic-issuer", "sujet-é"))

    def test_same_subject_at_two_issuers_resolves_to_distinct_users(self):
        keys = (external(), replace(external(), issuer="https://other.example.invalid"))
        rows = (link(), LocalIdentityLink(keys[1].issuer, SUBJECT, 18, AccountState.ACTIVE))

        class SyntheticLookup:
            def find_by_external_identity(self, *, issuer, subject):
                return tuple(row for row in rows if (row.issuer, row.subject) == (issuer, subject))

        lookup = SyntheticLookup()
        first, second = (resolve_local_identity(key, lookup=lookup) for key in keys)
        self.assertEqual((first.user_id, second.user_id), (17, 18))
        self.assertEqual(resolve_local_identity(keys[0], lookup=lookup), first)

    def test_absent_or_untyped_identity_is_rejected_before_lookup(self):
        lookup = provider(link())
        for value in (None, True, 17, SUBJECT, {"issuer": ISSUER, "subject": SUBJECT}, object()):
            with self.subTest(kind=type(value).__name__), self.assertRaises(InvalidExternalIdentity):
                resolve_local_identity(value, lookup=lookup)
        lookup.find_by_external_identity.assert_not_called()

    def test_malformed_external_fields_are_rejected_without_echo(self):
        for field in ("issuer", "subject"):
            for value in (None, True, 17, "", " ", " value", "value ", "private\nvalue",
                          "private\x00value", "x" * 2049):
                with self.subTest(field=field, kind=type(value).__name__):
                    with self.assertRaises(InvalidExternalIdentity) as caught:
                        replace(external(), **{field: value})
                    self.assertEqual(str(caught.exception), "EXTERNAL_IDENTITY_INVALID")

    def test_bypassed_or_incomplete_external_objects_are_revalidated(self):
        lookup = provider(link())
        incomplete = object.__new__(VerifiedExternalIdentity)
        malformed = external()
        object.__setattr__(malformed, "subject", None)
        for value in (incomplete, malformed):
            with self.assertRaises(InvalidExternalIdentity):
                resolve_local_identity(value, lookup=lookup)
        lookup.find_by_external_identity.assert_not_called()

    def test_missing_link_is_refused_without_automatic_registration(self):
        lookup = provider()
        with self.assertRaises(IdentityLinkNotFound) as caught:
            resolve_local_identity(external(), lookup=lookup)
        self.assertEqual(str(caught.exception), "LOCAL_IDENTITY_NOT_FOUND")
        self.assertEqual([call[0] for call in lookup.mock_calls], ["find_by_external_identity"])

    def test_multiple_links_are_ambiguous_including_identical_duplicates(self):
        for rows in ((link(), link()), (link(), replace(link(), user_id=18))):
            with self.subTest(users=tuple(row.user_id for row in rows)), self.assertRaises(AmbiguousIdentityLink):
                resolve_local_identity(external(), lookup=provider(*rows))

    def test_incoherent_or_malformed_links_are_rejected(self):
        rows = [None, True, 17, {"user_id": 17}, object.__new__(LocalIdentityLink)]
        for field, values in {
            "issuer": (None, True, "other", " issuer "),
            "subject": (None, True, "other", " subject "),
            "user_id": (None, True, False, 0, -1, "17", 17.0),
            "account_state": (None, True, "active", "unknown"),
        }.items():
            rows.extend(replace(link(), **{field: value}) for value in values)
        for index, row in enumerate(rows):
            with self.subTest(case=index), self.assertRaises(InvalidIdentityLink):
                resolve_local_identity(external(), lookup=provider(row))

    def test_suspended_account_is_refused(self):
        with self.assertRaises(InactiveLocalAccount) as caught:
            resolve_local_identity(external(), lookup=provider(replace(link(), account_state=AccountState.SUSPENDED)))
        self.assertEqual(str(caught.exception), "LOCAL_ACCOUNT_INACTIVE")

    def test_email_or_name_cannot_be_used_for_linking(self):
        lookup = provider(replace(link(), subject="synthetic@example.invalid"))
        with self.assertRaises(InvalidIdentityLink):
            resolve_local_identity(external(), lookup=lookup)
        self.assertEqual([field.name for field in fields(VerifiedExternalIdentity)], ["issuer", "subject"])
        self.assertFalse(hasattr(lookup, "find_by_email"))
        self.assertFalse(hasattr(lookup, "find_by_name"))

    def test_invalid_lookup_configuration_is_distinct(self):
        for lookup in (None, True, {}, lambda **kwargs: (link(),)):
            with self.subTest(kind=type(lookup).__name__), self.assertRaises(InvalidIdentityLookup):
                resolve_local_identity(external(), lookup=lookup)

    def test_provider_failure_is_unavailability_not_missing_identity_and_never_retried(self):
        for failure in (RuntimeError(SUBJECT), TimeoutError(ISSUER), IdentityLinkNotFound()):
            lookup = provider()
            lookup.find_by_external_identity.side_effect = failure
            with self.subTest(kind=type(failure).__name__), self.assertRaises(IdentityLookupUnavailable) as caught:
                resolve_local_identity(external(), lookup=lookup)
            self.assertEqual(str(caught.exception), "LOCAL_IDENTITY_LOOKUP_UNAVAILABLE")
            self.assertIsNone(caught.exception.__cause__)
            self.assertIsNone(caught.exception.__context__)
            lookup.find_by_external_identity.assert_called_once_with(issuer=ISSUER, subject=SUBJECT)

    def test_provider_response_must_be_an_explicit_snapshot(self):
        for value in (None, True, link(), [link()], {"user_id": 17}, iter((link(),))):
            lookup = provider()
            lookup.find_by_external_identity.return_value = value
            with self.subTest(kind=type(value).__name__), self.assertRaises(InvalidIdentityLink):
                resolve_local_identity(external(), lookup=lookup)

    def test_resolution_grants_no_membership_or_permission(self):
        lookup = provider(link())
        resolved = resolve_local_identity(external(), lookup=lookup)
        self.assertEqual(set(resolved.__dataclass_fields__), {"user_id", "issuer", "subject", "account_state"})
        self.assertIs(decide_authorization(identity=resolved, company_id=7).effect, AuthorizationEffect.DENY)
        self.assertEqual([call[0] for call in lookup.mock_calls], ["find_by_external_identity"])

    def test_contracts_are_immutable_and_hide_external_identifiers_in_repr(self):
        for obj, field, value in ((external(), "subject", "other"), (link(), "user_id", 18)):
            with self.subTest(kind=type(obj).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(obj, field, value)
                with self.assertRaises(FrozenInstanceError):
                    delattr(obj, field)
                self.assertFalse(hasattr(obj, "__dict__"))
                self.assertNotIn(ISSUER, repr(obj))
                self.assertNotIn(SUBJECT, repr(obj))

    def test_all_public_errors_are_constant_without_sensitive_inputs(self):
        for error in (InvalidExternalIdentity, IdentityLinkNotFound, AmbiguousIdentityLink,
                      InvalidIdentityLink, InactiveLocalAccount, InvalidIdentityLookup,
                      IdentityLookupUnavailable):
            instance = error()
            self.assertEqual(len(instance.args), 1)
            for representation in (str(instance), repr(instance)):
                self.assertNotIn(ISSUER, representation)
                self.assertNotIn(SUBJECT, representation)
            with self.assertRaises(TypeError):
                error(SUBJECT)

    def test_fresh_import_and_resolution_have_no_historical_sql_or_network_effects(self):
        script = '''
            import importlib.abc, sys
            from unittest.mock import patch
            sys.path.insert(0, sys.argv[1])
            class BlockRuntime(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.startswith(('sqlalchemy', 'fastapi', 'psycopg', 'dotenv',
                                            'pydantic_settings', 'app.models', 'app.core.config',
                                            'app.core.database', 'app.main')):
                        raise AssertionError('Runtime import forbidden')
            sys.meta_path.insert(0, BlockRuntime())
            with patch('socket.create_connection', side_effect=AssertionError('Network forbidden')), \\
                 patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')), \\
                 patch('builtins.open', side_effect=AssertionError('Implicit file read forbidden')):
                from app.core.identity import VerifiedExternalIdentity, LocalIdentityLink, resolve_local_identity
                from app.core.authorization import AccountState
                class Lookup:
                    def find_by_external_identity(self, *, issuer, subject):
                        return (LocalIdentityLink(issuer, subject, 17, AccountState.ACTIVE),)
                result = resolve_local_identity(VerifiedExternalIdentity('issuer', 'subject'), lookup=Lookup())
                assert result.user_id == 17
        '''
        result = subprocess.run([sys.executable, "-B", "-I", "-c", textwrap.dedent(script),
                                 str(ROOT / "backend")], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
