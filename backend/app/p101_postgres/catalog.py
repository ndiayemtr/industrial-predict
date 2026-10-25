"""Strict expected catalog shapes. PostgreSQL rendering remains to be verified."""

import re

from app.p101_postgres.runtime import GuardRejected


# pg_get_constraintdef(..., false), with search_path fixed to pg_catalog.
CONSTRAINTS = {
    "p101_registry_pk": ("p", ["idempotency_key"], [], "PRIMARY KEY (idempotency_key)"),
    "p101_prediction_unique": ("u", ["prediction_id"], [], "UNIQUE (prediction_id)"),
    "p101_prediction_fk": ("f", ["prediction_id"], ["id"],
        "FOREIGN KEY (prediction_id) REFERENCES public.prediction_records(id) DEFERRABLE INITIALLY DEFERRED"),
    "p101_key_hex": ("c", ["idempotency_key"], [], "CHECK (((idempotency_key)::text ~ '^[0-9a-f]{64}$'::text))"),
    "p101_content_hex": ("c", ["content_sha256"], [], "CHECK (((content_sha256)::text ~ '^[0-9a-f]{64}$'::text))"),
    "p101_key_size": ("c", ["key_canonical"], [], "CHECK ((octet_length(key_canonical) <= 4096))"),
    "p101_content_size": ("c", ["content_canonical"], [], "CHECK ((octet_length(content_canonical) <= 16384))"),
}

MARKER_CONSTRAINTS = {
    "environment_guard_pkey": "PRIMARY KEY (singleton)",
    "environment_guard_singleton_check": "CHECK (singleton)",
    "environment_guard_purpose_check": "CHECK ((purpose = 'p101-ml-sandbox'::text))",
    "environment_guard_database_name_check": "CHECK ((database_name = 'industrial_predict_ml_sandbox'::name))",
    "environment_guard_core_revision_check": "CHECK ((core_revision = '09ac8101e9fe'::text))",
    "environment_guard_p101_revision_check": "CHECK ((p101_revision = 'p101_0001'::text))",
}

TABLES = {
    "p101_pilot.idempotency_records": ["idempotency_key:character varying(64):true",
        "key_canonical:text:true", "content_sha256:character varying(64):true", "content_canonical:text:true",
        "prediction_id:integer:true", "first_created_at:timestamp with time zone:true"],
    "p101_pilot.environment_guard": ["singleton:boolean:true", "instance_uuid:uuid:true", "purpose:text:true",
        "database_name:name:true", "owner_role:name:true", "writer_role:name:true", "reader_role:name:true",
        "bootstrap_uuid:uuid:true", "provisioning_closed:boolean:true", "core_revision:text:true", "p101_revision:text:true"],
    "p101_pilot.alembic_version": ["version_num:character varying(32):true"],
    "public.prediction_records": ["id:integer:true", "equipment_id:integer:true", "sensor_id:integer:false",
        "measurement_id:integer:false", "prediction_type:character varying(50):true", "score:double precision:true",
        "level:character varying(50):false", "is_alert:boolean:false", "model_name:character varying(100):false",
        "model_version:character varying(50):false", "horizon_hours:double precision:false", "details:json:false",
        "predicted_at:timestamp with time zone:true", "created_at:timestamp with time zone:true"],
}


def sql_shape(value):
    if type(value) is not str:
        raise GuardRejected("Missing SQL definition")
    # Keep string literals intact; never normalize expression semantics or casts.
    return "".join(part if i % 2 else re.sub(r"\s+", " ", part)
                   for i, part in enumerate(re.split(r"('(?:''|[^'])*')", value))).strip()


def validate_objects(rows, owner):
    names = [row["name"] for row in rows]
    if len(names) != len(TABLES) or set(names) != set(TABLES):
        raise GuardRejected("Unexpected sandbox objects")
    for row in rows:
        if (row["owner"] != owner or row["schema_owner"] != owner and row["name"].startswith("p101_pilot.")
                or row["relkind"] != "r" or row["relrowsecurity"] is not False
                or row["columns"] != TABLES[row["name"]]):
            raise GuardRejected("Sandbox object definition or owner mismatch")


def validate_marker_constraints(rows):
    if len(rows) != len(MARKER_CONSTRAINTS) or {r["conname"] for r in rows} != set(MARKER_CONSTRAINTS):
        raise GuardRejected("Marker constraints missing or unexpected")
    for row in rows:
        if (row["convalidated"] is not True or row["condeferrable"] is not False
                or sql_shape(row["definition"]) != MARKER_CONSTRAINTS[row["conname"]]):
            raise GuardRejected("Marker constraint definition mismatch")
