"""Pure local PredictionRecord mapping and strict two-row retry comparison."""

from dataclasses import dataclass
import json

from app.anomaly_detection.p101_canonical import bounded_details, finite_value, instant_datetime, manifest_sha256, utc_instant
from app.anomaly_detection.p101_contracts import ASSET, Computed, LogicalPrediction, Statistics
from app.p101_local_demo.contracts import CUTOFFS, TARGETS, CalculationContext, ComputedPair, SqlIdentityMap
from app.p101_local_demo.processing import validate_context
from app.p101_local_demo.reader import instant, sql_id, validate_fixture
from app.p101_local_demo.setup_config import REVISION, ROLES
from app.p101_persistence.canonical import build_key, canonical_projection
from app.p101_persistence.contracts import CALCULATION_REVISION, FIXTURE_SHA256, IdempotencyTuple
from app.p101_persistence.preparation import project_content


ADAPTER_VERSION = 'p101-local-persistence-v1'
DETAIL_SCHEMA = 'p101-local-demo-details-v1'
FIELDS = ('id', 'equipment_id', 'sensor_id', 'measurement_id', 'prediction_type', 'score',
          'level', 'is_alert', 'model_name', 'model_version', 'horizon_hours', 'details',
          'predicted_at', 'created_at')


class PredictionError(ValueError):
    """Stable diagnostic only; never driver SQL, credentials or supplied values."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PredictionPlan:
    target: str
    payload_json: str
    key_json: str
    content_json: str

    def sql_values(self):
        result = json.loads(self.payload_json)
        for name in ('predicted_at', 'created_at'):
            result[name] = instant_datetime(result[name])
        return result


@dataclass(frozen=True)
class PersistenceResult:
    disposition: str
    records_json: str

    @property
    def records(self):
        return tuple(json.loads(self.records_json))


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def validate_writer(destination):
    destination.validate()
    if destination.role != ROLES[2] or destination.schema_revision != REVISION:
        raise PredictionError('WRITER_DESTINATION_REQUIRED')


def _mapping(identities):
    if type(identities) is not SqlIdentityMap or type(identities.measurements) is not tuple:
        raise PredictionError('SQL_MAPPING_REQUIRED')
    for value in (identities.company_id, identities.site_id, identities.equipment_id, identities.sensor_id):
        sql_id(value)
    if (len(identities.measurements) != 12
            or any(type(row) is not tuple or len(row) != 2 for row in identities.measurements)
            or {r[0] for r in identities.measurements} != {f'DEMO-M-{i:03d}' for i in range(1, 13)}
            or len({sql_id(r[1]) for r in identities.measurements}) != 12):
        raise PredictionError('SQL_MAPPING_REQUIRED')
    return dict(company_id=identities.company_id, site_id=identities.site_id,
        equipment_id=identities.equipment_id, sensor_id=identities.sensor_id,
        measurements=dict(sorted(identities.measurements)))


def _checked_result(result, reference, context):
    if type(result) is not Computed or result.status != 'computed':
        raise PredictionError('TWO_COMPUTED_REQUIRED')
    # Reuses ML4.2A's pure validation/projection, not its protected destination declarations.
    logical = project_content(result)
    p, d = result.prediction, result.prediction.details
    if p.measurement_fixture_id not in TARGETS:
        raise PredictionError('TARGET_MISMATCH')
    position = TARGETS.index(p.measurement_fixture_id)
    expected_ids = tuple(f'DEMO-M-{i:03d}' for i in range(position + 1, position + 11))
    by_id = {r['fixture_id']: r for r in reference['observations']}
    target = by_id[p.measurement_fixture_id]
    if (result.dataset_sha256 != FIXTURE_SHA256 or d['producer']['code_revision'] != CALCULATION_REVISION
            or d['run_id'] != context.run_id or d['prepared_at'] != utc_instant(context.prepared_at)
            or d['cutoff_utc'] != CUTOFFS[position] or result.reference_ids != expected_ids
            or result.reference_sha256 != manifest_sha256({'observations': [by_id[i] for i in expected_ids]})):
        raise PredictionError('COMPUTED_CONTEXT_MISMATCH')
    for key in ('timestamp', 'available_at', 'value', 'quality', 'unit'):
        expected = instant(target[key]) if key in ('timestamp', 'available_at') else target[key]
        if d['target'][key] != expected:
            raise PredictionError('TARGET_FIXTURE_MISMATCH')
    return logical


def prepare_predictions(pair, destination, reference, context, created_at):
    """Produce 13 INSERT values; id is allocated only by PostgreSQL RETURNING."""
    try:
        validate_writer(destination)
        validate_fixture(reference)
        validate_context(context)
        created = utc_instant(created_at)
        if created < utc_instant(context.prepared_at):
            raise PredictionError('CREATED_AT_PRECEDES_CALCULATION')
        if (type(pair) is not ComputedPair or type(pair.results) is not tuple or len(pair.results) != 2
                or any(type(r) is not Computed for r in pair.results)
                or {r.prediction.measurement_fixture_id for r in pair.results} != set(TARGETS)):
            raise PredictionError('TWO_COMPUTED_REQUIRED')
        mapping = _mapping(pair.identities)
        prepared = []
        for result in sorted(pair.results, key=lambda r: r.prediction.measurement_fixture_id):
            logical = _checked_result(result, reference, context)
            p, d = result.prediction, result.prediction.details
            key = build_key(IdempotencyTuple(destination.instance_uuid, result.dataset_sha256,
                ASSET['equipment_code'], ASSET['sensor_code'], p.measurement_fixture_id, p.predicted_at,
                d['cutoff_utc'], p.prediction_type, p.model_name, p.model_version,
                d['producer']['code_revision'], result.reference_sha256))
            content = canonical_projection(dict(schema_version=ADAPTER_VERSION,
                instance_uuid=destination.instance_uuid, logical=json.loads(logical.canonical_json), sql_mapping=mapping))
            details = dict(schema_version=DETAIL_SCHEMA, synthetic=True, reason=d['reason'], calculation=d,
                local_demo=dict(instance_uuid=destination.instance_uuid, adapter_version=ADAPTER_VERSION,
                    idempotency_key=key.projection.sha256, content_sha256=content.sha256, sql_mapping=mapping))
            bounded_details(details)  # Final wrapper: six levels, 240 chars/string, 6000 UTF-8 bytes.
            payload = dict(equipment_id=mapping['equipment_id'], sensor_id=mapping['sensor_id'],
                measurement_id=mapping['measurements'][p.measurement_fixture_id],
                prediction_type=p.prediction_type, score=p.score, level=p.level, is_alert=p.is_alert,
                model_name=p.model_name, model_version=p.model_version, horizon_hours=p.horizon_hours,
                details=details, predicted_at=p.predicted_at, created_at=created)
            prepared.append(PredictionPlan(p.measurement_fixture_id, _json(payload),
                key.projection.canonical_json, content.canonical_json))
        return tuple(prepared)
    except PredictionError:
        raise
    except Exception:
        raise PredictionError('MAPPING_REJECTED') from None


def compare_records(rows, plans, identities, destination, reference):
    """Validate all 14 fields, rebuild stored projections, return original records on retry."""
    try:
        if len(rows) != 2 or len({sql_id(r['id']) for r in rows}) != 2:
            raise PredictionError('PARTIAL_OR_DUPLICATE_STATE')
        computed, normalized, contexts = [], [], []
        for original in rows:
            if set(original) != set(FIELDS):
                raise PredictionError('RECORD_FIELDS_MISMATCH')
            row = dict(original)
            for name in ('equipment_id', 'sensor_id', 'measurement_id'):
                sql_id(row[name])
            if not finite_value(row['score']) or row['score'] not in (0, 1) or type(row['is_alert']) is not bool:
                raise PredictionError('INVALID_STORED_SCORE')
            for name in ('predicted_at', 'created_at'):
                row[name] = instant(row[name])
            details = row['details']
            if type(details) is not dict or set(details) != {'schema_version','synthetic','reason','calculation','local_demo'}:
                raise PredictionError('STORED_DETAILS_REJECTED')
            bounded_details(details)
            d = details['calculation']
            source = details['local_demo']['sql_mapping']
            if set(source) != {'company_id','site_id','equipment_id','sensor_id','measurements'}:
                raise PredictionError('STORED_SQL_MAPPING_REJECTED')
            _mapping(SqlIdentityMap(source['company_id'], source['site_id'], source['equipment_id'],
                source['sensor_id'], tuple(source['measurements'].items())))
            context = CalculationContext(d['run_id'], d['prepared_at'], d['producer']['code_revision'], CUTOFFS)
            contexts.append(context)
            p = LogicalPrediction(ASSET['equipment_id'], ASSET['sensor_id'], d['target']['fixture_id'],
                row['predicted_at'], int(row['score']), row['is_alert'], _json(d), row['prediction_type'],
                row['model_name'], row['model_version'], row['level'], row['horizon_hours'])
            computed.append(Computed(p, tuple(r['fixture_id'] for r in d['reference']['observations']),
                Statistics(**{k:d['statistics'][k] for k in ('mean','sample_std','absolute_deviation','threshold')}),
                d['dataset']['sha256'], d['reference']['sha256']))
            normalized.append(row)
        if contexts[0] != contexts[1] or normalized[0]['created_at'] != normalized[1]['created_at']:
            raise PredictionError('INCONSISTENT_STORED_BATCH')
        rebuilt = prepare_predictions(ComputedPair(tuple(computed), identities), destination, reference,
                                      contexts[0], normalized[0]['created_at'])
        candidates = {p.target:p for p in plans}
        by_target = {r['details']['calculation']['target']['fixture_id']:r for r in normalized}
        for stored_plan in rebuilt:
            row = dict(by_target[stored_plan.target])
            row.pop('id')
            # Full stored details must also be well formed, including their own fingerprints and SQL mapping.
            if canonical_projection(row).canonical_json != canonical_projection(json.loads(stored_plan.payload_json)).canonical_json:
                raise PredictionError('STORED_CONTENT_CONFLICT')
            candidate = candidates[stored_plan.target]
            if stored_plan.key_json != candidate.key_json or stored_plan.content_json != candidate.content_json:
                raise PredictionError('CONTENT_CONFLICT')
        return PersistenceResult('identical_retry', _json([by_target[t] for t in TARGETS]))
    except PredictionError:
        raise
    except Exception:
        raise PredictionError('STORED_RECORD_REJECTED') from None
