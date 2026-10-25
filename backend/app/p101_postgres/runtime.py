"""Explicit private configuration and independent signed execution approval."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import re
from pathlib import Path
from uuid import UUID

from app.anomaly_detection.p101_canonical import instant_datetime, utc_instant
from app.p101_persistence.canonical import canonical_projection
from app.p101_persistence.contracts import DestinationDeclaration, PreparationDossier
from app.p101_persistence.preparation import validate_destination


REVISION = "p101_0001"
CORE_REVISION = "09ac8101e9fe"
RELEASE_PATHS = tuple(sorted([
    *(f"backend/app/p101_postgres/{name}.py" for name in
      ("__init__", "tables", "runtime", "session", "mapping", "ddl", "guard", "repository", "service",
       "administration", "bootstrap", "catalog")),
    *(f"backend/app/p101_persistence/{name}.py" for name in ("__init__", "contracts", "canonical", "preparation")),
    *(f"backend/app/anomaly_detection/{name}.py" for name in
      ("p101_contracts", "p101_canonical", "p101_core", "statistical_detector")),
    "tests/p101_anomaly/fixtures/p101-temperature-v1.json",
    "backend/p101_migrations/alembic.ini", "backend/p101_migrations/env.py",
    "backend/p101_migrations/versions/p101_0001_registry.py",
    "backend/p101_core_migrations/alembic.ini", "backend/p101_core_migrations/env.py",
    *(f"backend/migrations/versions/{name}.py" for name in (
        "0468ed5be8f1_create_companies_table", "50e5051527dc_create_sites_table",
        "656260b06cdf_create_equipments_table", "572080d9e581_create_sensors_table",
        "570ce155aaf8_create_measurements_table", "783e16aa6ce3_create_maintenance_records_table",
        "675ebfea0bb5_add_equipment_criticality", "d6ec01cf13b6_add_prediction_records",
        "09ac8101e9fe_add_maintenance_recommendations")),
]))


class PersistenceError(ValueError):
    """Sanitized operational error; never embeds a DSN or database exception."""


class GuardRejected(PersistenceError):
    pass


class ContentConflict(PersistenceError):
    pass


@dataclass(frozen=True)
class SandboxConfig:
    destination: DestinationDeclaration
    server_address: str
    server_port: int
    owner_role: str
    reader_role: str
    persistence_revision: str
    tls_root_certificate: str
    password: str = field(repr=False)
    release_files: tuple[tuple[str, str], ...]
    tls_root_sha256: str
    bootstrap_uuid: str

    def validate(self):
        validate_destination(self.destination)
        try:
            valid_bootstrap = str(UUID(self.bootstrap_uuid)) == self.bootstrap_uuid
        except (ValueError, TypeError, AttributeError):
            valid_bootstrap = False
        if (not valid_bootstrap or not isinstance(self.tls_root_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", self.tls_root_sha256) is None
                or self.tls_root_sha256 == "0" * 64):
            raise GuardRejected("Approved CA digest and bootstrap identity required")
        for role in (self.owner_role, self.reader_role):
            if not re.fullmatch(r"p101_[a-z0-9_]{1,48}", role):
                raise GuardRejected("Invalid sandbox role")
        if len({self.owner_role, self.reader_role, self.destination.role}) != 3:
            raise GuardRejected("Roles must be distinct")
        if (not isinstance(self.server_address, str) or not self.server_address
                or type(self.server_port) is not int or not 1 <= self.server_port <= 65535
                or not re.fullmatch(r"[0-9a-f]{40}", self.persistence_revision)
                or self.persistence_revision == "0" * 40
                or not isinstance(self.password, str) or not self.password
                or not isinstance(self.tls_root_certificate, str) or not self.tls_root_certificate):
            raise GuardRejected("Explicit sandbox configuration required")
        if (type(self.release_files) is not tuple or len(self.release_files) != len(RELEASE_PATHS)
                or any(type(row) is not tuple or len(row) != 2
                       for row in self.release_files)):
            raise GuardRejected("Approved release file manifest required")
        if (tuple(row[0] for row in self.release_files) != RELEASE_PATHS
                or any(type(row[1]) is not str or re.fullmatch(r"[0-9a-f]{64}", row[1]) is None
                       for row in self.release_files)):
            raise GuardRejected("Approved release file manifest required")


def dossier_fingerprint(dossier: PreparationDossier) -> str:
    """Bind the exact preparation attempt as well as its deterministic content."""
    return canonical_projection({
        "destination": asdict(dossier.destination), "provenance": asdict(dossier.provenance),
        "authorization": asdict(dossier.authorization),
        "manifest_digest": hashlib.sha256(dossier.manifest_canonical_json.encode()).hexdigest(),
        "targets": [{"identity": t.identity, "key": t.key.projection.sha256,
                     "content": t.content.sha256,
                     "details_digest": hashlib.sha256(t.read_plan.details.candidate_json.encode()).hexdigest()}
                    for t in dossier.targets],
    }).sha256


def guard_policy_fingerprint(config: SandboxConfig) -> str:
    return canonical_projection({"destination": asdict(config.destination),
        "server_address": config.server_address, "server_port": config.server_port,
        "owner_role": config.owner_role, "reader_role": config.reader_role,
        "persistence_revision": config.persistence_revision,
        "tls_root_certificate": config.tls_root_certificate,
        "tls_root_sha256": config.tls_root_sha256, "bootstrap_uuid": config.bootstrap_uuid,
        "core_revision": CORE_REVISION, "p101_revision": REVISION,
        "release_files": config.release_files,
    }).sha256


def verify_ca(config: SandboxConfig) -> None:
    """Verify approved bytes, not X.509 validity or actual server authentication."""
    config.validate()
    try:
        path = Path(config.tls_root_certificate)
        if (not path.is_absolute() or path.resolve() != path or not path.is_file()
                or path.stat().st_size > 65536
                or hashlib.sha256(path.read_bytes()).hexdigest() != config.tls_root_sha256):
            raise GuardRejected("Approved CA content mismatch")
    except OSError:
        raise GuardRejected("Approved CA unavailable") from None


def verify_release(config: SandboxConfig) -> None:
    config.validate()
    root = Path(__file__).resolve().parents[3]
    try:
        for path, digest in config.release_files:
            source = root / path
            if source.resolve() != source or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise GuardRejected("Executable release differs from approved evidence")
    except OSError:
        raise GuardRejected("Approved release unavailable") from None


@dataclass(frozen=True)
class ExecutionApproval:
    approval_uuid: str
    dossier_sha256: str
    persistence_revision: str
    expires_at: str
    guard_policy_sha256: str
    signature: str = field(repr=False)

    def payload(self, destination: DestinationDeclaration) -> bytes:
        return canonical_projection({"scope": "p101-write-pair-v1",
            "approval_uuid": self.approval_uuid, "dossier_sha256": self.dossier_sha256,
            "persistence_revision": self.persistence_revision,
            "guard_policy_sha256": self.guard_policy_sha256,
            "expires_at": utc_instant(self.expires_at), "destination": asdict(destination),
        }).canonical_json.encode("utf-8")


class ApprovalVerifier:
    """Verification only. The independent issuer/key distribution is external.

    A preparation declaration cannot issue an execution approval. No default key,
    environment lookup or signing endpoint is provided.
    """
    def __init__(self, verification_key: bytes):
        if type(verification_key) is not bytes or len(verification_key) < 32:
            raise GuardRejected("Independent verification key required")
        self.__key = verification_key

    def verify(self, approval: ExecutionApproval, dossier: PreparationDossier,
               config: SandboxConfig, now: datetime) -> None:
        try:
            config.validate()
            if (type(approval) is not ExecutionApproval
                    or str(UUID(approval.approval_uuid)) != approval.approval_uuid
                    or now.tzinfo is None or now.utcoffset() is None
                    or instant_datetime(approval.expires_at) <= now.astimezone(timezone.utc)
                    or dossier.destination != config.destination
                    or approval.dossier_sha256 != dossier_fingerprint(dossier)
                    or approval.guard_policy_sha256 != guard_policy_fingerprint(config)
                    or approval.persistence_revision != config.persistence_revision):
                raise GuardRejected("Execution approval mismatch or expired")
            expected = hmac.new(self.__key, approval.payload(config.destination), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, approval.signature):
                raise GuardRejected("Execution approval not authenticated")
            # Verify bytes only after authenticating the independent approval.
            # The issuer must attest the association between these bytes and Git
            # revision; a supplied SHA string alone never establishes that fact.
            verify_ca(config)
            verify_release(config)
        except GuardRejected:
            raise
        except (ValueError, TypeError, AttributeError, OSError, IndexError) as exc:
            raise GuardRejected("Invalid execution approval") from None
