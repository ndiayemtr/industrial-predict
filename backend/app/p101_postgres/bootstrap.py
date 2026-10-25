"""Reproducible synthetic bootstrap plans and opt-in owner execution, never automatic."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re

from sqlalchemy import text

from app.anomaly_detection.p101_canonical import instant_datetime, manifest_sha256, utc_instant
from app.anomaly_detection.p101_contracts import ASSET
from app.p101_persistence.canonical import canonical_projection
from app.p101_persistence.contracts import FIXTURE_SHA256
from app.p101_postgres.administration import (
    AdminAction, authorize, check_owner_identity, require_core_revision, validate_owner_transport,
)
from app.p101_postgres.mapping import sql_id
from app.p101_postgres.guard import check_installation
from app.p101_postgres.runtime import CORE_REVISION, REVISION, GuardRejected


SOURCE_TABLES = ("companies", "sites", "equipments", "sensors", "measurements")
BUSINESS_TABLES = SOURCE_TABLES + ("prediction_records", "maintenance_records", "maintenance_recommendations")


@dataclass(frozen=True)
class BootstrapPlan:
    canonical_json: str
    sha256: str


def role_creation_plan(config):
    """Bootstrap-admin phase, before owner login. No password or implicit execution.

    Fresh roles only: an already existing role is an error, never adopted.
    Owner must separately become database owner and receive a private LOGIN secret
    under a future resource/credential authorization, before owner migrations.
    """
    config.validate()
    return tuple(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                 'NOREPLICATION NOBYPASSRLS NOINHERIT'
                 for role in (config.owner_role, config.destination.role, config.reader_role))


def privilege_plan(config, sequence):
    """Post-migration plan; identifier comes from pg_get_serial_sequence, not a guess."""
    config.validate()
    if type(sequence) is not str or re.fullmatch(r"public\.[a-z0-9_]+", sequence) is None:
        raise GuardRejected("Unexpected prediction sequence")
    writer, reader, owner = (f'"{r}"' for r in (config.destination.role, config.reader_role, config.owner_role))
    database = config.destination.database  # fixed by the offline contract
    sources = ",".join("public." + t for t in SOURCE_TABLES)
    return (
        f'REVOKE ALL ON DATABASE "{database}" FROM PUBLIC,{writer},{reader}',
        f'GRANT CONNECT ON DATABASE "{database}" TO {writer},{reader}',
        f'REVOKE ALL ON SCHEMA public,p101_pilot FROM PUBLIC,{writer},{reader}',
        f'GRANT USAGE ON SCHEMA public,p101_pilot TO {writer},{reader}',
        f'REVOKE ALL ON ALL TABLES IN SCHEMA public,p101_pilot FROM PUBLIC,{writer},{reader}',
        f'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC,{writer},{reader}',
        f'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA p101_pilot FROM PUBLIC,{writer},{reader}',
        f'ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public,p101_pilot REVOKE ALL ON TABLES FROM PUBLIC',
        f'ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public,p101_pilot REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC',
        f'GRANT SELECT ON {sources},public.prediction_records TO {writer},{reader}',
        f'GRANT SELECT ON public.alembic_version,p101_pilot.alembic_version,p101_pilot.environment_guard,'
        f'p101_pilot.idempotency_records TO {writer}',
        f'GRANT INSERT ON public.prediction_records,p101_pilot.idempotency_records TO {writer}',
        f'GRANT USAGE ON SEQUENCE {sequence} TO {writer}',
        f'GRANT EXECUTE ON FUNCTION p101_pilot.lock_sources() TO {writer}',
    )


def build_bootstrap_plan(config, manifest, prepared_at):
    """Only the pinned 12-observation fixture is accepted; never compute ML here."""
    config.validate()
    try:
        if manifest_sha256(manifest) != FIXTURE_SHA256 or len(manifest["observations"]) != 12:
            raise GuardRejected("Pinned synthetic fixture required")
        if tuple(row["fixture_id"] for row in manifest["observations"]) != tuple(f"DEMO-M-{i:03d}" for i in range(1, 13)):
            raise GuardRejected("Ordered complete synthetic fixture required")
        stamp = utc_instant(prepared_at)
        if instant_datetime(stamp) < max(instant_datetime(r["available_at"]) for r in manifest["observations"]):
            raise GuardRejected("Bootstrap time precedes synthetic availability")
        payload = {"schema_version": "p101-bootstrap-v1", "bootstrap_uuid": config.bootstrap_uuid,
            "instance_uuid": config.destination.instance_uuid, "prepared_at": stamp,
            "fixture_sha256": FIXTURE_SHA256, "manifest": manifest, "asset": dict(ASSET),
            "owner_role": config.owner_role, "writer_role": config.destination.role, "reader_role": config.reader_role,
            "core_revision": CORE_REVISION, "p101_revision": REVISION,
            "parents": [
                {"table": "companies", "name": "Entreprise P101 synthétique", "code": ASSET["company_code"]},
                {"table": "sites", "name": "Site P101 synthétique", "code": ASSET["site_code"]},
                {"table": "equipments", "name": "Pompe P101 — démonstration synthétique", "code": ASSET["equipment_code"],
                 "equipment_type": "pump", "criticality": "medium", "status": "active"},
                {"table": "sensors", "name": "Température P101 synthétique", "code": ASSET["sensor_code"],
                 "sensor_type": "temperature", "unit": "°C", "status": "active"}],
            "role_creation": role_creation_plan(config)}
        projection = canonical_projection(payload)
        return BootstrapPlan(projection.canonical_json, projection.sha256)
    except GuardRejected:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise GuardRejected("Invalid synthetic bootstrap plan") from None


def validate_bootstrap_plan(config, plan):
    if type(plan) is not BootstrapPlan:
        raise GuardRejected("Typed synthetic plan required")
    try:
        data = json.loads(plan.canonical_json)
        # Canonical numeric values are strings; reconstruct only the fixture values.
        manifest = data["manifest"]
        for row in manifest["observations"]:
            row["value"] = float(row["value"])
        if build_bootstrap_plan(config, manifest, data["prepared_at"]) != plan:
            raise GuardRejected("Synthetic bootstrap content mismatch")
        return data
    except GuardRejected:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise GuardRejected("Invalid synthetic bootstrap plan") from None


def bootstrap_data(connection, config, plan, approval, verifier):
    """Future operation, never called by B-2.1 tests. One owner transaction.

    No automatic retry, role creation, credentials or migration. A commit exception
    must be treated as uncertain and independently inspected before any retry.
    """
    data = validate_bootstrap_plan(config, plan)
    authorize(config, approval, verifier, AdminAction.BOOTSTRAP, plan.sha256, datetime.now(timezone.utc))
    validate_owner_transport(connection, config)
    if connection.in_transaction():
        raise GuardRejected("Fresh owner connection required for bootstrap")
    with connection.begin():
        check_owner_identity(connection, config)
        require_core_revision(connection)
        if connection.execute(text("SELECT version_num FROM p101_pilot.alembic_version")).scalar_one() != REVISION:
            raise GuardRejected("Pilot schema revision rejected")
        check_installation(connection, config, owner_session=True)
        connection.execute(text("SELECT pg_advisory_xact_lock(1010042)"))
        for table in tuple("public." + t for t in BUSINESS_TABLES) + (
                "p101_pilot.idempotency_records", "p101_pilot.environment_guard"):
            if connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() != 0:
                raise GuardRejected("Bootstrap requires empty dedicated tables; no adoption or cleanup")
        # UTC-only parent columns are historically timestamp without time zone.
        parent_time = instant_datetime(data["prepared_at"]).replace(tzinfo=None)
        allocated = []
        for i, parent in enumerate(data["parents"]):
            values = dict(parent)
            table = values.pop("table")
            values.update(created_at=parent_time, updated_at=parent_time)
            if i:
                values[("", "company_id", "site_id", "equipment_id")[i]] = allocated[-1]
            columns = ",".join(values)
            parameters = ",".join(":" + key for key in values)
            allocated.append(sql_id(connection.execute(text(
                f"INSERT INTO public.{table} ({columns}) VALUES ({parameters}) RETURNING id"), values).scalar_one()))
        sensor_id = allocated[-1]
        for observation in data["manifest"]["observations"]:
            sql_id(connection.execute(text("""INSERT INTO public.measurements(sensor_id,timestamp,value,quality)
                VALUES (:sensor_id,:timestamp,:value,:quality) RETURNING id"""),
                {"sensor_id": sensor_id, "timestamp": instant_datetime(observation["timestamp"]),
                 "value": float(observation["value"]), "quality": observation["quality"]}).scalar_one())
        marker = dict(instance_uuid=config.destination.instance_uuid, bootstrap_uuid=config.bootstrap_uuid,
            database_name=config.destination.database, purpose=config.destination.purpose,
            owner_role=config.owner_role, writer_role=config.destination.role, reader_role=config.reader_role,
            core_revision=CORE_REVISION, p101_revision=REVISION)
        connection.execute(text("""INSERT INTO p101_pilot.environment_guard(singleton,instance_uuid,bootstrap_uuid,
            database_name,purpose,owner_role,writer_role,reader_role,core_revision,p101_revision,provisioning_closed)
            VALUES (true,:instance_uuid,:bootstrap_uuid,:database_name,:purpose,:owner_role,:writer_role,
                    :reader_role,:core_revision,:p101_revision,false)"""), marker)
        sequence = connection.execute(text("SELECT pg_get_serial_sequence('public.prediction_records','id')")).scalar_one()
        for statement in privilege_plan(config, sequence):
            connection.execute(text(statement))
        updated = connection.execute(text("""UPDATE p101_pilot.environment_guard SET provisioning_closed=true
            WHERE singleton AND bootstrap_uuid=:bootstrap_uuid AND NOT provisioning_closed"""),
            {"bootstrap_uuid": config.bootstrap_uuid})
        if updated.rowcount != 1:
            raise GuardRejected("Provisioning closure rejected")
        authorize(config, approval, verifier, AdminAction.BOOTSTRAP, plan.sha256, datetime.now(timezone.utc))
    return config.bootstrap_uuid
