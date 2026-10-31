"""Static checks and doubles only. Never launch guardian, shell or Docker."""

import ast
import builtins
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import re
import shlex
import socket
import subprocess
import threading
import traceback
from unittest.mock import Mock

import pytest

from oidc_postgres_bootstrap.guardian import validation as g


ROOT = Path(__file__).parent
MARKER = "SYNTHETIC_SENSITIVE_GUARDIAN_MARKER"


@pytest.fixture(autouse=True)
def no_operational_effect(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("operational call")
        raise AssertionError("Only static checks and doubles are permitted")

    for target, name in ((subprocess, "run"), (subprocess, "Popen"), (socket, "create_connection"),
                         (socket, "getaddrinfo"), (socket.socket, "connect"),
                         (threading.Thread, "start"), (builtins, "input")):
        monkeypatch.setattr(target, name, forbidden)
    yield
    assert attempts == []


def data():
    return {
        "guardian_bytes": (ROOT / "guardian.sh").read_bytes(),
        "recipe_bytes": (ROOT / "Dockerfile.in").read_bytes(),
        "ignore_bytes": (ROOT / ".dockerignore").read_bytes(),
        "manifest_bytes": (ROOT / "artifact_manifest.json").read_bytes(),
        "bootstrap_bytes": (ROOT.parent / "bootstrap.sh").read_bytes(),
    }


def rejected(callback):
    with pytest.raises(g.GuardianPreparationRejected) as caught:
        callback()
    error = caught.value
    assert str(error) == "OIDC idle guardian preparation rejected"
    assert error.__context__ is None and error.__cause__ is None and error.__suppress_context__ is True
    assert MARKER not in str(error) + repr(error) + "".join(traceback.format_exception(error))


def encode_manifest(manifest):
    return (json.dumps(manifest, indent=2) + "\n").encode("ascii")


def test_nominal_supplied_bytes_and_reader_double_provide_no_authority():
    supplied = data()
    reader = Mock(side_effect=lambda key: supplied[key])
    result = g.validate_preparation(**{key: reader(key) for key in supplied})
    assert reader.call_count == 5
    assert result.execution_authorized is result.build_authorized is result.authenticated is False
    assert repr(result) == "<PreparationValidation: offline-only>"
    rejected(lambda: bool(result))
    with pytest.raises(FrozenInstanceError):
        result.guardian_sha256 = "f" * 64


def test_guardian_has_only_idle_external_command_and_no_activation_input():
    source = data()["guardian_bytes"].decode("ascii")
    lexer = shlex.shlex(source, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    tokens = list(lexer)
    assert not set(tokens) & {"postgres", "initdb", "pg_ctl", "psql", "docker", "curl", "wget", "nc",
                              "exec", "eval", "source", ".", "read", "env", "printenv", "openssl"}
    external = [line.strip() for line in source.splitlines() if line.lstrip().startswith("/")]
    assert external == ["/usr/bin/sleep infinity &"]
    assert source.index('if [ "$#" -ne 0 ]; then') < source.index("/usr/bin/sleep")
    assert "exit 78" in source and "exit 70" in source
    assert "bootstrap.sh" not in source
    assert not any(value in source for value in ("--activate", "ALLOW_BOOTSTRAP", "POSTGRES_PASSWORD", "PGPASSWORD", "$@", "$*"))


def test_signal_wiring_and_child_wait_are_static_only():
    source = data()["guardian_bytes"].decode("ascii")
    assert "trap stop_guardian TERM INT" in source
    assert "trap '' HUP QUIT USR1 USR2" in source
    assert "trap '' TERM INT" in source
    assert 'kill -TERM "$idle_pid" 2>/dev/null || :' in source
    assert 'wait "$idle_pid" 2>/dev/null || :' in source
    assert "exit 0\n}" in source
    assert source.index("trap stop_guardian") < source.index("/usr/bin/sleep")
    assert source.count("/usr/bin/sleep infinity &") == 1
    assert "while " not in source  # No automatic relaunch of a failed idle child.


def test_recipe_pins_base_and_replaces_both_image_startup_defaults():
    lines = data()["recipe_bytes"].decode("ascii").splitlines()
    assert lines == [
        "FROM --platform=linux/amd64 docker.io/library/postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317",
        "COPY --chown=0:0 --chmod=0555 guardian.sh /usr/local/libexec/oidc-test-guardian",
        "USER 0:0", 'ENTRYPOINT ["/usr/local/libexec/oidc-test-guardian"]', "CMD []",
        "STOPSIGNAL SIGTERM", "HEALTHCHECK NONE",
    ]
    assert not any(line.startswith(("RUN ", "ADD ", "ARG ", "ENV ", "ONBUILD ", "VOLUME ")) for line in lines)


def test_build_context_and_artifact_hashes_are_closed():
    supplied = data()
    assert supplied["ignore_bytes"] == b"**\n!guardian.sh\n!Dockerfile.in\n!.dockerignore\n"
    manifest = json.loads(supplied["manifest_bytes"])
    actual = {"guardian.sh": sha256(supplied["guardian_bytes"]).hexdigest(),
              "Dockerfile.in": sha256(supplied["recipe_bytes"]).hexdigest(),
              ".dockerignore": sha256(supplied["ignore_bytes"]).hexdigest()}
    assert manifest["artifacts"] == actual
    assert manifest["derived_digest"] == "unavailable_until_authorized_build"
    assert not any(name.endswith((".key", ".pem", ".env")) for name in actual)


def test_delivered_payloads_have_no_secret_literals_or_secret_input_channel():
    supplied = data()
    patterns = (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", r"AKIA[0-9A-Z]{16}",
                r"gh[pousr]_[A-Za-z0-9]{30,}", r"sk-(?:proj-)?[A-Za-z0-9_-]{30,}",
                r"(?i)(?:https?|postgres(?:ql)?)://[^\s/:]+:[^\s/@]+@")
    for name in ("guardian_bytes", "recipe_bytes", "ignore_bytes", "manifest_bytes"):
        source = supplied[name].decode("ascii")
        assert not any(re.search(pattern, source) for pattern in patterns)
    tokens = shlex.split(supplied["guardian_bytes"].decode("ascii"), comments=True)
    assert not set(tokens) & {"read", "readlink", "cat", "printenv", "env", "openssl"}


@pytest.mark.parametrize("field", ["guardian_bytes", "recipe_bytes", "ignore_bytes", "manifest_bytes", "bootstrap_bytes"])
def test_missing_and_unknown_inputs_fail_closed(field):
    supplied = data()
    del supplied[field]
    rejected(lambda: g.validate_preparation(**supplied))
    rejected(lambda: g.validate_preparation(**dict(data(), approved=True)))


@pytest.mark.parametrize("field", ["guardian_bytes", "recipe_bytes", "ignore_bytes", "manifest_bytes", "bootstrap_bytes"])
@pytest.mark.parametrize("mutation", ["crlf", "nul", "unicode_separator", "non_utf8", "mutable_bytes", "text"])
def test_only_original_immutable_ascii_lf_bytes_are_accepted(field, mutation):
    supplied = data()
    original = supplied[field]
    supplied[field] = {
        "crlf": original.replace(b"\n", b"\r\n"), "nul": original + b"\x00",
        "unicode_separator": original + "\u2028".encode(), "non_utf8": original + b"\xff",
        "mutable_bytes": bytearray(original), "text": original.decode("ascii"),
    }[mutation]
    rejected(lambda: g.validate_preparation(**supplied))


@pytest.mark.parametrize("payload", [b"postgres\n", b"initdb\n", b". ../bootstrap.sh\n", b"eval \"$@\"\n",
                                     b"docker start target\n", b"nc -l 5432\n", b"read command\n"])
def test_modified_guardian_cannot_be_approved_by_recomputed_manifest(payload):
    supplied = data()
    supplied["guardian_bytes"] += payload
    manifest = json.loads(supplied["manifest_bytes"])
    manifest["artifacts"]["guardian.sh"] = sha256(supplied["guardian_bytes"]).hexdigest()
    supplied["manifest_bytes"] = encode_manifest(manifest)
    rejected(lambda: g.validate_preparation(**supplied))


@pytest.mark.parametrize("field,payload", [("recipe_bytes", b"RUN touch /tmp/changed\n"),
    ("recipe_bytes", b'CMD ["postgres"]\n'), ("ignore_bytes", b"!secret.key\n")])
def test_extra_build_directive_or_context_inclusion_is_refused(field, payload):
    supplied = data()
    supplied[field] += payload
    rejected(lambda: g.validate_preparation(**supplied))


@pytest.mark.parametrize("field,value", [("base_image", "postgres:17"), ("platform", "linux/arm64"),
    ("entrypoint", ["docker-entrypoint.sh"]), ("command", ["postgres"]), ("activation_interface", "enabled"),
    ("initial_user", "postgres"), ("owner_uid", False), ("owner_gid", 0.0), ("mode", "0777"),
    ("stop_signal", "SIGKILL"), ("derived_digest", "sha256:" + "f" * 64)])
def test_unexpected_manifest_configuration_is_refused(field, value):
    supplied = data()
    manifest = json.loads(supplied["manifest_bytes"])
    manifest[field] = value
    supplied["manifest_bytes"] = encode_manifest(manifest)
    rejected(lambda: g.validate_preparation(**supplied))


def test_manifest_fields_runtime_and_duplicates_are_closed():
    original = data()
    for key in json.loads(original["manifest_bytes"]):
        supplied = data()
        manifest = json.loads(supplied["manifest_bytes"])
        del manifest[key]
        supplied["manifest_bytes"] = encode_manifest(manifest)
        rejected(lambda: g.validate_preparation(**supplied))
    for field, value in (("read_only_rootfs", False), ("privileged", True), ("cap_add", ["SYS_ADMIN"]),
                         ("cap_drop", []), ("guardian_writable_directories", ["/tmp"])):
        supplied = data()
        manifest = json.loads(supplied["manifest_bytes"])
        manifest["runtime_requirements"][field] = value
        supplied["manifest_bytes"] = encode_manifest(manifest)
        rejected(lambda: g.validate_preparation(**supplied))
    supplied = data()
    manifest = json.loads(supplied["manifest_bytes"])
    manifest["approved"] = True
    supplied["manifest_bytes"] = encode_manifest(manifest)
    rejected(lambda: g.validate_preparation(**supplied))
    supplied["manifest_bytes"] = b'{"base_image":"one","base_image":"two"}\n'
    rejected(lambda: g.validate_preparation(**supplied))


def test_bootstrap_refusal_is_unchanged_and_not_delivered_or_loaded():
    supplied = data()
    assert sha256(supplied["bootstrap_bytes"]).hexdigest() == "d319573e82d26516aca327a1294dd44d6abad2e5883995a1b557969a9aa24665"
    assert supplied["bootstrap_bytes"].split(b"\n")[:4] == [b"#!/usr/bin/env bash",
        b"# Preparation artifact: no configuration, argument or environment enables it.",
        b"printf '%s\\n' 'OIDC bootstrap operational authority is unavailable' >&2", b"exit 78"]
    assert b"bootstrap" not in supplied["recipe_bytes"] and b"bootstrap.sh" not in supplied["guardian_bytes"]
    supplied["bootstrap_bytes"] = supplied["bootstrap_bytes"].replace(b"exit 78\n", b"# exit 78\n", 1)
    rejected(lambda: g.validate_preparation(**supplied))


def test_public_errors_detach_active_context_without_logging(caplog, capsys):
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        rejected(lambda: g.validate_preparation(**dict(data(), guardian_bytes=MARKER)))
        rejected(lambda: g.validate_preparation(**dict(data(), manifest_bytes=b"invalid\n")))
        rejected(lambda: bool(g.validate_preparation(**data())))
    assert caplog.records == []
    output = capsys.readouterr()
    assert output.out == output.err == ""


def test_validator_import_and_validation_have_no_io_or_activation_flags(monkeypatch):
    supplied = data()
    source = Path(g.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert imports <= {"dataclasses", "functools", "hashlib", "json"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"open", "exec", "eval", "compile", "__import__"} for node in ast.walk(tree))
    for name in ("ALLOW_BOOTSTRAP", "APPROVED", "DOCKER_HOST", "PGPASSWORD"):
        monkeypatch.setenv(name, MARKER)
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("file IO")
        raise AssertionError("Offline validation must not read files")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    assert g.validate_preparation(**supplied).execution_authorized is False
    exec(compile(source, "guardian_validation_import_probe", "exec"), {"__name__": "guardian_validation_import_probe"})
    assert attempts == []
