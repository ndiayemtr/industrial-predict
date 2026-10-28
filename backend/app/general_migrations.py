"""Offline general-migration declarations and guards; never an SQL executor.

Declarations are NOT authenticated approvals. P101 trust domains are not reused.
No general authority is configured, so every execution request is denied, even
after a successful preflight. The only allowlisted label is a synthetic test
environment; it does not register or authorize an actual database.

Source fingerprints use UTF-8/LF bytes (CRLF normalized), independent of checkout
line endings. Reading metadata uses AST, never imports revision modules. Hashes
pin the nine historical sources; future sources and this boundary are included
in each declaration's exact snapshot, without claiming authentication or TOCTOU
protection. A trusted immutable release will be required before execution.
Physical Alembic revision loading is unavailable, including after preflight.
"""

import ast
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
import hashlib
from ipaddress import ip_address
from pathlib import Path
import re
from uuid import UUID


BACKEND = Path(__file__).resolve().parents[1]
HISTORICAL_DIRECTORY = BACKEND / "migrations/versions"
GENERAL_DIRECTORY = BACKEND / "general_migrations"
HISTORICAL_HEAD = "09ac8101e9fe"
HISTORICAL_CHAIN = (
    "0468ed5be8f1", "50e5051527dc", "656260b06cdf", "572080d9e581",
    "570ce155aaf8", "783e16aa6ce3", "675ebfea0bb5", "d6ec01cf13b6", HISTORICAL_HEAD,
)
HISTORICAL_SOURCES = (
    ("0468ed5be8f1_create_companies_table.py", "e5e562511a7e83d4d984f51a58ced52c827521618e77a5f2ac101fddf8894bba"),
    ("09ac8101e9fe_add_maintenance_recommendations.py", "11e4b0d62de251d00d1ee1829ff031b8492d43a49ca8d9d931cb1fe0489488ef"),
    ("50e5051527dc_create_sites_table.py", "24c8234a5e8ce9aae6dbd3b8fcfa1b58539eb19874d36518dfdd544a73b63b66"),
    ("570ce155aaf8_create_measurements_table.py", "bc9262c2685575835ad372d4c82e174d9327a065b728675b2ba72e798968d44c"),
    ("572080d9e581_create_sensors_table.py", "a623ae93139cd1f88deb299b20aa9e69d1fe99428a37e03fd90fd7dfbf9d81ca"),
    ("656260b06cdf_create_equipments_table.py", "636729273bc38cf8571eb6c9fd2945d9d1c7c572a4ada82432fa0e2e30c41269"),
    ("675ebfea0bb5_add_equipment_criticality.py", "3d7e21e45645c53ece6fac7355209d2a011cba7c58f18599b1a3c22bd1a1d041"),
    ("783e16aa6ce3_create_maintenance_records_table.py", "780c871579b9cc7a0b91dc4f7836ac17e64d984db20dd6647cc9a09249c4aef9"),
    ("d6ec01cf13b6_add_prediction_records.py", "1fbda40b9aa8a1997ecb29fd6859a3c64785781c5163128940612bd5f15b4f99"),
)
ALLOWED_ENVIRONMENTS = frozenset({"oidc-migration-test"})
SCHEMA_SCOPE = ("public.oidc_transactions",)


class MigrationGuardError(ValueError):
    CODE = "GENERAL_MIGRATION_REJECTED"

    def __init__(self):
        super().__init__(self.CODE)


class MigrationExecutionDisabled(MigrationGuardError):
    CODE = "GENERAL_MIGRATION_EXECUTION_DISABLED"


def _guarded(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            pass
        # Never retain sensitive validation/file/Alembic exception context.
        raise MigrationGuardError()
    return checked


def _require(condition):
    if not condition:
        raise ValueError()


@dataclass(frozen=True, slots=True, repr=False)
class TransportExpectation:
    sslmode: str
    ca_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class DestinationExpectation:
    environment_id: str
    instance_id: str
    host: str
    port: int
    database: str
    role: str
    server_address: str
    server_port: int
    transport: TransportExpectation


@dataclass(frozen=True, slots=True)
class RevisionDescription:
    revision: str
    parent: str | None
    path: str  # backend-relative POSIX path, never an import instruction


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    revisions: tuple[RevisionDescription, ...]
    sources: tuple[SourceFingerprint, ...]


@dataclass(frozen=True, slots=True, repr=False)
class MigrationIntent:
    destination: DestinationExpectation
    direction: str
    initial_revision: str
    final_revision: str
    sequence: tuple[str, ...]
    sources: tuple[SourceFingerprint, ...]
    schema_scope: tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class ApprovalDeclaration:
    """Untrusted assertion of approval; no signature or trusted issuer implied."""

    approval_id: str
    authority_id: str
    intent: MigrationIntent
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PreflightReport:
    declaration_matches: bool
    sources_match: bool
    authenticated: bool
    execution_enabled: bool


def _revision_id(value):
    return type(value) is str and re.fullmatch(r"[a-z0-9_]{1,32}", value) and value not in {"head", "heads", "base"}


def _read(path):
    _require(path.resolve() == path and path.is_file() and path.stat().st_size <= 1_048_576)
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _fingerprint(path, source):
    return SourceFingerprint(path.relative_to(BACKEND).as_posix(), hashlib.sha256(source.encode("utf-8")).hexdigest())


def _parse_revision(path, source):
    values = {}
    for node in ast.parse(source).body:
        target = node.target if isinstance(node, ast.AnnAssign) else (
            node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else None)
        if isinstance(target, ast.Name) and target.id in {"revision", "down_revision", "branch_labels", "depends_on"}:
            _require(target.id not in values)
            values[target.id] = ast.literal_eval(node.value)
    _require(set(values) == {"revision", "down_revision", "branch_labels", "depends_on"})
    _require(_revision_id(values["revision"]))
    _require(values["down_revision"] is None or _revision_id(values["down_revision"]))
    _require(values["branch_labels"] is None and values["depends_on"] is None)
    return RevisionDescription(values["revision"], values["down_revision"], path.relative_to(BACKEND).as_posix())


@_guarded
def resolve_upgrade(revisions: tuple[RevisionDescription, ...], initial: str, final: str) -> tuple[str, ...]:
    """Pure graph resolution, not approval; synthetic future nodes are supported."""
    _require(type(revisions) is tuple and all(type(r) is RevisionDescription for r in revisions))
    _require(initial == HISTORICAL_HEAD and _revision_id(final))  # No business bootstrap/downgrade.
    nodes = {r.revision: r for r in revisions}
    _require(len(nodes) == len(revisions) and initial in nodes and final in nodes)
    _require(all(_revision_id(r.revision) and (r.parent is None or r.parent in nodes) for r in revisions))
    _require([r.revision for r in revisions if r.parent is None] == [HISTORICAL_CHAIN[0]])
    parents = {r.parent for r in revisions}
    heads = set(nodes) - parents
    _require(len(heads) == 1)
    chain = []
    current = next(iter(heads))
    while current is not None:
        _require(current not in chain)
        chain.append(current)
        current = nodes[current].parent
    chain.reverse()
    _require(len(chain) == len(nodes) and tuple(chain[:9]) == HISTORICAL_CHAIN)
    _require(chain.index(final) >= chain.index(initial))
    return tuple(chain[chain.index(initial) + 1:chain.index(final) + 1])


@_guarded
def inspect_sources() -> SourceSnapshot:
    """Explicit filesystem read only; no revision import, SQL or Alembic command."""
    # No authority can authenticate a new physical revision in this lot. Refuse
    # it before reading/parsing it; future dependency tests use metadata in memory.
    _require(not tuple((GENERAL_DIRECTORY / "versions").glob("*.py")))
    _require({p.name for p in HISTORICAL_DIRECTORY.glob("*.py")} == {name for name, _ in HISTORICAL_SOURCES})
    revisions, fingerprints = [], []
    for name, expected in HISTORICAL_SOURCES:
        path = HISTORICAL_DIRECTORY / name
        source = _read(path)
        fingerprint = _fingerprint(path, source)
        _require(fingerprint.sha256 == expected)
        fingerprints.append(fingerprint)
        revisions.append(_parse_revision(path, source))
    for path in (GENERAL_DIRECTORY / "alembic.ini", GENERAL_DIRECTORY / "env.py", Path(__file__).resolve()):
        fingerprints.append(_fingerprint(path, _read(path)))
    graph = tuple(sorted(revisions, key=lambda r: r.revision))
    resolve_upgrade(graph, HISTORICAL_HEAD, HISTORICAL_HEAD)
    return SourceSnapshot(graph, tuple(sorted(fingerprints, key=lambda s: s.path)))


def _valid_host(host):
    # ASCII DNS without a trailing root dot; literal IPv4 or unbracketed IPv6.
    # Scoped IPv6 and ambiguous numeric DNS spellings are outside this profile.
    if type(host) is not str or not host.isascii() or not 0 < len(host) <= 253 or "%" in host:
        return False
    try:
        ip_address(host)
        return True
    except ValueError:
        pass
    if re.fullmatch(r"[0-9.]+", host):
        return False
    return all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
               for label in host.split("."))


def _validate_destination(destination):
    _require(type(destination) is DestinationExpectation)
    _require(destination.environment_id in ALLOWED_ENVIRONMENTS)
    _require(str(UUID(destination.instance_id)) == destination.instance_id)
    _require(_valid_host(destination.host))
    _require(all(type(p) is int and 1 <= p <= 65535 for p in (destination.port, destination.server_port)))
    ip_address(destination.server_address)
    for value in (destination.database, destination.role):
        _require(type(value) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value))
        _require(not value.startswith("p101_") and "p101" not in value)
    _require(destination.database not in {"industrial_predict", "industrial_predict_ml_sandbox"})
    transport = destination.transport
    _require(type(transport) is TransportExpectation and transport.sslmode == "verify-full")
    _require(type(transport.ca_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", transport.ca_sha256)
             and transport.ca_sha256 != "0" * 64)


@_guarded
def preflight(intent: MigrationIntent, approval: ApprovalDeclaration, *, now: datetime) -> PreflightReport:
    """Check an untrusted claim against current sources; NEVER authenticate it.

With no future revision, only the empty reference-to-reference sequence can be
described. This is a preparatory no-op declaration, not a migratable bootstrap.
"""
    _require(type(intent) is MigrationIntent and type(approval) is ApprovalDeclaration)
    _validate_destination(intent.destination)
    _require(intent.direction == "upgrade" and type(intent.sequence) is tuple)
    _require(intent.schema_scope == SCHEMA_SCOPE and type(intent.schema_scope) is tuple)
    snapshot = inspect_sources()
    _require(intent.sources == snapshot.sources and type(intent.sources) is tuple)
    _require(intent.sequence == resolve_upgrade(snapshot.revisions, intent.initial_revision, intent.final_revision))
    _require(str(UUID(approval.approval_id)) == approval.approval_id)
    _require(type(approval.authority_id) is str and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", approval.authority_id))
    _require(type(approval.intent) is MigrationIntent and approval.intent == intent)
    _require(all(type(t) is datetime and t.tzinfo is not None and t.utcoffset() == timedelta(0)
                 for t in (now, approval.expires_at)))
    _require(now < approval.expires_at)
    return PreflightReport(True, True, False, False)


def request_execution(intent, approval, *, now, connection=None):
    """No authority/enable switch/callback exists. Never inspect the connection."""
    preflight(intent, approval, now=now)
    raise MigrationExecutionDisabled()


@_guarded
def make_alembic_config():
    """Verify sources first, then return an INERT configuration, never a loader.

    Returning real revision locations would allow later source changes to be
    imported by Alembic without another check. Until immutable approved loading
    is available, ScriptDirectory/commands must fail even for this config.
    Use inspect_sources()/resolve_upgrade() for non-importing graph inspection.
    """
    inspect_sources()
    from alembic.config import Config

    config = Config(str(GENERAL_DIRECTORY / "alembic.ini"))
    # No operational paths, alternate loaders or runtime options may escape.
    _require(set(config.get_section(config.config_ini_section)) <= {"here", "path_separator"})
    _require(config.get_main_option("path_separator") == "newline")
    return config
