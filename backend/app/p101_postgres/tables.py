"""Independent Core metadata: no app.models, Base, settings or global engine."""

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer,
    JSON, MetaData, String, Table, Text, UniqueConstraint,
)


metadata = MetaData()
predictions = Table(
    "prediction_records", metadata,
    Column("id", Integer, primary_key=True),
    Column("equipment_id", Integer, nullable=False),
    Column("sensor_id", Integer), Column("measurement_id", Integer),
    Column("prediction_type", String(50), nullable=False), Column("score", Float, nullable=False),
    Column("level", String(50)), Column("is_alert", Boolean),
    Column("model_name", String(100)), Column("model_version", String(50)),
    Column("horizon_hours", Float), Column("details", JSON),
    Column("predicted_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False), schema="public",
)
registry = Table(
    "idempotency_records", metadata,
    Column("idempotency_key", String(64), primary_key=True),
    Column("key_canonical", Text, nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("content_canonical", Text, nullable=False),
    Column("prediction_id", Integer, ForeignKey("public.prediction_records.id",
           name="p101_prediction_fk", ondelete="NO ACTION", deferrable=True,
           initially="DEFERRED"), nullable=False),
    Column("first_created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("prediction_id", name="p101_prediction_unique"),
    CheckConstraint("idempotency_key ~ '^[0-9a-f]{64}$'", name="p101_key_hex"),
    CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="p101_content_hex"),
    CheckConstraint("octet_length(key_canonical) <= 4096", name="p101_key_size"),
    CheckConstraint("octet_length(content_canonical) <= 16384", name="p101_content_size"),
    schema="p101_pilot",
)
