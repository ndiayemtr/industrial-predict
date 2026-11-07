"""P101 journal metadata only; no writer, authority or database lifecycle.

One complete, immutable logical record is reserved before the prediction INSERT
using a caller-allocated prediction id and a deferred FK. 'recorded' describes
content, never a client commit acknowledgement. SQL triggers are published only
in the guarded revision; create_all() is not an equivalent deployment.
"""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class P101PredictionOperation(Base):
    __tablename__ = "p101_prediction_operations"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_p101_operations_key"),
        UniqueConstraint("company_id", "equipment_id", "sensor_id", "measurement_id", "model_name", "model_version",
                         name="uq_p101_operations_business"),
        UniqueConstraint("prediction_id", name="uq_p101_operations_prediction"),
        UniqueConstraint("id", "prediction_id", name="uq_p101_operations_pair"),
        ForeignKeyConstraint(["prediction_id", "id"], ["prediction_records.id", "prediction_records.p101_operation_id"],
                             name="fk_p101_operations_prediction", ondelete="RESTRICT", onupdate="RESTRICT",
                             deferrable=True, initially="DEFERRED"),
        CheckConstraint("id > 0 AND company_id > 0 AND site_id > 0 AND equipment_id > 0 AND sensor_id > 0 AND measurement_id > 0 AND actor_user_id > 0 AND prediction_id > 0",
                        name="ck_p101_operations_ids"),
        CheckConstraint("idempotency_key ~ '^[0-9a-f]{64}$' AND input_sha256 ~ '^[0-9a-f]{64}$' AND result_sha256 ~ '^[0-9a-f]{64}$'",
                        name="ck_p101_operations_hashes"),
        CheckConstraint("model_name = 'statistical_deviation' AND model_version = 'p101-dev-stat-v1'",
                        name="ck_p101_operations_model"),
        CheckConstraint("state = 'recorded'", name="ck_p101_operations_state"),
        CheckConstraint("score IN (0, 1) AND is_alert = (score = 1)", name="ck_p101_operations_score"),
        CheckConstraint("actor_issuer <> '' AND actor_issuer = trim(actor_issuer) AND actor_subject <> '' AND actor_subject = trim(actor_subject) AND actor_issuer !~ '[[:cntrl:]]' AND actor_subject !~ '[[:cntrl:]]' AND octet_length(actor_issuer) + octet_length(actor_subject) <= 2048",
                        name="ck_p101_operations_actor"),
        CheckConstraint("isfinite(prepared_at) AND isfinite(recorded_at) AND isfinite(target_at) AND prepared_at <= recorded_at",
                        name="ck_p101_operations_times"),
        CheckConstraint("octet_length(result_details_json) BETWEEN 1 AND 6000 AND result_sha256 = encode(sha256(convert_to(result_details_json, 'UTF8')), 'hex')",
                        name="ck_p101_operations_result"),
        CheckConstraint("idempotency_key = encode(sha256(convert_to('[' || company_id::text || ',' || equipment_id::text || ',' || sensor_id::text || ',' || measurement_id::text || ',\"statistical_deviation\",\"p101-dev-stat-v1\"]', 'UTF8')), 'hex')",
                        name="ck_p101_operations_key"),
        CheckConstraint("(jsonb_typeof(result_details_json::jsonb) = 'object' AND result_details_json::jsonb->>'schema_version' = 'p101-dev-anomaly-details-v1' AND result_details_json::jsonb->>'input_sha256' = input_sha256 AND result_details_json::jsonb->'model'->>'name' = model_name AND result_details_json::jsonb->'model'->>'version' = model_version AND result_details_json::jsonb->'asset'->>'company_id' = company_id::text AND result_details_json::jsonb->'asset'->>'site_id' = site_id::text AND result_details_json::jsonb->'asset'->>'equipment_id' = equipment_id::text AND result_details_json::jsonb->'asset'->>'sensor_id' = sensor_id::text AND result_details_json::jsonb->'target'->>'measurement_id' = measurement_id::text) IS TRUE",
                        name="ck_p101_operations_payload"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement="ignore_fk")
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    site_id: Mapped[int] = mapped_column(Integer, nullable=False)
    equipment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sensor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    result_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    result_details_json: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    actor_subject: Mapped[str] = mapped_column(String(2048), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    is_alert: Mapped[bool] = mapped_column(Boolean, nullable=False)
    prediction_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prepared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
