"""Local-only instance marker and prediction constraints; no fixture or prediction INSERT."""

from alembic import op
import sqlalchemy as sa

from app.p101_local_demo.contracts import DATABASE, PURPOSE
from app.p101_local_demo.setup_config import REVISION, SetupError, SetupSettings
from app.p101_persistence.contracts import FIXTURE_SHA256


revision = 'p101_local_0001'
down_revision = '09ac8101e9fe'
branch_labels = None
depends_on = None
PROFILE = "prediction_type='anomaly' AND model_name='statistical_deviation' AND model_version='p101-stat-v1'"
CONTENT_CHECK = """CASE WHEN prediction_type='anomaly' AND model_name='statistical_deviation'
 AND model_version='p101-stat-v1' THEN (
 sensor_id IS NOT NULL AND measurement_id IS NOT NULL AND score IN (0,1)
 AND is_alert=(score=1) AND level IS NULL AND horizon_hours IS NULL
 AND json_typeof(details)='object' AND octet_length(details::text)<=6000
 AND details->>'schema_version'='p101-local-demo-details-v1'
 AND json_typeof(details->'synthetic')='boolean' AND details->>'synthetic'='true'
 AND json_typeof(details->'reason')='string' AND length(details->>'reason') BETWEEN 1 AND 1000
 AND json_typeof(details->'calculation')='object'
 AND json_typeof(details->'local_demo')='object'
 AND details->'local_demo'->>'instance_uuid'='{instance_uuid}'
 AND details->'local_demo'->>'idempotency_key' ~ '^[0-9a-f]{{64}}$'
 AND details->'local_demo'->>'content_sha256' ~ '^[0-9a-f]{{64}}$'
 ) IS TRUE ELSE true END"""


def upgrade():
    settings = op.get_context().config.attributes.get('local_settings')
    if type(settings) is not SetupSettings:
        raise SetupError('Local migration requires verified explicit settings')
    settings.validate()
    op.execute('CREATE SCHEMA local_demo')
    op.create_table('environment',
        sa.Column('singleton', sa.Boolean(), primary_key=True),
        sa.Column('instance_uuid', sa.Uuid(), nullable=False, unique=True),
        sa.Column('purpose', sa.Text(), nullable=False),
        sa.Column('database_name', sa.Text(), nullable=False),
        sa.Column('schema_revision', sa.Text(), nullable=False),
        sa.Column('fixture_sha256', sa.String(64), nullable=False),
        sa.Column('bootstrap_sha256', sa.String(64), nullable=True),
        sa.Column('bootstrap_closed', sa.Boolean(), nullable=False),
        sa.CheckConstraint('singleton', name='ck_local_singleton'),
        sa.CheckConstraint("purpose='local-p101-functional-demo'", name='ck_local_purpose'),
        sa.CheckConstraint("database_name='industrial_predict_p101_local_demo'", name='ck_local_database'),
        sa.CheckConstraint("schema_revision='p101_local_0001'", name='ck_local_revision'),
        sa.CheckConstraint("fixture_sha256 ~ '^[0-9a-f]{64}$'", name='ck_local_fixture'),
        sa.CheckConstraint("((NOT bootstrap_closed AND bootstrap_sha256 IS NULL) OR "
                           "(bootstrap_closed AND bootstrap_sha256 ~ '^[0-9a-f]{64}$')) IS TRUE",
                           name='ck_local_bootstrap'), schema='local_demo')
    op.get_bind().execute(sa.text("""INSERT INTO local_demo.environment
        (singleton,instance_uuid,purpose,database_name,schema_revision,fixture_sha256,bootstrap_closed)
        VALUES (true,CAST(:uuid AS uuid),:purpose,:database,:revision,:fixture,false)"""),
        dict(uuid=settings.instance_uuid, purpose=PURPOSE, database=DATABASE,
             revision=REVISION, fixture=FIXTURE_SHA256))
    op.create_index('uq_local_p101_target', 'prediction_records',
        ['equipment_id', 'sensor_id', 'measurement_id', 'model_name', 'model_version'],
        unique=True, schema='public', postgresql_where=sa.text(PROFILE))
    op.create_check_constraint('ck_local_p101_content', 'prediction_records',
        CONTENT_CHECK.format(instance_uuid=settings.instance_uuid), schema='public')


def downgrade():
    raise SetupError('Local pilot downgrade intentionally disabled; explicit retention review required')
