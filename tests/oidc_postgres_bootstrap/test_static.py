"""Only pure validation and source inspection; never execute the shell/SQL."""

import ast
import builtins
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import socket
import subprocess
import threading
import traceback

import pytest

from oidc_postgres_support import campaign_contract
from oidc_postgres_bootstrap import validation as v


HERE = Path(__file__).parent
MARKER = "SYNTHETIC_PRIVATE_ERROR_MARKER"
SUFFIX = "a62b2d3d2b104a008c01202610290001"


@pytest.fixture(autouse=True)
def prohibit_operations(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("forbidden operation")
        raise AssertionError("Forbidden offline operation")

    for target, name in ((subprocess, "Popen"), (subprocess, "run"),
                         (socket.socket, "connect"), (socket.socket, "connect_ex"),
                         (socket, "create_connection"), (socket, "getaddrinfo"),
                         (threading.Thread, "start")):
        monkeypatch.setattr(target, name, forbidden)
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "sqlalchemy", "psycopg", "psycopg2", "docker", "alembic", "dotenv"}:
            forbidden()
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    yield
    assert attempts == []


def campaign():
    return campaign_contract(
        campaign_id="a62b2d3d-2b10-4a00-8c01-202610290001", container_id="f" * 64,
        container_name=f"oidc-tx-{SUFFIX}-postgres",
        image_ref="docker.io/library/postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317",
        image_id="sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317",
        platform="linux/amd64", network_id="bad3825904081e17d0c9dcf14ac7a88b3560cedaf60d8cb6c9912710b858b85e",
        network_name=f"oidc-tx-{SUFFIX}-net", subnet="172.30.91.0/28", gateway="172.30.91.1",
        storage_kind="tmpfs", storage_target="/var/lib/postgresql/data", storage_bytes=268435456,
        host="127.0.0.1", port=56439, database=f"oidct_{SUFFIX}",
        preparation_role=f"oidct_{SUFFIX}_owner", application_role=f"oidct_{SUFFIX}_app",
        observation_role=f"oidct_{SUFFIX}_observer", transport="verify-full", ca_sha256="a" * 64,
        server_address="172.30.91.2", server_port=5432, server_version_num=170010,
        cluster_name=f"oidc-test-{SUFFIX}", scope="public.oidc_transactions")


def plan_values():
    return dict(
        campaign=campaign(), engine_id="a78547e2-4024-47fd-80f3-63a4b1c48b0c",
        # Explicit candidate only: no claim that Docker Desktop will use it.
        source_cidr="172.30.91.1/32",
        paths=tuple(v.PathRule(kind, path, "postgres", 0o700) for kind, path in (
            ("root", "/var/lib/postgresql/data"), ("pgdata", "/var/lib/postgresql/data/pgdata"),
            ("socket", "/var/lib/postgresql/data/run"), ("secrets", "/var/lib/postgresql/data/secrets"),
            ("tls", "/var/lib/postgresql/data/tls"), ("logs", "/var/lib/postgresql/data/log"),
            ("work", "/var/lib/postgresql/data/work"))),
        roles=tuple(v.RoleRule(kind, f"oidct_{SUFFIX}_{kind}", False, False, False, False, False, kind == "owner")
                    for kind in ("owner", "app", "observer")),
        postgres_version="17.10", local_auth="scram-sha-256", host_auth="scram-sha-256",
        local_listen="", client_mode="verify-full", tls_min="TLSv1.2")


def plan():
    return v.bootstrap_plan(**plan_values())


def templates():
    return {name: (HERE / name).read_bytes().decode("utf-8") for name in (
        "postgresql.local.conf.in", "postgresql.tls.conf.in", "pg_hba.local.conf.in",
        "pg_hba.tls.conf.in", "roles.sql.in", "openssl.cnf.in")}


def synthetic_secrets():
    return {kind: ("synthetic-offline-" + kind + "-fixture-only").encode("ascii")
            for kind in ("bootstrap", "owner", "app", "observer")}


def observations():
    # Independent literals: do not copy PHASE_REQUIREMENTS from the validator.
    facts = (
        (("authority", "unavailable_in_this_lot"), ("environment", "explicit_clean"), ("secrets", "staged_private")),
        (("filesystem", "tmpfs_268435456"), ("root_owner", "postgres"), ("root_mode", "0700"),
         ("extra_mounts", "none"), ("generation", "first_start_only")),
        (("version", "17.10"), ("linux_user", "postgres"), ("pgdata_before", "empty"),
         ("local_auth", "scram-sha-256"), ("host_auth", "scram-sha-256"), ("tcp", "absent"), ("cluster", "initialized")),
        (("transport", "private_unix_socket"), ("tcp", "absent"), ("roles", "three_restricted_nologin"),
         ("database", "dedicated"), ("table_oidc", "absent"), ("global_stats_grant", "absent")),
        (("ca", "campaign_dedicated"), ("server_san", "IP:127.0.0.1"), ("key_owner", "postgres"),
         ("key_mode", "0600"), ("hba", "validated_exact"), ("tcp", "absent")),
        (("roles", "passwords_installed_before_login"), ("bootstrap_login", "disabled"),
         ("local_server", "stopped"), ("container", "same_running_generation"),
         ("tls", "required"), ("hba", "validated_exact")),
        (("client", "verify-full"), ("sql_roles", "three_independent_sessions"),
         ("source", "observed_matching_approved_cidr"), ("identity", "fresh_bound_connections"), ("table_oidc", "absent")),
    )
    return tuple(v.PhaseEvidence(phase, "a78547e2-4024-47fd-80f3-63a4b1c48b0c", "f" * 64,
        "bad3825904081e17d0c9dcf14ac7a88b3560cedaf60d8cb6c9912710b858b85e",
        "a62b2d3d-2b10-4a00-8c01-202610290001", 1, False, facts[index])
        for index, phase in enumerate(("A", "B", "C", "D", "E", "F", "G")))


def rejected(operation):
    with pytest.raises(v.BootstrapRejected) as caught:
        operation()
    error = caught.value
    assert str(error) == "OIDC bootstrap preparation rejected"
    assert error.__context__ is None and error.__cause__ is None
    assert error.__suppress_context__ is True
    assert MARKER not in repr(error) + "".join(traceback.format_exception(error))


def test_nominal_artifacts_only_produce_offline_results():
    prepared = plan()
    assert v.validate_templates(prepared, templates()).completed == ()
    assert v.validate_entrypoint((HERE / "bootstrap.sh").read_bytes()).completed == ()
    result = v.validate_phases(prepared, observations(), synthetic_secrets())
    assert result.completed == ("A", "B", "C", "D", "E", "F", "G")
    for value in (prepared, result, *prepared.paths, *prepared.roles, *observations()):
        assert value.execution_authorized is False
        assert "offline" in repr(value)
        rejected(lambda: bool(value))
    with pytest.raises(FrozenInstanceError):
        prepared.source_cidr = "0.0.0.0/0"


def test_configuration_is_closed_and_complete():
    rejected(lambda: v.bootstrap_plan())
    for field in plan_values():
        values = plan_values()
        del values[field]
        rejected(lambda: v.bootstrap_plan(**values))
    rejected(lambda: v.bootstrap_plan(**dict(plan_values(), authorize=True)))


@pytest.mark.parametrize("field,value", [
    ("engine_id", "other"), ("source_cidr", "0.0.0.0/0"), ("source_cidr", "172.30.91.0/28"),
    ("source_cidr", "8.8.8.8/32"), ("source_cidr", "implicit"),
    ("postgres_version", "17"), ("local_auth", "trust"), ("host_auth", "trust"),
    ("host_auth", "md5"), ("local_listen", "*"), ("local_listen", "127.0.0.1"),
    ("client_mode", "require"), ("client_mode", "prefer"), ("tls_min", "TLSv1"),
])
def test_insecure_plan_is_refused(field, value):
    rejected(lambda: v.bootstrap_plan(**dict(plan_values(), **{field: value})))


@pytest.mark.parametrize("field,value", [
    ("container_id", "00dc9dd7a2b2204a5017662cadfdc9c8ee9ec48b70fe75c56ef92362c641c03e"),
    ("network_id", "c" * 64), ("image_ref", "docker.io/library/postgres@sha256:" + "b" * 64),
    ("image_id", "sha256:" + "c" * 64), ("platform", "linux/arm64"),
    ("host", "::1"), ("port", 56440), ("storage_bytes", 536870912),
    ("server_version_num", 170009), ("server_address", "172.30.91.3"),
    ("scope", "public.users"),
])
def test_divergent_campaign_and_old_container_are_refused(field, value):
    values = plan_values()
    values["campaign"] = replace(values["campaign"], **{field: value})
    rejected(lambda: v.bootstrap_plan(**values))


@pytest.mark.parametrize("index", range(7))
@pytest.mark.parametrize("field,value", [("path", "/outside"), ("path", "/var/lib/postgresql/data/../outside"),
    ("owner", "root"), ("mode", 0o755), ("mode", True)])
def test_every_path_and_traversal_permission_is_checked(index, field, value):
    values = plan_values()
    paths = list(values["paths"])
    paths[index] = replace(paths[index], **{field: value})
    values["paths"] = tuple(paths)
    rejected(lambda: v.bootstrap_plan(**values))


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("field", ["superuser", "createdb", "createrole", "replication", "bypassrls"])
def test_every_campaign_role_is_restricted(index, field):
    values = plan_values()
    roles = list(values["roles"])
    roles[index] = replace(roles[index], **{field: True})
    values["roles"] = tuple(roles)
    rejected(lambda: v.bootstrap_plan(**values))


def test_app_has_no_ddl_and_roles_remain_nologin_before_password_installation():
    values = plan_values()
    values["roles"] = (values["roles"][0], replace(values["roles"][1], ddl=True), values["roles"][2])
    rejected(lambda: v.bootstrap_plan(**values))
    sql = templates()["roles.sql.in"]
    assert sql.count(" NOLOGIN ") == 3
    assert "REVOKE ALL PRIVILEGES ON DATABASE" in sql
    assert 'GRANT CREATE ON SCHEMA public TO "@OWNER@";' in sql
    assert "CREATE TABLE" not in sql and "pg_read_all_stats" not in sql


@pytest.mark.parametrize("variant", ["missing", "empty", "too_short", "newline", "shared", "wrong_type"])
def test_passwords_are_explicit_nonempty_distinct_synthetic_data(variant):
    secrets = synthetic_secrets()
    if variant == "missing":
        del secrets["bootstrap"]
    elif variant == "empty":
        secrets["bootstrap"] = b""
    elif variant == "too_short":
        secrets["bootstrap"] = b"synthetic"
    elif variant == "newline":
        secrets["bootstrap"] += b"\n"
    elif variant == "shared":
        secrets["app"] = secrets["owner"]
    else:
        secrets["bootstrap"] = MARKER
    rejected(lambda: v.validate_phases(plan(), observations(), secrets))


@pytest.mark.parametrize("name,old,new", [
    ("postgresql.local.conf.in", "listen_addresses = ''", "listen_addresses = '*'"),
    ("postgresql.local.conf.in", "ssl = off", "ssl = on"),
    ("postgresql.tls.conf.in", "ssl = on", "ssl = off"),
    ("postgresql.tls.conf.in", "ssl_key_file = '@ROOT@/tls/server.key'", "ssl_key_file = '/outside/key'"),
    ("postgresql.tls.conf.in", "ssl_min_protocol_version = 'TLSv1.2'", "ssl_min_protocol_version = 'TLSv1'"),
    ("postgresql.local.conf.in", "temp_tablespaces = ''", "temp_tablespaces = 'external'"),
    ("pg_hba.local.conf.in", "scram-sha-256", "trust"),
    ("pg_hba.tls.conf.in", "hostssl", "host"),
    ("pg_hba.tls.conf.in", "@SOURCE_CIDR@", "0.0.0.0/0"),
    ("pg_hba.tls.conf.in", "@DATABASE@", "all"),
    ("pg_hba.tls.conf.in", "scram-sha-256", "md5"),
    ("openssl.cnf.in", "subjectAltName = IP:127.0.0.1", "subjectAltName = DNS:localhost"),
    ("roles.sql.in", "NOSUPERUSER", "SUPERUSER"),
    ("roles.sql.in", "NOLOGIN", "LOGIN"),
])
def test_dangerous_template_changes_are_refused(name, old, new):
    files = templates()
    assert old in files[name]
    files[name] = files[name].replace(old, new)
    rejected(lambda: v.validate_templates(plan(), files))


@pytest.mark.parametrize("name", ["postgresql.local.conf.in", "postgresql.tls.conf.in", "pg_hba.local.conf.in", "pg_hba.tls.conf.in", "roles.sql.in", "openssl.cnf.in"])
def test_absent_or_extended_template_is_refused(name):
    files = templates()
    del files[name]
    rejected(lambda: v.validate_templates(plan(), files))
    files = templates()
    files[name] += "\ninclude = '/unexpected'\n"
    rejected(lambda: v.validate_templates(plan(), files))


@pytest.mark.parametrize("key", ["ssl", "ssl_cert_file", "ssl_key_file", "ssl_ca_file", "ssl_min_protocol_version"])
def test_each_tls_setting_is_mandatory(key):
    files = templates()
    files["postgresql.tls.conf.in"] = "\n".join(
        line for line in files["postgresql.tls.conf.in"].splitlines() if not line.startswith(key + " ="))
    rejected(lambda: v.validate_templates(plan(), files))


@pytest.mark.parametrize("index", range(7))
def test_every_phase_requires_its_own_independent_postconditions(index):
    proof = observations()
    for observation in range(len(proof[index].observations)):
        altered = list(proof[:index + 1])
        conditions = list(altered[index].observations)
        key, _ = conditions[observation]
        conditions[observation] = (key, "unverified")
        altered[index] = replace(altered[index], observations=tuple(conditions))
        rejected(lambda: v.validate_phases(plan(), tuple(altered), synthetic_secrets()))


@pytest.mark.parametrize("field,value", [("engine_id", "other"), ("container_id", "b" * 64),
    ("network_id", "c" * 64), ("campaign_id", "other"), ("generation", 2),
    ("generation", True), ("invalidated", True), ("phase", "B"), ("observations", (("exit_code", "0"),))])
def test_identity_generation_invalidation_and_phase_order_are_checked(field, value):
    proof = (replace(observations()[0], **{field: value}),)
    rejected(lambda: v.validate_phases(plan(), proof, synthetic_secrets()))


def test_incomplete_phase_history_does_not_authorize_continuation():
    proof = observations()
    rejected(lambda: v.validate_phases(plan(), proof[1:], synthetic_secrets()))
    rejected(lambda: v.validate_phases(plan(), (proof[0], proof[2]), synthetic_secrets()))
    assert v.validate_phases(plan(), proof[:1], synthetic_secrets()).completed == ("A",)


@pytest.mark.parametrize("change", ["remove_exit", "env_bypass", "premature_command", "remove_phase_guard", "trust"])
def test_script_is_permanently_gated_in_this_lot(change):
    source = (HERE / "bootstrap.sh").read_bytes()
    if change == "remove_exit":
        source = source.replace(b"exit 78", b"true", 1)
    elif change == "env_bypass":
        source = source.replace(b"exit 78", b'if [ "$ALLOW_BOOTSTRAP" != 1 ]; then exit 78; fi', 1)
    elif change == "premature_command":
        source = b"initdb\n" + source
    elif change == "remove_phase_guard":
        source = source.replace(b"live_gate C || return 78", b"true")
    else:
        source = source.replace(b"--auth-local=scram-sha-256", b"--auth-local=trust")
    rejected(lambda: v.validate_entrypoint(source))


def test_import_has_no_io_or_operational_dependency(monkeypatch):
    source = (HERE / "validation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert imports <= {"dataclasses", "functools", "ipaddress", "re", "oidc_postgres_support"}
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("file access")
        raise AssertionError("File access forbidden at import")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    namespace = {"__name__": "offline_bootstrap_import_probe"}
    exec(compile(source, "offline_bootstrap_import_probe", "exec"), namespace)
    assert attempts == []


@pytest.mark.parametrize("path", ["plan", "templates", "phases", "entrypoint", "bool"])
def test_errors_remain_sanitized_inside_active_exception(path, caplog, capsys):
    operations = {"plan": lambda: v.bootstrap_plan(campaign=MARKER),
        "templates": lambda: v.validate_templates(plan(), {"secret": MARKER}),
        "phases": lambda: v.validate_phases(plan(), observations(), {"bootstrap": MARKER}),
        "entrypoint": lambda: v.validate_entrypoint(MARKER), "bool": lambda: bool(plan())}
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        rejected(operations[path])
    assert caplog.records == []
    output = capsys.readouterr()
    assert output.out == output.err == ""


def test_environment_flags_and_libpq_settings_have_no_authority(monkeypatch):
    for name in ("ALLOW_BOOTSTRAP", "PGHOST", "PGPASSWORD", "DATABASE_URL"):
        monkeypatch.setenv(name, MARKER)
    assert plan().execution_authorized is False
    rejected(lambda: v.bootstrap_plan())
    rejected(lambda: bool(v.validate_phases(plan(), observations(), synthetic_secrets())))


@pytest.mark.parametrize("variant", [
    "hash_shell", "hash_plain", "direct_shell", "inline_shell", "extra_meta",
    "extra_connect", "misplaced_connect", "modified_connect", "inline_connect_meta",
    "uppercase_connect", "leading_blank", "extra_blank", "space_only_line", "sql_comment",
])
def test_sql_closed_model_rejects_hidden_and_unexpected_psql_commands(variant):
    files = templates()
    original = files["roles.sql.in"]
    lines = original.split("\n")[:-1]
    if variant == "hash_shell":
        lines.append("# \\! printf SYNTHETIC_ONLY")
    elif variant == "hash_plain":
        lines.insert(0, "# not a SQL comment")
    elif variant == "direct_shell":
        lines.append("\\! printf SYNTHETIC_ONLY")
    elif variant == "inline_shell":
        lines[0] += " \\! printf SYNTHETIC_ONLY"
    elif variant == "extra_meta":
        lines.append("\\gexec")
    elif variant == "extra_connect":
        lines.append(lines[6])
    elif variant == "misplaced_connect":
        lines[5], lines[6] = lines[6], lines[5]
    elif variant == "modified_connect":
        lines[6] = lines[6].replace("5432", "5433")
    elif variant == "inline_connect_meta":
        lines[6] += " \\! printf SYNTHETIC_ONLY"
    elif variant == "uppercase_connect":
        lines[6] = lines[6].replace("\\connect", "\\CONNECT")
    elif variant == "leading_blank":
        lines.insert(0, "")
    elif variant == "extra_blank":
        lines.append("")
    elif variant == "space_only_line":
        lines.insert(6, "   ")
    else:
        lines.append("-- comments are outside this closed SQL model")
    files["roles.sql.in"] = "\n".join(lines) + "\n"
    rejected(lambda: v.validate_templates(plan(), files))


@pytest.mark.parametrize("separator", [
    "\r", "\r\n", "\0", "\t", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x1f",
    "\x7f", "\x85", "\xa0", "\u2028", "\u2029", "\ufeff", "\u202e",
])
def test_sql_rejects_control_characters_and_ambiguous_separators(separator):
    files = templates()
    files["roles.sql.in"] += "# hidden" + separator + "\\! printf SYNTHETIC_ONLY\n"
    rejected(lambda: v.validate_templates(plan(), files))


def test_sql_nominal_connect_has_exact_shape_and_position():
    files = templates()
    lines = files["roles.sql.in"].split("\n")
    assert len(lines) == 11 and lines[-1] == ""
    assert lines[6] == '\\connect "@DATABASE@" "@BOOTSTRAP@" "@ROOT@/run" 5432'
    assert sum("\\" in line for line in lines) == 1
    assert v.validate_templates(plan(), files).completed == ()


@pytest.mark.parametrize("name", [
    "postgresql.local.conf.in", "postgresql.tls.conf.in", "pg_hba.local.conf.in",
    "pg_hba.tls.conf.in", "openssl.cnf.in",
])
def test_hash_comments_belong_only_to_their_configuration_formats(name):
    files = templates()
    files[name] = "# harmless configuration comment\n\n" + files[name]
    assert v.validate_templates(plan(), files).completed == ()


@pytest.mark.parametrize("separator", [
    b"\r", b"\r\n", b"\0", b"\t", b"\v", b"\f", b"\x1c", b"\x1d", b"\x1e", b"\x1f",
    b"\x7f", "\x85".encode("utf-8"), "\xa0".encode("utf-8"),
    "\u2028".encode("utf-8"), "\u2029".encode("utf-8"),
    "\ufeff".encode("utf-8"), "\u202e".encode("utf-8"),
])
def test_bash_rejects_raw_separators_that_might_hide_the_exit(separator):
    source = (HERE / "bootstrap.sh").read_bytes()
    altered = source.replace(b"\nexit 78\n", b"\n# hidden" + separator + b"exit 78\n", 1)
    assert altered != source
    rejected(lambda: v.validate_entrypoint(altered))


@pytest.mark.parametrize("variant", [
    "crlf_entire_file", "commented_exit", "missing_exit", "missing_printf",
    "both_commented", "missing_shebang", "missing_final_lf", "non_utf8", "utf8_bom",
])
def test_bash_rejects_invalid_raw_file_or_refusal_prefix(variant):
    source = (HERE / "bootstrap.sh").read_bytes()
    if variant == "crlf_entire_file":
        altered = source.replace(b"\n", b"\r\n")
    elif variant == "commented_exit":
        altered = source.replace(b"\nexit 78\n", b"\n# exit 78\n", 1)
    elif variant == "missing_exit":
        altered = source.replace(b"\nexit 78\n", b"\n", 1)
    elif variant == "missing_printf":
        altered = b"\n".join(line for line in source.split(b"\n")
                             if line != b"printf '%s\\n' 'OIDC bootstrap operational authority is unavailable' >&2")
    elif variant == "both_commented":
        altered = source.replace(b"\nprintf ", b"\n# printf ", 1).replace(b"\nexit 78\n", b"\n# exit 78\n", 1)
    elif variant == "missing_shebang":
        altered = source.partition(b"\n")[2]
    elif variant == "missing_final_lf":
        altered = source[:-1]
    elif variant == "non_utf8":
        altered = source.replace(b"\nexit 78\n", b"\n# \xffexit 78\n", 1)
    else:
        altered = b"\xef\xbb\xbf" + source
    rejected(lambda: v.validate_entrypoint(altered))


@pytest.mark.parametrize("input_type", ["str", "bytearray", "memoryview"])
def test_bash_requires_original_immutable_bytes_without_text_reencoding(input_type):
    source = (HERE / "bootstrap.sh").read_bytes()
    value = {"str": lambda: source.decode("utf-8"), "bytearray": lambda: bytearray(source),
             "memoryview": lambda: memoryview(source)}[input_type]()
    rejected(lambda: v.validate_entrypoint(value))


def test_bash_lf_prefix_and_original_file_are_accepted_without_execution():
    source = (HERE / "bootstrap.sh").read_bytes()
    assert source.startswith(b"#!/usr/bin/env bash\n") and b"\r" not in source
    assert b"\nexit 78\n" in source
    result = v.validate_entrypoint(source)
    assert result.completed == () and result.execution_authorized is False


@pytest.mark.parametrize("format_name", ["sql", "bash"])
def test_malformed_inputs_are_sanitized_with_an_active_sensitive_context(format_name):
    files = templates()
    files["roles.sql.in"] += "# " + MARKER + "\r\\! printf SYNTHETIC_ONLY\n"
    script = (HERE / "bootstrap.sh").read_bytes() + b"\xff" + MARKER.encode("ascii") + b"\n"
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        if format_name == "sql":
            rejected(lambda: v.validate_templates(plan(), files))
        else:
            rejected(lambda: v.validate_entrypoint(script))
