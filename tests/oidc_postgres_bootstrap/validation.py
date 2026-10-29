"""Offline declarations only. No operating authority, IO, SQL or process API."""

from dataclasses import dataclass, fields
from functools import wraps
from ipaddress import IPv4Network
import re

from oidc_postgres_support import CampaignContract, validate_contract


ENGINE_ID = "a78547e2-4024-47fd-80f3-63a4b1c48b0c"
OLD_CONTAINER_ID = "00dc9dd7a2b2204a5017662cadfdc9c8ee9ec48b70fe75c56ef92362c641c03e"
NETWORK_ID = "bad3825904081e17d0c9dcf14ac7a88b3560cedaf60d8cb6c9912710b858b85e"
IMAGE_DIGEST = "7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317"
ROOT = "/var/lib/postgresql/data"
PHASES = ("A", "B", "C", "D", "E", "F", "G")


class BootstrapRejected(ValueError):
    def __init__(self):
        super().__init__("OIDC bootstrap preparation rejected")


def _reject():
    try:
        raise BootstrapRejected() from None
    except BootstrapRejected as error:
        error.__context__ = None
        error.__cause__ = None
        error.__suppress_context__ = True
        raise


def _guarded(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            pass
        _reject()
    return checked


class _Inert:
    __slots__ = ()

    def __repr__(self):
        return f"<{type(self).__name__}: offline>"

    def __bool__(self):
        _reject()

    @property
    def execution_authorized(self):
        return False


@dataclass(frozen=True, slots=True, repr=False)
class PathRule(_Inert):
    kind: str
    path: str
    owner: str
    mode: int


@dataclass(frozen=True, slots=True, repr=False)
class RoleRule(_Inert):
    kind: str
    name: str
    superuser: bool
    createdb: bool
    createrole: bool
    replication: bool
    bypassrls: bool
    ddl: bool


@dataclass(frozen=True, slots=True, repr=False)
class BootstrapPlan(_Inert):
    campaign: CampaignContract
    engine_id: str
    source_cidr: str
    paths: tuple[PathRule, ...]
    roles: tuple[RoleRule, ...]
    postgres_version: str
    local_auth: str
    host_auth: str
    local_listen: str
    client_mode: str
    tls_min: str


@dataclass(frozen=True, slots=True, repr=False)
class PhaseEvidence(_Inert):
    phase: str
    engine_id: str
    container_id: str
    network_id: str
    campaign_id: str
    generation: int
    invalidated: bool
    observations: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True, repr=False)
class OfflineResult(_Inert):
    completed: tuple[str, ...]
    classification: str = "injected_static_evidence_only"


def _require(condition):
    if not condition:
        _reject()


def _shape(value, cls):
    _require(type(value) is cls)
    for field in fields(cls):
        member = getattr(value, field.name)
        if field.type in (str, int, bool):
            _require(type(member) is field.type)
        elif field.type is CampaignContract:
            validate_contract(member)
        else:
            _require(type(member) is tuple)


def _plan(plan):
    _shape(plan, BootstrapPlan)
    campaign = plan.campaign
    _require(plan.engine_id == ENGINE_ID)
    # An approved recreation must receive a new ID, never reuse this stopped one.
    _require(campaign.container_id != OLD_CONTAINER_ID)
    _require(campaign.campaign_id == "a62b2d3d-2b10-4a00-8c01-202610290001")
    _require(campaign.network_id == NETWORK_ID)
    _require(campaign.image_ref == "docker.io/library/postgres@sha256:" + IMAGE_DIGEST)
    _require(campaign.image_id == "sha256:" + IMAGE_DIGEST and campaign.platform == "linux/amd64")
    _require(campaign.subnet == "172.30.91.0/28" and campaign.gateway == "172.30.91.1")
    _require(campaign.server_address == "172.30.91.2")
    _require(campaign.storage_bytes == 268435456)
    _require(campaign.host == "127.0.0.1" and campaign.port == 56439)
    _require(campaign.server_version_num == 170010)
    _require(plan.postgres_version == "17.10")
    _require(plan.local_auth == plan.host_auth == "scram-sha-256")
    _require(plan.local_listen == "")
    _require(plan.client_mode == "verify-full" and plan.tls_min == "TLSv1.2")
    source = IPv4Network(plan.source_cidr, strict=True)
    _require(source.prefixlen == 32)
    _require(any(source.subnet_of(IPv4Network(block)) for block in
                 ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")))
    expected = {"root": ROOT, "pgdata": ROOT + "/pgdata", "socket": ROOT + "/run",
                "secrets": ROOT + "/secrets", "tls": ROOT + "/tls",
                "logs": ROOT + "/log", "work": ROOT + "/work"}
    _require(len(plan.paths) == len(expected))
    seen = set()
    for rule in plan.paths:
        _shape(rule, PathRule)
        _require(rule.kind in expected and rule.kind not in seen)
        seen.add(rule.kind)
        _require(rule.path == expected[rule.kind] and rule.owner == "postgres" and rule.mode == 0o700)
    _require(len(plan.roles) == 3)
    names = {"owner": campaign.preparation_role, "app": campaign.application_role,
             "observer": campaign.observation_role}
    seen = set()
    for role in plan.roles:
        _shape(role, RoleRule)
        _require(role.kind in names and role.kind not in seen)
        seen.add(role.kind)
        _require(role.name == names[role.kind])
        _require(not any((role.superuser, role.createdb, role.createrole, role.replication, role.bypassrls)))
        _require(role.ddl is (role.kind == "owner"))
    return plan


@_guarded
def bootstrap_plan(**values):
    return _plan(BootstrapPlan(**values))


def _tokens(plan):
    campaign = plan.campaign
    return {"ROOT": ROOT, "DATABASE": campaign.database, "OWNER": campaign.preparation_role,
            "APP": campaign.application_role, "OBSERVER": campaign.observation_role,
            "BOOTSTRAP": campaign.database + "_bootstrap", "SERVER": campaign.server_address,
            "CLUSTER": campaign.cluster_name, "SOURCE_CIDR": plan.source_cidr}


def _physical_lines(text):
    _require(type(text) is str and bool(text))
    # Closed ASCII artifacts: LF is the only permitted control/separator.
    _require(all(character == "\n" or " " <= character <= "~" for character in text))
    return tuple(text.split("\n"))


def _config_lines(text, *, format_name):
    lines = _physical_lines(text)
    if format_name == "sql":
        # Exact physical SQL lines, including the single final LF. No comment
        # removal: psql does not treat '#' as a SQL comment.
        _require(lines[-1] == "")
        lines = lines[:-1]
        for index, line in enumerate(lines):
            _require(bool(line) and line == line.strip(" ") and not line.startswith("#"))
            if "\\" in line:
                _require(index == 6 and line.startswith("\\connect ") and line.count("\\") == 1)
        # The complete tuple is subsequently compared with the exact SQL model,
        # including connect arguments and position. This is not a SQL parser.
        return lines
    _require(format_name in ("postgresql", "hba", "openssl"))
    # These three configuration formats support full-line hash comments.
    return tuple(line.strip(" ") for line in lines
                 if line.strip(" ") and not line.lstrip(" ").startswith("#"))


def _postgres_expected(plan, tls):
    common = {
        "data_directory": f"'{ROOT}/pgdata'", "port": "5432",
        "unix_socket_directories": f"'{ROOT}/run'", "unix_socket_permissions": "0700",
        "cluster_name": f"'{plan.campaign.cluster_name}'", "password_encryption": "'scram-sha-256'",
        "logging_collector": "on", "log_directory": f"'{ROOT}/log'", "log_statement": "'none'",
        "log_min_error_statement": "panic", "log_error_verbosity": "terse",
        "log_parameter_max_length_on_error": "0", "max_connections": "12",
        "shared_buffers": "'32MB'", "work_mem": "'1MB'", "maintenance_work_mem": "'16MB'",
        "min_wal_size": "'32MB'", "max_wal_size": "'64MB'", "temp_file_limit": "32768",
        "temp_tablespaces": "''", "fsync": "on", "synchronous_commit": "on", "full_page_writes": "on",
        "listen_addresses": f"'{plan.campaign.server_address}'" if tls else "''",
        "hba_file": f"'{ROOT}/work/pg_hba.{'tls' if tls else 'local'}.conf'", "ssl": "on" if tls else "off",
    }
    if tls:
        common.update(ssl_cert_file=f"'{ROOT}/tls/server.crt'", ssl_key_file=f"'{ROOT}/tls/server.key'",
                      ssl_ca_file=f"'{ROOT}/tls/ca.crt'", ssl_min_protocol_version="'TLSv1.2'")
    return common


@_guarded
def validate_templates(plan, templates):
    """Validate supplied text without opening files or rendering runnable output."""
    _plan(plan)
    _require(type(templates) is dict and set(templates) == {
        "postgresql.local.conf.in", "postgresql.tls.conf.in", "pg_hba.local.conf.in",
        "pg_hba.tls.conf.in", "roles.sql.in", "openssl.cnf.in"})
    tokens = _tokens(plan)
    rendered = {}
    for name, text in templates.items():
        _require(type(text) is str)
        for token in re.findall(r"@([A-Z_]+)@", text):
            _require(token in tokens)
        for token, value in tokens.items():
            text = text.replace("@" + token + "@", value)
        _require("@" not in text)
        if name == "roles.sql.in":
            format_name = "sql"
        elif name.startswith("postgresql."):
            format_name = "postgresql"
        elif name.startswith("pg_hba."):
            format_name = "hba"
        else:
            format_name = "openssl"
        rendered[name] = _config_lines(text, format_name=format_name)
    for tls in (False, True):
        name = f"postgresql.{'tls' if tls else 'local'}.conf.in"
        expected = _postgres_expected(plan, tls)
        lines = rendered[name]
        _require(len(lines) == len(expected))
        parsed = {}
        for line in lines:
            key, value = (part.strip() for part in line.split("=", 1))
            _require(key not in parsed)
            parsed[key] = value
        _require(parsed == expected)
    database, admin = tokens["DATABASE"], tokens["BOOTSTRAP"]
    _require(rendered["pg_hba.local.conf.in"] == (
        f'local postgres "{admin}" scram-sha-256', f'local "{database}" "{admin}" scram-sha-256',
        "local all all reject", "host all all all reject"))
    roles = ",".join('"' + tokens[kind] + '"' for kind in ("OWNER", "APP", "OBSERVER"))
    _require(rendered["pg_hba.tls.conf.in"] == (
        "local all all reject", "hostnossl all all all reject",
        f'hostssl "{database}" {roles} {plan.source_cidr} scram-sha-256', "hostssl all all all reject"))
    # Literal SQL identifiers are safe because the campaign contract fixes their alphabet.
    expected_roles = tuple(f'CREATE ROLE "{tokens[kind]}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;'
                           for kind in ("OWNER", "APP", "OBSERVER"))
    _require(rendered["roles.sql.in"] == expected_roles + (
        f'CREATE DATABASE "{database}" OWNER "{admin}" TEMPLATE template0;',
        f'REVOKE ALL PRIVILEGES ON DATABASE "{database}" FROM PUBLIC;',
        f'GRANT CONNECT ON DATABASE "{database}" TO {roles};',
        f'\\connect "{database}" "{admin}" "{ROOT}/run" 5432',
        'REVOKE ALL ON SCHEMA public FROM PUBLIC;',
        f'GRANT USAGE ON SCHEMA public TO {roles};',
        f'GRANT CREATE ON SCHEMA public TO "{tokens["OWNER"]}";',))
    _require(rendered["openssl.cnf.in"] == ("[req]", "prompt = no", "distinguished_name = dn",
        "req_extensions = server_ext", "[dn]", "CN = OIDC TEST", "[server_ext]",
        "basicConstraints = critical,CA:FALSE", "keyUsage = critical,digitalSignature,keyEncipherment",
        "extendedKeyUsage = serverAuth", "subjectAltName = IP:127.0.0.1"))
    return OfflineResult(())


@_guarded
def validate_entrypoint(source):
    """Require original bytes with LF, check guards, never invoke a shell."""
    _require(type(source) is bytes and source.endswith(b"\n"))
    # Strict decoding does not normalize newlines. Callers must not supply text
    # read with universal-newline conversion or re-encode normalized text.
    text = source.decode("utf-8", errors="strict")
    physical = _physical_lines(text)
    _require(physical[0] == "#!/usr/bin/env bash")
    lines = tuple(line.strip(" ") for line in physical[1:]
                  if line.strip(" ") and not line.lstrip(" ").startswith("#"))
    _require(lines[:2] == (
        "printf '%s\\n' 'OIDC bootstrap operational authority is unavailable' >&2", "exit 78"))
    for phase in PHASES:
        _require(f"phase_{phase}() {{\n    live_gate {phase} || return 78\n" in text)
    _require("--auth-local=scram-sha-256" in text and "--auth-host=scram-sha-256" in text)
    _require("--pwfile=\"$SECRETS/bootstrap.pw\"" in text)
    _require('live_postcondition F || return 78\n    exec ' in text)
    _require(not any(word in text for word in ("--auth=trust", "--auth-local=trust", "--auth-host=trust", "eval ", "docker-entrypoint.sh")))
    return OfflineResult(())


# Each phase needs independent observations, not an earlier exit code or flag.
PHASE_REQUIREMENTS = {
    "A": (("authority", "unavailable_in_this_lot"), ("environment", "explicit_clean"), ("secrets", "staged_private")),
    "B": (("filesystem", "tmpfs_268435456"), ("root_owner", "postgres"), ("root_mode", "0700"),
          ("extra_mounts", "none"), ("generation", "first_start_only")),
    "C": (("version", "17.10"), ("linux_user", "postgres"), ("pgdata_before", "empty"),
          ("local_auth", "scram-sha-256"), ("host_auth", "scram-sha-256"), ("tcp", "absent"), ("cluster", "initialized")),
    "D": (("transport", "private_unix_socket"), ("tcp", "absent"), ("roles", "three_restricted_nologin"),
          ("database", "dedicated"), ("table_oidc", "absent"), ("global_stats_grant", "absent")),
    "E": (("ca", "campaign_dedicated"), ("server_san", "IP:127.0.0.1"), ("key_owner", "postgres"),
          ("key_mode", "0600"), ("hba", "validated_exact"), ("tcp", "absent")),
    "F": (("roles", "passwords_installed_before_login"), ("bootstrap_login", "disabled"),
          ("local_server", "stopped"), ("container", "same_running_generation"),
          ("tls", "required"), ("hba", "validated_exact")),
    "G": (("client", "verify-full"), ("sql_roles", "three_independent_sessions"),
          ("source", "observed_matching_approved_cidr"), ("identity", "fresh_bound_connections"),
          ("table_oidc", "absent")),
}


@_guarded
def validate_phases(plan, evidence, secret_material):
    """Syntactic simulation only. This never issues a phase execution token."""
    _plan(plan)
    _require(type(secret_material) is dict and set(secret_material) == {"bootstrap", "owner", "app", "observer"})
    _require(all(type(value) is bytes and len(value) >= 32 and not any(c in value for c in (b"\0", b"\n", b"\r"))
                 for value in secret_material.values()))
    _require(len(set(secret_material.values())) == 4)
    _require(type(evidence) is tuple and 0 < len(evidence) <= len(PHASES))
    for phase, record in zip(PHASES, evidence):
        _shape(record, PhaseEvidence)
        _require(record.phase == phase and record.engine_id == plan.engine_id)
        _require(record.container_id == plan.campaign.container_id and record.network_id == plan.campaign.network_id)
        _require(record.campaign_id == plan.campaign.campaign_id)
        _require(record.generation == 1 and record.invalidated is False)
        for observation in record.observations:
            _require(type(observation) is tuple and len(observation) == 2)
            _require(all(type(value) is str for value in observation))
        _require(record.observations == PHASE_REQUIREMENTS[phase])
    return OfflineResult(PHASES[:len(evidence)])
