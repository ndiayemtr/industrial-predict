"""Sandbox-only registry and bidirectional protections. Never auto-applied."""

from alembic import op
import re
from sqlalchemy import text

from app.p101_postgres.ddl import FUNCTIONS, function_ddl

revision = "p101_0001"
down_revision = None
branch_labels = ("p101_sandbox",)
depends_on = None


def upgrade():
    config = op.get_context().config.attributes["p101_config"]
    # env.py has checked the effective owner/destination and independent approval.
    writer, reader = config.destination.role, config.reader_role
    if any(re.fullmatch(r"p101_[a-z0-9_]{1,48}", role) is None for role in (writer, reader)):
        raise ValueError("Invalid sandbox role identifier")
    op.execute("""CREATE TABLE p101_pilot.environment_guard (
      singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
      instance_uuid uuid NOT NULL, purpose text NOT NULL CHECK(purpose='p101-ml-sandbox'),
      database_name name NOT NULL CHECK(database_name='industrial_predict_ml_sandbox'),
      owner_role name NOT NULL,writer_role name NOT NULL,reader_role name NOT NULL,
      bootstrap_uuid uuid NOT NULL,provisioning_closed boolean NOT NULL DEFAULT false,
      core_revision text NOT NULL CHECK(core_revision='09ac8101e9fe'),
      p101_revision text NOT NULL CHECK(p101_revision='p101_0001'))""")
    op.execute("""CREATE TABLE p101_pilot.idempotency_records (
      idempotency_key varchar(64) NOT NULL CONSTRAINT p101_registry_pk PRIMARY KEY,
      key_canonical text NOT NULL,content_sha256 varchar(64) NOT NULL,
      content_canonical text NOT NULL,prediction_id integer NOT NULL,
      first_created_at timestamptz NOT NULL,
      CONSTRAINT p101_prediction_unique UNIQUE(prediction_id),
      CONSTRAINT p101_prediction_fk FOREIGN KEY(prediction_id) REFERENCES public.prediction_records(id)
        ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
      CONSTRAINT p101_key_hex CHECK(idempotency_key ~ '^[0-9a-f]{64}$'),
      CONSTRAINT p101_content_hex CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
      CONSTRAINT p101_key_size CHECK(octet_length(key_canonical)<=4096),
      CONSTRAINT p101_content_size CHECK(octet_length(content_canonical)<=16384))""")
    for name in FUNCTIONS:
        op.execute(function_ddl(name))
    op.execute("""CREATE TRIGGER p101_shape BEFORE INSERT OR UPDATE OR DELETE ON public.prediction_records
                  FOR EACH ROW EXECUTE FUNCTION p101_pilot.enforce_shape()""")
    op.execute("""CREATE CONSTRAINT TRIGGER p101_prediction_link AFTER INSERT OR UPDATE OR DELETE
        ON public.prediction_records DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION p101_pilot.enforce_link()""")
    op.execute("""CREATE CONSTRAINT TRIGGER p101_registry_link AFTER INSERT OR UPDATE OR DELETE
        ON p101_pilot.idempotency_records DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION p101_pilot.enforce_link()""")
    for name, (args, _, _, _) in FUNCTIONS.items():
        signature = "jsonb" if args else ""
        op.execute(f"REVOKE ALL ON FUNCTION p101_pilot.{name}({signature}) FROM PUBLIC")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA p101_pilot FROM PUBLIC")
    op.execute(f'GRANT USAGE ON SCHEMA p101_pilot TO "{writer}","{reader}"')
    op.execute(f'GRANT SELECT ON p101_pilot.environment_guard,p101_pilot.alembic_version TO "{writer}"')
    op.execute(f'GRANT SELECT ON public.alembic_version TO "{writer}"')
    op.execute(f'REVOKE ALL ON p101_pilot.idempotency_records,public.prediction_records FROM "{writer}"')
    op.execute(f'GRANT SELECT,INSERT ON p101_pilot.idempotency_records,public.prediction_records TO "{writer}"')
    op.execute(f'GRANT SELECT ON public.prediction_records TO "{reader}"')
    for table in ("companies", "sites", "equipments", "sensors", "measurements"):
        op.execute(f'REVOKE ALL ON public.{table} FROM "{writer}"')
        op.execute(f'GRANT SELECT ON public.{table} TO "{writer}","{reader}"')
    for table in ("maintenance_records", "maintenance_recommendations"):
        op.execute(f'REVOKE ALL ON public.{table} FROM "{writer}"')
    op.execute(f'GRANT EXECUTE ON FUNCTION p101_pilot.lock_sources() TO "{writer}"')
    sequence = op.get_bind().execute(text(
        "SELECT pg_get_serial_sequence('public.prediction_records','id')")).scalar_one()
    if not isinstance(sequence, str) or re.fullmatch(r"public\.[a-z0-9_]+", sequence) is None:
        raise ValueError("Unexpected prediction sequence")
    op.execute(f'GRANT USAGE ON SEQUENCE {sequence} TO "{writer}"')
    # No marker INSERT or fixture provisioning. Separate admin approval is required.


def downgrade():
    count = op.get_bind().execute(text("""SELECT
      (SELECT count(*) FROM p101_pilot.idempotency_records) +
      (SELECT count(*) FROM public.prediction_records WHERE model_name='statistical_deviation')""")).scalar_one()
    if count:
        raise ValueError("P101 history requires an explicit retention procedure")
    config = op.get_context().config.attributes["p101_config"]
    writer, reader = config.destination.role, config.reader_role
    if any(re.fullmatch(r"p101_[a-z0-9_]{1,48}", role) is None for role in (writer, reader)):
        raise ValueError("Invalid sandbox role identifier")
    # Remove the writer's capability before removing its reverse protections.
    op.execute(f'REVOKE ALL ON public.prediction_records FROM "{writer}","{reader}"')
    sequence = op.get_bind().execute(text(
        "SELECT pg_get_serial_sequence('public.prediction_records','id')")).scalar_one()
    if not isinstance(sequence, str) or re.fullmatch(r"public\.[a-z0-9_]+", sequence) is None:
        raise ValueError("Unexpected prediction sequence")
    op.execute(f'REVOKE ALL ON SEQUENCE {sequence} FROM "{writer}"')
    for table in ("companies", "sites", "equipments", "sensors", "measurements"):
        op.execute(f'REVOKE ALL ON public.{table} FROM "{writer}","{reader}"')
    op.execute("DROP TRIGGER p101_prediction_link ON public.prediction_records")
    op.execute("DROP TRIGGER p101_shape ON public.prediction_records")
    op.execute("DROP TRIGGER p101_registry_link ON p101_pilot.idempotency_records")
    for name in ("lock_sources", "enforce_link", "enforce_shape", "canonical_value"):
        signature = "jsonb" if name == "canonical_value" else ""
        op.execute(f"DROP FUNCTION p101_pilot.{name}({signature})")
    op.execute("DROP TABLE p101_pilot.idempotency_records")
    op.execute("DROP TABLE p101_pilot.environment_guard")
    # Keep the sandbox schema/version table managed by the independent Alembic environment.
