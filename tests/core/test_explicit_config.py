"""Explicit configuration only: synthetic credentials, no PostgreSQL or runtime."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch

from pydantic import SecretStr, ValidationError


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.application_config import ApplicationConfig
from app.core.config_loader import ConfigurationError, load_application_config


# Deliberately fake and local to these tests; never read from any real settings.
SECRET = "SYNTHETIC-CONFIG-PASSWORD-ONLY"
URL = f"postgresql+psycopg://test_role:{SECRET}@sql.example.invalid:6543/test_database"


class ExplicitConfigTests(unittest.TestCase):
    def test_valid_explicit_config_preserves_input_and_is_immutable(self):
        source = {"database_url": URL}
        config = load_application_config(source)
        self.assertIsInstance(config, ApplicationConfig)
        self.assertIsInstance(config.database_url, SecretStr)
        self.assertEqual(config.database_url.get_secret_value(), URL)
        self.assertEqual(source, {"database_url": URL})
        with self.assertRaises(TypeError) as caught:
            config.database_url = "another-sensitive-value"
        self.assertNotIn("another-sensitive-value", str(caught.exception))
        self.assertEqual(config.database_url.get_secret_value(), URL)

    def test_explicit_ipv4_ipv6_and_escaped_credentials(self):
        for value in (
            "postgresql+psycopg://user:fake@127.0.0.1:6543/database",
            "postgresql+psycopg://user:fake@[::1]:6543/database",
            "postgresql+psycopg://user:fake%40%3A%2F%25@sql.example.invalid:6543/database",
        ):
            with self.subTest(destination=value.split("@")[-1]):
                self.assertEqual(load_application_config({"database_url": value})
                                 .database_url.get_secret_value(), value)

    def test_absent_or_empty_destination_is_rejected_without_default(self):
        for source in ({}, {"database_url": None}, {"database_url": ""}):
            with self.subTest(source_kind=type(source.get("database_url")).__name__):
                with self.assertRaises(ConfigurationError):
                    load_application_config(source)

    def test_unknown_fields_are_rejected_even_with_valid_destination(self):
        with self.assertRaises(ConfigurationError):
            load_application_config({"database_url": URL, "unexpected": True})

    def test_incomplete_incoherent_or_ambiguous_urls_are_rejected(self):
        invalid = (
            "not-a-url", "sqlite:///:memory:", "postgresql://user:fake@host:6543/db",
            "postgresql+psycopg://user:fake@host/db",  # No implicit 5432.
            "postgresql+psycopg://user:fake@:6543/db",  # No implicit Unix socket.
            "postgresql+psycopg://host:6543/db",  # No implicit operating-system role.
            "postgresql+psycopg://user@host:6543/db",  # No implicit password source.
            "postgresql+psycopg://user:@host:6543/db",
            "postgresql+psycopg://user:fake@host:6543/",  # No default database.
            "postgresql+psycopg://user:fake@host:0/db",
            "postgresql+psycopg://user:fake@host:65536/db",
            "postgresql+psycopg://user:fake@host:not-a-port/db",
            "postgresql+psycopg://user:fake@bad..host:6543/db",
            "postgresql+psycopg://user:fake@host:6543/db?service=implicit",
            "postgresql+psycopg://user:fake@host:6543/db?host=alternate",
            "postgresql+psycopg://user:fake@host:6543/db?sslmode=disable",
            "postgresql+psycopg://user:fake@host:6543/db\n",
            "postgresql+psycopg://user:fake%00@host:6543/db",
            "postgresql+psycopg://user%0Aname:fake@host:6543/db",
        )
        for position, url in enumerate(invalid):
            with self.subTest(case=position):
                with self.assertRaises(ConfigurationError):
                    load_application_config({"database_url": url})

    def test_wrong_value_types_are_rejected(self):
        for value in (True, 5432, 1.5, [], {}, URL.encode("utf-8")):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(ConfigurationError):
                    load_application_config({"database_url": value})

    def test_loader_never_discovers_a_source_or_opens_a_supplied_path(self):
        with patch("builtins.open", side_effect=AssertionError("File access forbidden")), \
             patch("io.open", side_effect=AssertionError("File access forbidden")):
            for source in (None, URL, Path("private-settings.json"), lambda: {"database_url": URL}, []):
                with self.subTest(kind=type(source).__name__):
                    with self.assertRaises(ConfigurationError):
                        load_application_config(source)

    def test_environment_cannot_fill_override_or_repair_explicit_values(self):
        ambient = {"DATABASE_URL": URL, "PGHOST": "ambient.invalid", "PGPORT": "5432",
                   "PGDATABASE": "ambient", "PGUSER": "ambient", "PGPASSWORD": "AMBIENT-FAKE"}
        with patch.dict(os.environ, ambient, clear=True):
            with self.assertRaises(ConfigurationError):
                load_application_config({})
            with self.assertRaises(ConfigurationError):
                load_application_config({"database_url": "invalid"})
            other = URL.replace("sql.example.invalid", "explicit.example.invalid")
            self.assertEqual(load_application_config({"database_url": other})
                             .database_url.get_secret_value(), other)

    def test_representations_and_exports_do_not_disclose_destination_or_password(self):
        config = load_application_config({"database_url": URL})
        for rendered in (repr(config), str(config), repr(config.database_url), str(config.database_url),
                         repr(config.model_dump()), config.model_dump_json(),
                         repr(config.model_dump(mode="json"))):
            with self.subTest(representation=rendered):
                self.assertNotIn(SECRET, rendered)
                self.assertNotIn("sql.example.invalid", rendered)
                self.assertNotIn("test_role", rendered)
        self.assertEqual(config.model_dump(), {})

    def test_direct_model_errors_are_redacted_including_structured_errors(self):
        # Pydantic's hide_input_in_errors alone would still expose inputs in errors()/json().
        for source in ({"database_url": URL + "?service=bad"},
                       {"database_url": URL, SECRET: URL},
                       {"database_url": {"nested": SECRET}}, URL):
            with self.subTest(kind=type(source).__name__):
                with self.assertRaises(ValidationError) as caught:
                    ApplicationConfig.model_validate(source)
                error = caught.exception
                for rendered in (str(error), repr(error), repr(error.errors()), error.json()):
                    self.assertNotIn(SECRET, rendered)
                    self.assertNotIn(URL, rendered)
                    self.assertNotIn("test_role", rendered)
                self.assertIsNone(error.__cause__)
                self.assertIsNone(error.__context__)
                self.assertEqual(error.errors()[0]["input"], "[redacted]")

    def test_loader_errors_do_not_retain_sensitive_causes_or_context(self):
        for source in ({"database_url": URL + "?service=bad"}, {SECRET: URL}, URL):
            with self.assertRaises(ConfigurationError) as caught:
                load_application_config(source)
            error = caught.exception
            self.assertNotIn(SECRET, str(error))
            self.assertNotIn(SECRET, repr(error))
            self.assertIsNone(error.__cause__)
            self.assertIsNone(error.__context__)

    def test_import_and_validation_have_no_legacy_file_network_or_runtime_effects(self):
        script = r'''
            import builtins, importlib.abc, io, socket, sys
            from unittest.mock import patch
            import sqlalchemy, sqlalchemy.orm
            sys.path.insert(0, sys.argv[1])
            def forbidden(*args, **kwargs):
                raise AssertionError('Implicit configuration, runtime or I/O forbidden')
            class BlockLegacy(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname in ('app.core.config','app.core.database','app.main','pydantic_settings','dotenv'):
                        forbidden()
            sys.meta_path.insert(0, BlockLegacy())
            def guard_open(original):
                def checked(file, *args, **kwargs):
                    if isinstance(file, str) and (file.endswith('.env') or '.env.' in file):
                        forbidden()
                    return original(file, *args, **kwargs)
                return checked
            from contextlib import ExitStack
            with ExitStack() as guards:
                guards.enter_context(patch('builtins.open',guard_open(builtins.open)))
                guards.enter_context(patch('io.open',guard_open(io.open)))
                for name in ('sqlalchemy.create_engine','sqlalchemy.engine_from_config',
                             'sqlalchemy.orm.sessionmaker','sqlalchemy.orm.Session',
                             'sqlalchemy.engine.Engine.connect','socket.create_connection','socket.socket.connect'):
                    guards.enter_context(patch(name,side_effect=forbidden))
                from app.core.application_config import ApplicationConfig
                from app.core.config_loader import load_application_config
                # No file read of any kind is permitted during loading/validation.
                with patch('builtins.open',side_effect=forbidden), patch('io.open',side_effect=forbidden):
                    c = load_application_config({'database_url':sys.argv[2]})
                    assert isinstance(c, ApplicationConfig)
                assert 'app.core.config' not in sys.modules
                assert 'app.core.database' not in sys.modules
                assert 'pydantic_settings' not in sys.modules
        '''
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP")
               if key in os.environ}
        env.update(DATABASE_URL="invalid://ambient", PGHOST="ambient.invalid")
        result = subprocess.run(
            [sys.executable, "-B", "-I", "-c", textwrap.dedent(script), str(ROOT / "backend"), URL],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
