"""Fail-closed catalog/identity checks, called inside every operational transaction."""

import hashlib
from sqlalchemy import text

from app.p101_postgres.ddl import FUNCTIONS
from app.p101_postgres.runtime import CORE_REVISION, REVISION, GuardRejected


IDENTITY_SQL = text("""
SELECT inet_server_addr()::text AS server_address, inet_server_port() AS server_port,
 current_database() AS database, session_user::text AS session_role, current_user::text AS effective_role,
 m.instance_uuid::text, m.purpose, m.owner_role::text, m.writer_role::text, m.reader_role::text,
 m.provisioning_closed, m.core_revision, m.p101_revision,
 (SELECT version_num FROM public.alembic_version) AS core_installed,
 (SELECT version_num FROM p101_pilot.alembic_version) AS p101_installed,
 current_setting('transaction_isolation') AS isolation_level,
 (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS ssl,
 NOT(r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication) AS limited_role,
 NOT EXISTS(SELECT 1 FROM pg_auth_members a WHERE a.member=r.oid) AS no_memberships,
 NOT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname IN ('public','p101_pilot') AND c.relowner=r.oid) AS not_owner,
 NOT has_schema_privilege(current_user,'public','CREATE')
   AND NOT has_schema_privilege(current_user,'p101_pilot','CREATE') AS no_ddl,
 NOT has_database_privilege(current_user,current_database(),'TEMP') AS no_temp,
 (SELECT bool_and(has_table_privilege(current_user,'public.'||t,'SELECT'))
  FROM unnest(ARRAY['companies','sites','equipments','sensors','measurements']) t) AS source_read,
 (SELECT bool_and(NOT has_table_privilege(current_user,'public.'||t,p))
  FROM unnest(ARRAY['companies','sites','equipments','sensors','measurements',
                   'maintenance_records','maintenance_recommendations']) t
  CROSS JOIN unnest(ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p) AS sources_immutable,
 (SELECT bool_and(has_table_privilege(current_user,t,'SELECT') AND has_table_privilege(current_user,t,'INSERT'))
  FROM unnest(ARRAY['public.prediction_records','p101_pilot.idempotency_records']) t) AS write_grants,
 (SELECT bool_and(NOT has_table_privilege(current_user,t,p))
  FROM unnest(ARRAY['public.prediction_records','p101_pilot.idempotency_records','p101_pilot.environment_guard']) t
  CROSS JOIN unnest(ARRAY['UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p) AS history_immutable,
 NOT has_table_privilege(current_user,'p101_pilot.environment_guard','INSERT') AS marker_immutable,
 (SELECT bool_and(NOT has_any_column_privilege(current_user,'public.'||t,p))
  FROM unnest(ARRAY['companies','sites','equipments','sensors','measurements',
                   'maintenance_records','maintenance_recommendations']) t
  CROSS JOIN unnest(ARRAY['INSERT','UPDATE','REFERENCES']) p)
  AND NOT has_any_column_privilege(current_user,'public.prediction_records','UPDATE')
  AND NOT has_any_column_privilege(current_user,'p101_pilot.idempotency_records','UPDATE')
  AND NOT has_any_column_privilege(current_user,'p101_pilot.environment_guard','INSERT')
  AND NOT has_any_column_privilege(current_user,'p101_pilot.environment_guard','UPDATE') AS no_column_writes,
 has_sequence_privilege(current_user,pg_get_serial_sequence('public.prediction_records','id'),'USAGE') AS sequence_usage,
 (SELECT pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='p101_pilot' AND c.relname='environment_guard') AS marker_owner
FROM pg_roles r CROSS JOIN p101_pilot.environment_guard m
WHERE r.rolname=current_user AND m.singleton
""")

FUNCTION_SQL = text("""
SELECT p.proname, pg_get_userbyid(p.proowner) AS owner, p.prosecdef, p.proconfig,
 encode(sha256(convert_to(p.prosrc,'UTF8')),'hex') AS body_sha256,
 has_function_privilege(current_user,p.oid,'EXECUTE') AS executable,
 EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
        WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_execute
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='p101_pilot'
""")

CONSTRAINT_SQL = text("""
SELECT c.conname,c.contype,c.condeferrable,c.condeferred,c.convalidated,
 c.conrelid='p101_pilot.idempotency_records'::regclass AS registry_table,
 CASE WHEN c.contype='f' THEN c.confrelid='public.prediction_records'::regclass AND c.confdeltype='a'
 ELSE true END AS reference_target
FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
WHERE n.nspname='p101_pilot' AND c.conname IN
('p101_registry_pk','p101_prediction_unique','p101_prediction_fk','p101_key_hex',
 'p101_content_hex','p101_key_size','p101_content_size')
""")

TRIGGER_SQL = text("""
SELECT t.tgname,t.tgenabled,coalesce(c.condeferrable,false) AS deferred_capable,
 coalesce(c.condeferred,false) AS initially_deferred,n.nspname AS table_schema,r.relname AS table_name,
 p.proname AS function_name,pn.nspname AS function_schema
FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace
JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace
LEFT JOIN pg_constraint c ON c.oid=t.tgconstraint
WHERE (n.nspname,r.relname) IN (('public','prediction_records'),('p101_pilot','idempotency_records'))
 AND t.tgname IN ('p101_shape','p101_prediction_link','p101_registry_link')
""")

REQUIRED_TRUE = ("provisioning_closed", "ssl", "limited_role", "no_memberships", "not_owner",
                 "no_ddl", "no_temp", "source_read", "sources_immutable", "write_grants",
                 "history_immutable", "marker_immutable", "sequence_usage", "no_column_writes")


def validate_identity(config, row):
    config.validate()
    d = config.destination
    expected = dict(server_address=config.server_address, server_port=config.server_port,
        database=d.database, session_role=d.role, effective_role=d.role,
        instance_uuid=d.instance_uuid, purpose="p101-ml-sandbox", owner_role=config.owner_role,
        writer_role=d.role, reader_role=config.reader_role, core_revision=CORE_REVISION,
        p101_revision=REVISION, core_installed=CORE_REVISION, p101_installed=REVISION,
        isolation_level="read committed", marker_owner=config.owner_role)
    if (not row or any(row.get(key) != value for key, value in expected.items())
            or any(row.get(key) is not True for key in REQUIRED_TRUE)):
        raise GuardRejected("Effective sandbox identity or privileges rejected")


def check_destination(session, config):
    """Only SELECT statements. Any missing catalog fact or exception rejects."""
    try:
        row = session.execute(IDENTITY_SQL).mappings().one()
        validate_identity(config, row)
        functions = list(session.execute(FUNCTION_SQL).mappings())
        if len(functions) != len(FUNCTIONS):
            raise GuardRejected("Sandbox functions missing or overloaded")
        for function in functions:
            name = function["proname"]
            if (name not in FUNCTIONS or function["owner"] != config.owner_role
                    or function["prosecdef"] is not True
                    or function["proconfig"] != ["search_path=pg_catalog"]
                    or function["body_sha256"] != hashlib.sha256(FUNCTIONS[name][2].encode()).hexdigest()
                    or function["public_execute"] is not False
                    or function["executable"] is not (name == "lock_sources")):
                raise GuardRejected("Sandbox function protection mismatch")
        constraints = list(session.execute(CONSTRAINT_SQL).mappings())
        expected = {"p101_registry_pk": "p", "p101_prediction_unique": "u", "p101_prediction_fk": "f",
                    "p101_key_hex": "c", "p101_content_hex": "c", "p101_key_size": "c", "p101_content_size": "c"}
        if len(constraints) != len(expected) or {c["conname"] for c in constraints} != set(expected):
            raise GuardRejected("Sandbox registry constraints missing")
        for c in constraints:
            deferred = c["conname"] == "p101_prediction_fk"
            if (c["contype"] != expected[c["conname"]] or c["convalidated"] is not True
                    or c["condeferrable"] is not deferred or c["condeferred"] is not deferred
                    or c["registry_table"] is not True or c["reference_target"] is not True):
                raise GuardRejected("Sandbox registry constraint mismatch")
        triggers = list(session.execute(TRIGGER_SQL).mappings())
        names = {"p101_shape", "p101_prediction_link", "p101_registry_link"}
        if len(triggers) != 3 or {t["tgname"] for t in triggers} != names:
            raise GuardRejected("Sandbox reverse protections missing")
        for trigger in triggers:
            deferred = trigger["tgname"] != "p101_shape"
            schema = "p101_pilot" if trigger["tgname"] == "p101_registry_link" else "public"
            table = "idempotency_records" if schema == "p101_pilot" else "prediction_records"
            if (trigger["tgenabled"] not in ("O", "A") or trigger["deferred_capable"] is not deferred
                    or trigger["initially_deferred"] is not deferred
                    or trigger["table_schema"] != schema or trigger["table_name"] != table
                    or trigger["function_schema"] != "p101_pilot"
                    or trigger["function_name"] != ("enforce_link" if deferred else "enforce_shape")):
                raise GuardRejected("Sandbox trigger disabled or not deferred")
    except GuardRejected:
        raise
    except Exception:
        raise GuardRejected("Sandbox catalog verification unavailable") from None
