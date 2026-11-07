"""P101 immutable operation journal declaration. No execution authority supplied."""

from alembic import op
import sqlalchemy as sa

revision = "p101_0001_operations"
down_revision = "b2b_0002_analyze"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prediction_records", sa.Column("p101_operation_id", sa.Integer(), nullable=True), schema="public")
    op.create_unique_constraint("uq_prediction_records_p101_pair", "prediction_records", ["id", "p101_operation_id"], schema="public")
    op.create_table(
        "p101_prediction_operations",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement="ignore_fk"),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=False),
        sa.Column("sensor_id", sa.Integer(), nullable=False),
        sa.Column("measurement_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("result_sha256", sa.String(64), nullable=False),
        sa.Column("result_details_json", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("actor_issuer", sa.String(2048), nullable=False),
        sa.Column("actor_subject", sa.String(2048), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("is_alert", sa.Boolean(), nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=False),
        sa.Column("target_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_p101_operations_key"),
        sa.UniqueConstraint("company_id", "equipment_id", "sensor_id", "measurement_id", "model_name", "model_version", name="uq_p101_operations_business"),
        sa.UniqueConstraint("prediction_id", name="uq_p101_operations_prediction"),
        sa.UniqueConstraint("id", "prediction_id", name="uq_p101_operations_pair"),
        sa.ForeignKeyConstraint(["prediction_id", "id"], ["public.prediction_records.id", "public.prediction_records.p101_operation_id"], name="fk_p101_operations_prediction", ondelete="RESTRICT", onupdate="RESTRICT", deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("id > 0 AND company_id > 0 AND site_id > 0 AND equipment_id > 0 AND sensor_id > 0 AND measurement_id > 0 AND actor_user_id > 0 AND prediction_id > 0", name="ck_p101_operations_ids"),
        sa.CheckConstraint("idempotency_key ~ '^[0-9a-f]{64}$' AND input_sha256 ~ '^[0-9a-f]{64}$' AND result_sha256 ~ '^[0-9a-f]{64}$'", name="ck_p101_operations_hashes"),
        sa.CheckConstraint("model_name = 'statistical_deviation' AND model_version = 'p101-dev-stat-v1'", name="ck_p101_operations_model"),
        sa.CheckConstraint("state = 'recorded'", name="ck_p101_operations_state"),
        sa.CheckConstraint("score IN (0, 1) AND is_alert = (score = 1)", name="ck_p101_operations_score"),
        sa.CheckConstraint("actor_issuer <> '' AND actor_issuer = trim(actor_issuer) AND actor_subject <> '' AND actor_subject = trim(actor_subject) AND actor_issuer !~ '[[:cntrl:]]' AND actor_subject !~ '[[:cntrl:]]' AND octet_length(actor_issuer) + octet_length(actor_subject) <= 2048", name="ck_p101_operations_actor"),
        sa.CheckConstraint("isfinite(prepared_at) AND isfinite(recorded_at) AND isfinite(target_at) AND prepared_at <= recorded_at", name="ck_p101_operations_times"),
        sa.CheckConstraint("octet_length(result_details_json) BETWEEN 1 AND 6000 AND result_sha256 = encode(sha256(convert_to(result_details_json, 'UTF8')), 'hex')", name="ck_p101_operations_result"),
        sa.CheckConstraint("idempotency_key = encode(sha256(convert_to('[' || company_id::text || ',' || equipment_id::text || ',' || sensor_id::text || ',' || measurement_id::text || ',\"statistical_deviation\",\"p101-dev-stat-v1\"]', 'UTF8')), 'hex')", name="ck_p101_operations_key"),
        sa.CheckConstraint("(jsonb_typeof(result_details_json::jsonb) = 'object' AND result_details_json::jsonb->>'schema_version' = 'p101-dev-anomaly-details-v1' AND result_details_json::jsonb->>'input_sha256' = input_sha256 AND result_details_json::jsonb->'model'->>'name' = model_name AND result_details_json::jsonb->'model'->>'version' = model_version AND result_details_json::jsonb->'asset'->>'company_id' = company_id::text AND result_details_json::jsonb->'asset'->>'site_id' = site_id::text AND result_details_json::jsonb->'asset'->>'equipment_id' = equipment_id::text AND result_details_json::jsonb->'asset'->>'sensor_id' = sensor_id::text AND result_details_json::jsonb->'target'->>'measurement_id' = measurement_id::text) IS TRUE", name="ck_p101_operations_payload"),
        schema="public",
    )
    op.create_foreign_key("fk_prediction_records_p101_operation", "prediction_records", "p101_prediction_operations", ["p101_operation_id", "id"], ["id", "prediction_id"], source_schema="public", referent_schema="public", ondelete="RESTRICT", onupdate="RESTRICT", deferrable=True, initially="DEFERRED", match="SIMPLE")
    op.execute("""CREATE FUNCTION public.p101_operation_append_only() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, pg_temp AS $body$
BEGIN
    RAISE EXCEPTION 'P101_OPERATION_RETENTION_REQUIRED' USING ERRCODE = '23514';
END;
$body$""")
    op.execute("""CREATE TRIGGER p101_operations_no_mutation
BEFORE UPDATE OR DELETE ON public.p101_prediction_operations
FOR EACH ROW EXECUTE FUNCTION public.p101_operation_append_only()""")
    op.execute("""CREATE TRIGGER p101_operations_no_truncate
BEFORE TRUNCATE ON public.p101_prediction_operations
FOR EACH STATEMENT EXECUTE FUNCTION public.p101_operation_append_only()""")
    op.execute("""CREATE FUNCTION public.p101_prediction_immutable() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, pg_temp AS $body$
BEGIN
    RAISE EXCEPTION 'P101_PREDICTION_RETENTION_REQUIRED' USING ERRCODE = '23514';
END;
$body$""")
    op.execute("""CREATE TRIGGER p101_predictions_no_mutation
BEFORE UPDATE OR DELETE ON public.prediction_records
FOR EACH ROW WHEN (OLD.p101_operation_id IS NOT NULL)
EXECUTE FUNCTION public.p101_prediction_immutable()""")
    op.execute("""CREATE FUNCTION public.p101_operation_validate() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, pg_temp AS $body$
DECLARE
    prediction public.prediction_records%ROWTYPE;
BEGIN
    SELECT * INTO prediction FROM public.prediction_records WHERE id = NEW.prediction_id FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'P101_OPERATION_PREDICTION_MISSING' USING ERRCODE = '23503';
    END IF;
    IF prediction.p101_operation_id IS DISTINCT FROM NEW.id
       OR prediction.equipment_id IS DISTINCT FROM NEW.equipment_id
       OR prediction.sensor_id IS DISTINCT FROM NEW.sensor_id
       OR prediction.measurement_id IS DISTINCT FROM NEW.measurement_id
       OR prediction.model_name IS DISTINCT FROM NEW.model_name
       OR prediction.model_version IS DISTINCT FROM NEW.model_version
       OR prediction.prediction_type IS DISTINCT FROM 'anomaly'
       OR prediction.predicted_at IS DISTINCT FROM NEW.target_at
       OR prediction.created_at IS DISTINCT FROM NEW.recorded_at
       OR prediction.level IS NOT NULL OR prediction.horizon_hours IS NOT NULL
       OR prediction.score IS NULL OR prediction.score NOT IN (0, 1)
       OR prediction.is_alert IS DISTINCT FROM (prediction.score = 1)
       OR prediction.score IS DISTINCT FROM NEW.score
       OR prediction.is_alert IS DISTINCT FROM NEW.is_alert
       OR prediction.details::jsonb IS DISTINCT FROM NEW.result_details_json::jsonb
       OR (NEW.result_details_json::jsonb->'target'->>'timestamp')::timestamptz IS DISTINCT FROM NEW.target_at
    THEN
        RAISE EXCEPTION 'P101_OPERATION_PREDICTION_MISMATCH' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$body$""")
    op.execute("""CREATE CONSTRAINT TRIGGER p101_operations_prediction_matches
AFTER INSERT ON public.p101_prediction_operations DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION public.p101_operation_validate()""")


def downgrade() -> None:
    raise RuntimeError("P101_OPERATION_DOWNGRADE_REQUIRES_SEPARATE_APPROVAL")
