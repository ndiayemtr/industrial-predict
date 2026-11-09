"""Synthetic SQL plans and offline state machine. Never opens a DB connection."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from threading import Lock

from app.p101_dev.adapter import IndustrialChain, IndustrialMeasurement, IndustrialSnapshot, evaluate_snapshot
from app.p101_dev.contracts import Computed, DeclaredProvenance
from b2b_postgres_qualification import validation as b2b
from b2b_postgres_qualification.contracts import Offline, ExecutionDisabled, deny
from p101_postgres_qualification.plans import require_campaign, fingerprint, exact_equal


FIXTURE = Path(__file__).with_name('fixture.json')
FIXTURE_SHA256 = 'df8eebb4c638ccf28d93baa48c3da82929b552a239da4fc34181b2db7b646576'


@dataclass(frozen=True, slots=True, repr=False)
class Reference(Offline):
    name: str


@dataclass(frozen=True, slots=True, repr=False)
class Statement(Offline):
    sql: str
    parameters: tuple
    returns: str | None = None


@dataclass(frozen=True, slots=True, repr=False)
class FixtureIds(Offline):
    company: int
    site: int
    equipment: int
    sensor: int
    measurements: tuple[int, ...]  # Ten reference ids followed by the target id.


@dataclass(frozen=True, slots=True, repr=False)
class Operation(Offline):
    campaign_sha256: str
    ids: FixtureIds
    computed: Computed
    key: str
    prepared_at: datetime
    recorded_at: datetime
    actor: tuple[int, str, str]


def _fixture():
    content = FIXTURE.read_text(encoding='utf-8').replace('\r\n', '\n')
    b2b.require(sha256(content.encode()).hexdigest() == FIXTURE_SHA256)
    return json.loads(content)


@b2b.guarded
def seed_plan(campaign, *, expected_campaign):
    """No presumed SQL ids: symbolic references resolve only from RETURNING results."""
    require_campaign(campaign, expected_campaign)
    data = _fixture()
    time = datetime.fromisoformat(data['observed_at']).replace(tzinfo=None)
    code = campaign.database
    steps = [
        Statement('INSERT INTO public.companies (name,code,description,created_at,updated_at) VALUES (%s,%s,%s,%s,%s) RETURNING id',
            ('Synthetic qualification', code, 'Synthetic only', time, time), 'company'),
        Statement('INSERT INTO public.sites (name,code,description,company_id,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id',
            ('Synthetic site', code, None, Reference('company'), time, time), 'site'),
        Statement('INSERT INTO public.equipments (name,code,equipment_type,description,status,site_id,created_at,updated_at,criticality) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
            ('Synthetic equipment', code, 'pump', None, 'active', Reference('site'), time, time, 'medium'), 'equipment'),
        Statement('INSERT INTO public.sensors (name,code,sensor_type,unit,description,status,equipment_id,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
            ('Synthetic sensor', code, data['sensor_type'], data['unit'], None, 'active', Reference('equipment'), time, time), 'sensor'),
    ]
    target = datetime.fromisoformat(data['target_at'])
    for index, value in enumerate((*data['reference_values'], data['target_value'])):
        observed = target - timedelta(days=10-index) if index < 10 else target
        steps.append(Statement('INSERT INTO public.measurements (sensor_id,timestamp,value,quality) VALUES (%s,%s,%s,%s) RETURNING id',
            (Reference('sensor'), observed, value, data['quality']), f'measurement_{index}'))
    return tuple(steps)


@b2b.guarded
def prepare_operation(campaign, ids, *, expected_campaign):
    require_campaign(campaign, expected_campaign)
    b2b.require(type(ids) is FixtureIds and type(ids.measurements) is tuple and len(ids.measurements) == 11)
    b2b.require(all(type(value) is int and 0 < value <= 2147483647 for value in (
        ids.company, ids.site, ids.equipment, ids.sensor, *ids.measurements)))
    b2b.require(len(set(ids.measurements)) == 11)
    data = _fixture()
    target, observed = (datetime.fromisoformat(data[name]) for name in ('target_at', 'observed_at'))
    chain = IndustrialChain(ids.company, ids.site, ids.company, ids.equipment, ids.site,
        ids.sensor, ids.equipment, data['sensor_type'], data['unit'])
    references = tuple(IndustrialMeasurement(ids.measurements[i], ids.sensor,
        target - timedelta(days=10-i), value, data['quality']) for i, value in enumerate(data['reference_values']))
    snapshot = IndustrialSnapshot(chain,
        IndustrialMeasurement(ids.measurements[10], ids.sensor, target, data['target_value'], data['quality']),
        references, target, observed, DeclaredProvenance('p101-qualification',
            'campaign:' + campaign.campaign_id, True, code_revision='bd5d82a093da7524cc2519237bdf3d444ff57366'))
    computed = evaluate_snapshot(snapshot)
    b2b.require(type(computed) is Computed and len(computed.details_json.encode()) <= 6000)
    key = sha256(json.dumps([ids.company, ids.equipment, ids.sensor, ids.measurements[10],
        computed.model_name, computed.model_version], separators=(',', ':')).encode()).hexdigest()
    actor = (1, 'https://qualification.invalid', 'campaign-' + campaign.campaign_id.replace('-', ''))
    return Operation(b2b.destination_fingerprint(campaign), ids, computed, key, observed,
        observed + timedelta(seconds=1), actor)


def _review_operation(campaign, operation):
    b2b.require(type(operation) is Operation)
    b2b.require(exact_equal(operation, prepare_operation(campaign, operation.ids, expected_campaign=campaign)))


def _rows(operation, prediction_id, operation_id):
    r = operation.computed
    journal = dict(id=operation_id, idempotency_key=operation.key, company_id=r.asset.company_id,
        site_id=r.asset.site_id, equipment_id=r.asset.equipment_id, sensor_id=r.asset.sensor_id,
        measurement_id=r.target.measurement_id, model_name=r.model_name, model_version=r.model_version,
        input_sha256=r.input_sha256, result_sha256=r.details_sha256, result_details_json=r.details_json,
        actor_user_id=operation.actor[0], actor_issuer=operation.actor[1], actor_subject=operation.actor[2],
        state='recorded', score=r.score, is_alert=r.is_alert, prediction_id=prediction_id,
        target_at=datetime.fromisoformat(r.target.timestamp.replace('Z', '+00:00')),
        prepared_at=operation.prepared_at, recorded_at=operation.recorded_at)
    prediction = dict(id=prediction_id, equipment_id=r.asset.equipment_id, sensor_id=r.asset.sensor_id,
        measurement_id=r.target.measurement_id, prediction_type='anomaly', score=float(r.score),
        level=None, is_alert=r.is_alert, model_name=r.model_name, model_version=r.model_version,
        horizon_hours=None, details=r.details, predicted_at=journal['target_at'],
        created_at=operation.recorded_at, p101_operation_id=operation_id)
    return journal, prediction


@b2b.guarded
def pair_plan(campaign, operation, *, expected_campaign):
    require_campaign(campaign, expected_campaign)
    _review_operation(campaign, operation)
    # Symbols are resolved from nextval and INSERT RETURNING, never by max(id).
    journal, prediction = _rows(operation, Reference('prediction_id'), Reference('operation_id'))
    del journal['id']
    del prediction['p101_operation_id']
    prediction['p101_operation_id'] = Reference('operation_id')
    # JSON is explicitly encoded/cast, not dependent on an ambient driver's adapter.
    prediction['details'] = operation.computed.details_json
    def insert(table, values, returning=None):
        marks = ['%s::json' if key == 'details' else '%s' for key in values]
        sql = f'INSERT INTO public.{table} (' + ','.join(values) + ') VALUES (' + ','.join(marks) + ')'
        if returning:
            sql += ' RETURNING id'
        return Statement(sql, tuple(values.values()), returning)
    return (
        Statement('BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE', ()),
        Statement("SET LOCAL search_path = public", ()),
        Statement("SELECT nextval(pg_get_serial_sequence('public.prediction_records','id')) AS id", (), 'prediction_id'),
        insert('p101_prediction_operations', journal, 'operation_id'),
        insert('prediction_records', prediction),
        Statement('SET CONSTRAINTS ALL IMMEDIATE', ()),
        Statement('COMMIT', ()),
    )


# Future independent reader must verify its own TLS/identity first. The LEFT JOIN
# also returns orphan journals so a missing prediction cannot be filtered away.
PAIR_SQL = """SELECT row_to_json(o) AS operation,row_to_json(p) AS prediction
 FROM public.p101_prediction_operations o LEFT JOIN public.prediction_records p
 ON p.id=o.prediction_id AND p.p101_operation_id=o.id
 WHERE o.idempotency_key=%s ORDER BY o.id LIMIT 2"""


@b2b.guarded
def normalize_pair_observation(rows):
    """Normalize only the documented JSON timestamp/float representation of PAIR_SQL.

    No filling absent fields, fixing ids, attaching naive timezones or reconstructing
    journal text. The exact-pair reviewer still checks every field afterwards.
    """
    b2b.require(type(rows) is list and len(rows) <= 2)
    result = []
    for row in rows:
        b2b.require(type(row) is dict and set(row) == {'operation', 'prediction'})
        journal, prediction = deepcopy(row['operation']), deepcopy(row['prediction'])
        b2b.require(type(journal) is dict and type(prediction) is dict)
        for record, names in ((journal, ('target_at', 'prepared_at', 'recorded_at')),
                              (prediction, ('predicted_at', 'created_at'))):
            for name in names:
                value = record[name]
                b2b.require(type(value) is str and len(value) <= 40)
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                b2b.require(parsed.tzinfo is not None and parsed.utcoffset() is not None)
                record[name] = parsed.astimezone(timezone.utc)
        b2b.require(type(prediction['score']) in (int, float) and prediction['score'] in (0, 1))
        prediction['score'] = float(prediction['score'])
        result.append((journal, prediction))
    return tuple(result)


@b2b.guarded
def review_pair(campaign, operation, *, expected_campaign, writer_connection_id,
                reader_connection_id, rows):
    """Compare injected observations; independent UUIDs alone do not attest live TLS."""
    require_campaign(campaign, expected_campaign)
    _review_operation(campaign, operation)
    b2b.identifier(writer_connection_id)
    b2b.identifier(reader_connection_id)
    b2b.require(writer_connection_id != reader_connection_id and type(rows) is tuple and len(rows) == 1)
    b2b.require(type(rows[0]) is tuple and len(rows[0]) == 2)
    journal, prediction = rows[0]
    b2b.require(type(journal) is dict and type(prediction) is dict)
    b2b.require(type(journal.get('id')) is int and journal['id'] > 0
        and type(prediction.get('id')) is int and prediction['id'] > 0)
    expected = _rows(operation, prediction['id'], journal['id'])
    b2b.require(exact_equal((journal, prediction), expected))
    # Digest metadata is safe to journal; it is not a persistence attestation.
    return fingerprint(dict(campaign=operation.campaign_sha256, key=operation.key,
        prediction_id=prediction['id'], operation_id=journal['id'],
        result_sha256=operation.computed.details_sha256))


class OfflineScenario(Offline):
    """Concrete in-memory rehearsal only; no callable SQL sink or driver injection."""

    def __init__(self, campaign, *, expected_campaign):
        require_campaign(campaign, expected_campaign)
        self._campaign, self._expected = campaign, expected_campaign
        self._attempted, self._rows, self._lock = set(), (), Lock()

    @b2b.guarded
    def rehearse(self, operation, *, prediction_id, operation_id, acknowledgement='confirmed'):
        with self._lock:
            _review_operation(self._campaign, operation)
            b2b.require(acknowledgement in ('confirmed', 'lost_before_commit', 'lost_after_commit'))
            b2b.require(all(type(value) is int and 0 < value <= 2147483647 for value in (prediction_id, operation_id)))
            b2b.require(operation.key not in self._attempted and not self._rows)
            self._attempted.add(operation.key)  # Retained even on ambiguous outcomes.
            if acknowledgement != 'lost_before_commit':
                self._rows = (_rows(operation, prediction_id, operation_id),)
            return 'simulated_commit_confirmed' if acknowledgement == 'confirmed' else 'uncertain'

    def observe(self):
        # A fresh copy models a separate read; never claimed to be a DB connection.
        with self._lock:
            return deepcopy(self._rows)


def request_scenario_execution(*args, **kwargs):
    """Read-only INFRA-3 cannot execute these INSERT/COMMIT statements."""
    deny(ExecutionDisabled)
