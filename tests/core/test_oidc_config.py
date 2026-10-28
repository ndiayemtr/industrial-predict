"""Synthetic configuration only; no provider, token, secret, SQL or network."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch

from pydantic import BaseModel, ValidationError


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.oidc_config import OidcConfig


def source(**changes):
    data = dict(issuer="https://Identity.example.invalid/Realm/", client_id="Synthetic-Client",
                callback_url="https://app.example.invalid/api/v1/auth/callback",
                signature_algorithms=("RS256", "ES256"), deployment_mode="production",
                transaction_ttl_seconds=300, clock_skew_seconds=30, max_id_token_age_seconds=600)
    data.update(changes)
    return data


class OidcConfigTests(unittest.TestCase):
    def reject(self, data):
        with self.assertRaises(ValidationError) as caught:
            OidcConfig.model_validate(data)
        self.assertIsNone(caught.exception.__context__)
        return caught.exception

    def test_valid_explicit_configuration_preserves_exact_identifiers(self):
        data = source()
        config = OidcConfig(**data)
        self.assertIsInstance(config, BaseModel)
        for field, value in data.items():
            self.assertEqual(getattr(config, field), value)
        self.assertFalse(config.allow_http_loopback_callback)
        self.assertEqual(data, source())

    def test_absent_incomplete_and_wrong_source_types_are_rejected(self):
        for data in (None, {}, True, "config.json", []):
            self.reject(data)
        for field in source():
            data = source()
            del data[field]
            with self.subTest(field=field):
                self.reject(data)

    def test_issuer_always_requires_https_even_in_development(self):
        for issuer in ("http://identity.example.invalid", "http://localhost:9000/realm"):
            self.reject(source(issuer=issuer, deployment_mode="development", allow_http_loopback_callback=True))

    def test_ambiguous_or_malformed_urls_are_rejected_in_both_fields(self):
        urls = ("", "not-a-url", "//identity.example.invalid", "https:///realm", "https://",
                "https://user:private@identity.example.invalid/realm", "https://host.invalid?",
                "https://host.invalid?issuer=other", "https://host.invalid#", "https://host.invalid#fragment",
                "https://host.invalid\\other", "https://host.invalid/%2e%2e/other", "https://host.invalid/%ZZ",
                "https://host.invalid/../other", "https://host.invalid/./other", "https://host.invalid//other",
                "https://host.invalid/path;param", "https://host.invalid\n", " https://host.invalid",
                "https://host.invalid/path with spaces", "https://bad..invalid", "https://host.invalid.",
                "https://host.invalid:", "https://host.invalid:0", "https://host.invalid:65536",
                "https://host.invalid:0443", "https://host.invalid:+443", "https://host.invalid:text",
                "https://[::1", "https://[v1.foo]/", "https://256.1.1.1/path", "https://127.1/path", "HTTPS://host.invalid",
                "https://höst.invalid", "https://host.invalid/" + "x" * 2049)
        for field in ("issuer", "callback_url"):
            for index, value in enumerate(urls):
                with self.subTest(field=field, case=index):
                    self.reject(source(**{field: value}))

    def test_https_urls_with_explicit_ports_ipv6_and_case_are_preserved(self):
        for url in ("https://Identity.example.invalid:8443/Realm/", "https://[2001:db8::1]:8443/callback"):
            config = OidcConfig(**source(issuer=url, callback_url=url))
            self.assertEqual((config.issuer, config.callback_url), (url, url))

    def test_production_never_allows_http_or_development_opt_in(self):
        self.reject(source(callback_url="http://127.0.0.1:4200/callback"))
        self.reject(source(allow_http_loopback_callback=True))

    def test_development_http_requires_separate_explicit_opt_in(self):
        self.reject(source(deployment_mode="development", callback_url="http://127.0.0.1:4200/callback"))
        for host in ("localhost", "127.0.0.1", "[::1]"):
            callback = f"http://{host}:4200/api/v1/auth/callback"
            config = OidcConfig(**source(deployment_mode="development", allow_http_loopback_callback=True,
                                         callback_url=callback))
            self.assertEqual(config.callback_url, callback)

    def test_loopback_opt_in_cannot_allow_remote_or_ambiguous_hosts(self):
        for host in ("localhost.attacker.invalid", "127.0.0.1.attacker.invalid", "0.0.0.0",
                     "192.168.1.10", "127.1", "2130706433", "[::ffff:127.0.0.1]", "127.0.0.2"):
            self.reject(source(deployment_mode="development", allow_http_loopback_callback=True,
                               callback_url=f"http://{host}:4200/callback"))
        self.reject(source(deployment_mode="development", allow_http_loopback_callback=True,
                           callback_url="http://localhost/callback"))

    def test_callback_is_one_exact_server_configured_value_not_a_wildcard(self):
        for value in ("https://*.example.invalid/callback", "https://app.example.invalid/callback*",
                      "https://app.example.invalid/callback?next=https://other.invalid"):
            self.reject(source(callback_url=value))
        self.reject(source(callback_url="https://app.example.invalid/callback", request_host="other.invalid"))

    def test_client_id_is_required_strict_and_not_normalized(self):
        for value in (None, True, 17, "", " ", " client", "client ", "private\nvalue", "x" * 513):
            self.reject(source(client_id=value))

    def test_only_explicit_nonempty_unique_algorithm_allowlist_is_accepted(self):
        for values in ((), ("none",), ("None",), ("HS256",), ("RS512",), ("unexpected",),
                       ("rs256",), ("RS256", "RS256"), ("RS256", "none"), (True,),
                       ["RS256"], "RS256", None):
            self.reject(source(signature_algorithms=values))
        self.assertEqual(OidcConfig(**source(signature_algorithms=("PS256",))).signature_algorithms, ("PS256",))

    def test_time_bounds_and_strict_integer_types(self):
        for field, low, high in (("transaction_ttl_seconds", 60, 600), ("clock_skew_seconds", 0, 120),
                                  ("max_id_token_age_seconds", 60, 3600)):
            for value in (low - 1, high + 1, True, str(low), 1.5, None):
                with self.subTest(field=field, value=value):
                    self.reject(source(**{field: value}))
            for value in (low, high):
                config = OidcConfig(**source(**{field: value}))
                self.assertEqual(getattr(config, field), value)

    def test_incoherent_timings_are_refused(self):
        self.reject(source(transaction_ttl_seconds=60, clock_skew_seconds=60))
        self.reject(source(max_id_token_age_seconds=60, clock_skew_seconds=60))

    def test_unknown_fields_and_invalid_https_policy_are_refused(self):
        self.reject(source(client_secret="SYNTHETIC-REJECTED-INPUT"))
        self.reject(source(disable_tls_verification=True))
        for value in (None, True, "test", "Production"):
            self.reject(source(deployment_mode=value))
        for value in (1, "true", None):
            self.reject(source(allow_http_loopback_callback=value))

    def test_model_is_immutable_without_sensitive_assignment_errors(self):
        config = OidcConfig(**source())
        with self.assertRaises(TypeError) as caught:
            config.client_id = "SYNTHETIC-PRIVATE-ASSIGNMENT"
        self.assertNotIn("SYNTHETIC-PRIVATE-ASSIGNMENT", str(caught.exception))
        with self.assertRaises(TypeError):
            del config.issuer
        with self.assertRaises(TypeError):
            config.signature_algorithms[0] = "none"
        self.assertEqual(config.client_id, source()["client_id"])

    def test_errors_and_repr_do_not_expose_supplied_values_or_unknown_keys(self):
        marker = "SYNTHETIC-PRIVATE-INPUT"
        for data in (source(client_id=marker + "\n"), source(**{marker: marker}),
                     source(issuer=f"https://user:{marker}@host.invalid")):
            error = self.reject(data)
            for view in (str(error), repr(error), str(error.errors()), error.json()):
                self.assertNotIn(marker, view)
            self.assertIsNone(error.__cause__)
        config = OidcConfig(**source())
        for field in ("issuer", "client_id", "callback_url"):
            self.assertNotIn(source()[field], repr(config))

    def test_environment_neither_supplies_nor_overrides_configuration(self):
        with patch.dict(os.environ, {"OIDC_ISSUER": "https://ambient.invalid", "OIDC_CLIENT_ID": "ambient",
                                     "DATABASE_URL": "invalid://ambient"}, clear=True):
            self.reject({})
            self.assertEqual(OidcConfig(**source()).issuer, source()["issuer"])

    def test_validation_does_not_read_files_environment_or_open_connections(self):
        with patch("builtins.open", side_effect=AssertionError("File access forbidden")), \
             patch("io.open", side_effect=AssertionError("File access forbidden")), \
             patch("os.getenv", side_effect=AssertionError("Environment access forbidden")), \
             patch.object(os._Environ, "__getitem__", side_effect=AssertionError("Environment access forbidden")), \
             patch("socket.create_connection", side_effect=AssertionError("Network forbidden")), \
             patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
            OidcConfig(**source())
            self.reject({})

    def test_fresh_import_has_no_historical_runtime_or_client_dependencies(self):
        script = '''
            import importlib.abc, sys, pydantic
            from unittest.mock import patch
            sys.path.insert(0, sys.argv[1])
            class BlockRuntime(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.startswith(('sqlalchemy', 'fastapi', 'psycopg', 'dotenv', 'pydantic_settings',
                                            'httpx', 'authlib', 'app.models', 'app.core.config',
                                            'app.core.database', 'app.main')):
                        raise AssertionError('Runtime/client import forbidden')
            sys.meta_path.insert(0, BlockRuntime())
            with patch('socket.create_connection', side_effect=AssertionError('Network forbidden')), \\
                 patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')), \\
                 patch('builtins.open', side_effect=AssertionError('Implicit file access forbidden')):
                from app.core.oidc_config import OidcConfig
                assert OidcConfig.model_config['frozen'] is True
        '''
        result = subprocess.run([sys.executable, "-B", "-I", "-c", textwrap.dedent(script),
                                 str(ROOT / "backend")], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
