"""Independent SQLAlchemy Core SELECTs and pure adaptation, without ORM/settings."""

from datetime import datetime
import json
import os
import unicodedata

from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, Table, select, text

from app.anomaly_detection.p101_canonical import finite_value, manifest_sha256, utc_instant
from app.anomaly_detection.p101_contracts import ASSET
from app.p101_persistence.contracts import FIXTURE_SHA256
from app.p101_local_demo.contracts import (
    AdaptedMeasurements, ErrorCode, LocalDemoError, LocalDestination, PURPOSE, SqlIdentityMap, SqlRows,
)


metadata = MetaData()
companies = Table("companies", metadata, Column("id", Integer), Column("code", String), schema="public")
sites = Table("sites", metadata, Column("id", Integer), Column("code", String),
              Column("company_id", Integer), schema="public")
equipments = Table("equipments", metadata, Column("id", Integer), Column("code", String),
    Column("site_id", Integer), Column("name", String), Column("equipment_type", String),
    Column("status", String), Column("criticality", String), schema="public")
sensors = Table("sensors", metadata, Column("id", Integer), Column("code", String),
    Column("equipment_id", Integer), Column("sensor_type", String), Column("unit", String),
    Column("status", String), schema="public")
measurements = Table("measurements", metadata, Column("id", Integer), Column("sensor_id", Integer),
    Column("timestamp", DateTime(timezone=True)), Column("value", Float), Column("quality", String), schema="public")

IDENTITY_SQL = text("""
SELECT current_database() AS database,session_user::text AS session_role,current_user::text AS effective_role,
 host(inet_server_addr()) AS server_address,inet_server_port() AS server_port,
 current_setting('transaction_isolation') AS isolation_level,
 current_setting('server_encoding') AS encoding,
 m.instance_uuid::text,m.purpose,m.database_name::text,m.bootstrap_closed,m.schema_revision,
 (SELECT version_num FROM public.alembic_version) AS installed_revision,
 to_regnamespace('p101_pilot') IS NULL AS no_protected_schema,
 NOT(r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls) AS limited_role,
 NOT EXISTS(SELECT 1 FROM pg_auth_members a WHERE a.member=r.oid) AS no_memberships,
 NOT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname IN ('public','local_demo') AND c.relowner=r.oid) AS not_owner,
 (SELECT bool_and(has_table_privilege(current_user,'public.'||t,'SELECT'))
  FROM unnest(ARRAY['companies','sites','equipments','sensors','measurements']) t) AS source_read,
 (SELECT bool_and(NOT has_table_privilege(current_user,'public.'||t,p)
                   AND CASE WHEN p IN ('INSERT','UPDATE','REFERENCES')
                       THEN NOT has_any_column_privilege(current_user,'public.'||t,p) ELSE true END)
  FROM unnest(ARRAY['companies','sites','equipments','sensors','measurements']) t
  CROSS JOIN unnest(ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p) AS sources_immutable
FROM pg_roles r CROSS JOIN local_demo.environment m WHERE r.rolname=current_user AND m.singleton
""")


def sql_id(value):
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise LocalDemoError(ErrorCode.SNAPSHOT)
    return value


def instant(value):
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise LocalDemoError(ErrorCode.SNAPSHOT)
        value = value.isoformat()
    return utc_instant(value)


def validate_transport(connection, config):
    """Never opens a connection. Reject wrong supplied transports before any SELECT."""
    try:
        if type(config) is not LocalDestination:
            raise LocalDemoError(ErrorCode.DESTINATION)
        config.validate()
        if any(k.startswith("PG") for k in os.environ):
            raise LocalDemoError(ErrorCode.DESTINATION)
        url = connection.engine.url
        driver = connection.connection.driver_connection
        if (url.drivername != "postgresql+psycopg" or url.host != config.host or url.port != config.port
                or url.database != config.database or url.username != config.role
                or driver.info.host != config.host or driver.info.port != config.port
                or driver.info.dbname != config.database or driver.info.user != config.role
                or driver.info.get_parameters().get("sslmode") != "disable"
                or driver.pgconn.ssl_in_use is not False or not connection.in_transaction()):
            raise LocalDemoError(ErrorCode.DESTINATION)
    except LocalDemoError:
        raise
    except Exception:
        raise LocalDemoError(ErrorCode.DESTINATION) from None


def validate_identity(config, row):
    config.validate()
    expected = dict(database=config.database, session_role=config.role, effective_role=config.role,
        server_address=config.server_address, server_port=config.server_port,
        instance_uuid=config.instance_uuid, purpose=PURPOSE, database_name=config.database,
        bootstrap_closed=True, schema_revision=config.schema_revision, installed_revision=config.schema_revision,
        isolation_level="read committed", encoding="UTF8", no_protected_schema=True,
        limited_role=True, no_memberships=True, not_owner=True, source_read=True, sources_immutable=True)
    if not row or any(row.get(k) != v or type(row.get(k)) is not type(v) for k, v in expected.items()):
        raise LocalDemoError(ErrorCode.DESTINATION)


def _parent(rows, kind):
    if type(rows) is not tuple or len(rows) != 1:
        raise LocalDemoError(ErrorCode.SNAPSHOT)
    row = dict(rows[0])
    sql_id(row["id"])
    if row["code"] != ASSET[kind + "_code"]:
        raise LocalDemoError(ErrorCode.SNAPSHOT)
    return row


def _parents(rows):
    c, s, e, n = (_parent(value, kind) for value, kind in zip(
        (rows.companies, rows.sites, rows.equipments, rows.sensors), ("company", "site", "equipment", "sensor")))
    if (sql_id(s["company_id"]) != c["id"] or sql_id(e["site_id"]) != s["id"]
            or sql_id(n["equipment_id"]) != e["id"] or e["equipment_type"] != "pump"
            or e["status"] != "operational" or e["criticality"] != "medium"
            or "synthétique" not in unicodedata.normalize("NFC", e["name"]).lower()
            or n["sensor_type"] != "temperature" or n["unit"] != "°C" or n["status"] != "active"):
        raise LocalDemoError(ErrorCode.SNAPSHOT)
    return c, s, e, n


def read_rows(connection, config):
    """Future read on an already supplied transaction; only SELECTs, no commit."""
    validate_transport(connection, config)
    try:
        validate_identity(config, connection.execute(IDENTITY_SQL).mappings().one())
        parents = []
        for table, kind in ((companies, "company"), (sites, "site"), (equipments, "equipment"), (sensors, "sensor")):
            found = tuple(dict(r) for r in connection.execute(select(table).where(
                table.c.code == ASSET[kind + "_code"]).limit(2)).mappings())
            _parent(found, kind)
            parents.append(found)
        empty = SqlRows(*parents, ())
        _, _, _, sensor = _parents(empty)
        # Read one excess row to reject extra data without unbounded transfer.
        data = tuple(dict(r) for r in connection.execute(select(measurements).where(
            measurements.c.sensor_id == sensor["id"]).order_by(
            measurements.c.timestamp, measurements.c.id).limit(13)).mappings())
        return SqlRows(*parents, data)
    except LocalDemoError:
        raise
    except Exception:
        raise LocalDemoError(ErrorCode.SNAPSHOT) from None


def validate_fixture(reference):
    try:
        if (manifest_sha256(reference) != FIXTURE_SHA256 or len(reference["observations"]) != 12
                or {r["fixture_id"] for r in reference["observations"]} != {f"DEMO-M-{i:03d}" for i in range(1, 13)}):
            raise LocalDemoError(ErrorCode.FIXTURE)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise LocalDemoError(ErrorCode.FIXTURE) from None


def adapt_rows(rows, reference):
    """Use SQL values; the pinned JSON supplies only missing synthetic metadata."""
    validate_fixture(reference)
    try:
        if type(rows) is not SqlRows or type(rows.measurements) is not tuple or len(rows.measurements) != 12:
            raise LocalDemoError(ErrorCode.SNAPSHOT)
        c, s, e, n = _parents(rows)
        by_time = {instant(r["timestamp"]): r for r in reference["observations"]}
        observations, mapping, ids, times = [], [], set(), set()
        for raw in rows.measurements:
            row = dict(raw)
            identity, timestamp = sql_id(row["id"]), instant(row["timestamp"])
            if (identity in ids or timestamp in times or timestamp not in by_time
                    or sql_id(row["sensor_id"]) != n["id"] or not finite_value(row["value"])
                    or row["quality"] != "good"):
                raise LocalDemoError(ErrorCode.SNAPSHOT)
            fixture = by_time[timestamp]
            # Never use fixture['value'] as the calculated temperature.
            observations.append(dict(fixture_id=fixture["fixture_id"], timestamp=timestamp,
                available_at=instant(fixture["available_at"]), asset=dict(ASSET), synthetic=True,
                unit=n["unit"], quality=row["quality"], value=row["value"]))
            mapping.append((fixture["fixture_id"], identity))
            ids.add(identity)
            times.add(timestamp)
        if times != set(by_time):
            raise LocalDemoError(ErrorCode.SNAPSHOT)
        observations.sort(key=lambda r: r["timestamp"])
        manifest = dict(schema_version=reference["schema_version"], dataset_id=reference["dataset_id"],
                        synthetic=True, asset=dict(ASSET), observations=observations)
        if manifest_sha256(manifest) != FIXTURE_SHA256:
            raise LocalDemoError(ErrorCode.FIXTURE)
        return AdaptedMeasurements(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False), SqlIdentityMap(c["id"], s["id"], e["id"], n["id"], tuple(sorted(mapping))))
    except LocalDemoError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise LocalDemoError(ErrorCode.SNAPSHOT) from None
