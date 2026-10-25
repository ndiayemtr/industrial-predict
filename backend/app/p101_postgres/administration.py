"""Explicit owner-only administrative entry points; no connection discovery."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from app.anomaly_detection.p101_canonical import instant_datetime, utc_instant
from app.p101_persistence.canonical import canonical_projection
from app.p101_postgres.runtime import (
    CORE_REVISION, REVISION, GuardRejected, SandboxConfig, guard_policy_fingerprint,
    verify_ca, verify_release,
)


class AdminAction(str, Enum):
    CORE = "p101-admin-core-migrate-v1"
    PILOT = "p101-admin-pilot-migrate-v1"
    BOOTSTRAP = "p101-admin-bootstrap-data-v1"


CORE_CHAIN = ("0468ed5be8f1", "50e5051527dc", "656260b06cdf", "572080d9e581",
              "570ce155aaf8", "783e16aa6ce3", "675ebfea0bb5", "d6ec01cf13b6", CORE_REVISION)
OWNER_OPTIONS = "-c search_path=pg_catalog -c timezone=UTC"


def migration_plan_sha256(action):
    if action not in (AdminAction.CORE, AdminAction.PILOT) or type(action) is not AdminAction:
        raise GuardRejected("Unsupported migration action")
    return canonical_projection({"action": action.value,
        "revisions": CORE_CHAIN if action == AdminAction.CORE else (REVISION,),
        "version_schema": "public" if action == AdminAction.CORE else "p101_pilot"}).sha256


@dataclass(frozen=True)
class AdminApproval:
    approval_uuid: str
    action: AdminAction
    plan_sha256: str
    policy_sha256: str
    expires_at: str
    signature: str = field(repr=False)

    def payload(self):
        return canonical_projection({"schema_version": "p101-admin-approval-v1",
            "approval_uuid": self.approval_uuid, "action": self.action.value,
            "plan_sha256": self.plan_sha256, "policy_sha256": self.policy_sha256,
            "expires_at": utc_instant(self.expires_at)}).canonical_json.encode("utf-8")


class AdminApprovalVerifier:
    """Separate administrative trust domain; no issuer or default key."""
    def __init__(self, verification_key: bytes):
        if type(verification_key) is not bytes or len(verification_key) < 32:
            raise GuardRejected("Independent admin verification key required")
        self.__key = verification_key

    def verify(self, approval, config, action, plan_sha256, now):
        try:
            config.validate()
            if (type(approval) is not AdminApproval or type(action) is not AdminAction
                    or str(UUID(approval.approval_uuid)) != approval.approval_uuid
                    or approval.action is not action or approval.plan_sha256 != plan_sha256
                    or len(plan_sha256) != 64 or any(c not in "0123456789abcdef" for c in plan_sha256)
                    or approval.policy_sha256 != guard_policy_fingerprint(config)
                    or now.tzinfo is None or now.utcoffset() is None
                    or instant_datetime(approval.expires_at) <= now.astimezone(timezone.utc)):
                raise GuardRejected("Administrative approval mismatch or expired")
            expected = hmac.new(self.__key, approval.payload(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, approval.signature):
                raise GuardRejected("Administrative approval not authenticated")
            verify_ca(config)
            verify_release(config)
        except GuardRejected:
            raise
        except (ValueError, TypeError, AttributeError, OSError):
            raise GuardRejected("Invalid administrative approval") from None


def authorize(config, approval, verifier, action, plan_digest, now):
    if type(config) is not SandboxConfig or type(verifier) is not AdminApprovalVerifier:
        raise GuardRejected("Typed administrative verifier and policy required")
    verifier.verify(approval, config, action, plan_digest, now)


def validate_owner_transport(connection, config):
    """Inspect the supplied connection only. Never create one or log parameters."""
    try:
        verify_ca(config)
        if any(name.startswith("PG") for name in os.environ):
            raise GuardRejected("Implicit libpq environment forbidden")
        url = connection.engine.url
        driver = connection.connection.driver_connection
        parameters = driver.info.get_parameters()
        if (url.drivername != "postgresql+psycopg" or url.host != config.destination.host
                or url.port != config.destination.port or url.database != config.destination.database
                or url.username != config.owner_role or driver.pgconn.ssl_in_use is not True
                or parameters.get("sslmode") != "verify-full"
                or parameters.get("sslrootcert") != config.tls_root_certificate
                or driver.info.options != OWNER_OPTIONS
                or driver.info.host != config.destination.host or driver.info.port != config.destination.port
                or driver.info.dbname != config.destination.database or driver.info.user != config.owner_role):
            raise GuardRejected("Explicit owner TLS transport rejected")
    except GuardRejected:
        raise
    except Exception:
        raise GuardRejected("Owner transport verification unavailable") from None


OWNER_IDENTITY_SQL = text("""
SELECT current_database() AS database,session_user::text AS session_role,current_user::text AS effective_role,
 inet_server_addr()::text AS address,inet_server_port() AS port,
 (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS ssl,
 current_setting('server_encoding') AS encoding
""")


def validate_owner_identity(config, row):
    expected = dict(database=config.destination.database, session_role=config.owner_role,
        effective_role=config.owner_role, address=config.server_address, port=config.server_port,
        ssl=True, encoding="UTF8")
    if not row or any(row.get(k) != v or type(row.get(k)) is not type(v) for k, v in expected.items()):
        raise GuardRejected("Effective administrative destination rejected")


def check_owner_identity(connection, config):
    validate_owner_identity(config, connection.execute(OWNER_IDENTITY_SQL).mappings().one())


def require_core_revision(connection):
    value = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
    if value != CORE_REVISION:
        raise GuardRejected("General schema revision rejected")


def migration_config(connection, config, approval, verifier, action):
    """Only build an Alembic Config; no import of DEV env or command execution."""
    from alembic.config import Config
    if action not in (AdminAction.CORE, AdminAction.PILOT) or type(action) is not AdminAction:
        raise GuardRejected("Unsupported migration action")
    root = Path(__file__).resolve().parents[2]
    folder = "p101_core_migrations" if action == AdminAction.CORE else "p101_migrations"
    cfg = Config(str(root / folder / "alembic.ini"))
    cfg.attributes.update(p101_connection=connection, p101_config=config,
                          p101_admin_approval=approval, p101_admin_verifier=verifier)
    return cfg


def run_migrations(connection, config, approval, verifier, action):
    """Future authorized operation; caller supplies a fresh owner connection."""
    authorize(config, approval, verifier, action, migration_plan_sha256(action), datetime.now(timezone.utc))
    validate_owner_transport(connection, config)
    if connection.in_transaction():
        raise GuardRejected("Fresh owner connection required")
    from alembic import command
    target = CORE_REVISION if action == AdminAction.CORE else REVISION
    command.upgrade(migration_config(connection, config, approval, verifier, action), target)


def validate_migration_source_config(cfg, action):
    root = Path(__file__).resolve().parents[2]
    folder = root / ("p101_core_migrations" if action == AdminAction.CORE else "p101_migrations")
    try:
        if (Path(cfg.config_file_name).resolve() != folder / "alembic.ini"
                or Path(cfg.get_main_option("script_location")).resolve() != folder):
            raise GuardRejected("Unexpected migration environment")
        versions = cfg.get_main_option("version_locations")
        if action == AdminAction.CORE:
            if Path(versions).resolve() != root / "migrations/versions":
                raise GuardRejected("Unexpected general revision source")
        elif versions is not None:
            raise GuardRejected("Unexpected pilot revision override")
    except (TypeError, ValueError, AttributeError):
        raise GuardRejected("Explicit migration source required") from None


def run_migration_environment(context, action):
    """Called only by the two opt-in Alembic env files, never on module import."""
    if context.is_offline_mode():
        raise GuardRejected("Offline administrative execution forbidden")
    cfg = context.config
    connection, policy = cfg.attributes.get("p101_connection"), cfg.attributes.get("p101_config")
    approval, verifier = cfg.attributes.get("p101_admin_approval"), cfg.attributes.get("p101_admin_verifier")
    digest = migration_plan_sha256(action)
    authorize(policy, approval, verifier, action, digest, datetime.now(timezone.utc))
    validate_migration_source_config(cfg, action)
    if context.get_revision_argument() != (CORE_REVISION if action == AdminAction.CORE else REVISION):
        raise GuardRejected("Only the exact approved upgrade target is permitted")
    validate_owner_transport(connection, policy)
    if connection.in_transaction():
        raise GuardRejected("Migration requires a fresh owner connection")
    with connection.begin():
        check_owner_identity(connection, policy)  # SELECTs before any DDL.
        if action == AdminAction.CORE:
            empty = connection.execute(text("""SELECT NOT EXISTS(SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','p101_pilot')
                AND c.relkind IN ('r','p','v','m','S','f'))""")).scalar_one()
            if empty is not True:
                raise GuardRejected("General bootstrap requires empty dedicated schemas")
            root = Path(__file__).resolve().parents[2]
            actual = {str(p.relative_to(root.parent)).replace('\\', '/') for p in (root / "migrations/versions").glob("*.py")}
            expected = {p for p, _ in policy.release_files if p.startswith("backend/migrations/versions/")}
            if actual != expected:
                raise GuardRejected("Unexpected general migration source")
            connection.execute(text("SET LOCAL search_path=public,pg_catalog"))
        else:
            require_core_revision(connection)
            if connection.execute(text("SELECT to_regnamespace('p101_pilot') IS NULL")).scalar_one() is not True:
                raise GuardRejected("Pilot migration requires a new dedicated schema")
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS p101_pilot"))
        context.configure(connection=connection, target_metadata=None, version_table="alembic_version",
                          version_table_schema="public" if action == AdminAction.CORE else "p101_pilot")
        with context.begin_transaction():
            context.run_migrations()
        authorize(policy, approval, verifier, action, digest, datetime.now(timezone.utc))
