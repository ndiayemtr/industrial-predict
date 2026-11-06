"""Synthetic business projections only; no SQL, ORM instances or live DEV data."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from app.p101_dev import adapter
from app.p101_dev.adapter import (
    IndustrialChain, IndustrialMeasurement, IndustrialSnapshot, adapt, evaluate_snapshot,
)
from app.p101_dev.contracts import (
    Abstained, AbstentionCode as A, Computed, DeclaredProvenance, EvaluationInput,
    Rejected, RejectionCode as R,
)
from app.p101_dev.evaluation import evaluate
from app.p101_dev.preparation import prepare
from test_evaluation import no_external_effects


@pytest.fixture
def industrial():
    chain = IndustrialChain(101, 202, 101, 303, 202, 404, 303, "temperature", "°C")
    target_time = datetime(2026, 4, 11, 13, 47, 2, 123456, tzinfo=timezone.utc)
    values = (65, 63, 67, 64.5, 65.5, 64.5, 65.5, 65, 65, 65)
    references = tuple(IndustrialMeasurement(i + 1, 404, target_time - timedelta(days=10-i), value, "good")
                       for i, value in enumerate(values))
    return IndustrialSnapshot(chain, IndustrialMeasurement(11, 404, target_time, 70, "good"),
        references, target_time, target_time + timedelta(days=5),
        DeclaredProvenance("synthetic-business-snapshot", "adapter-test-review", True))


def assert_abstained(snapshot, code):
    for result in (adapt(snapshot), evaluate_snapshot(snapshot)):
        assert type(result) is Abstained and result.code is code
        assert result.prediction is None and not hasattr(result, "score")


def assert_rejected(snapshot, code):
    for result in (adapt(snapshot), evaluate_snapshot(snapshot)):
        assert type(result) is Rejected and result.code is code
        assert not hasattr(result, "score")


def test_calculable_business_snapshot_uses_existing_engine(industrial, monkeypatch):
    before = deepcopy(industrial)
    calls = []
    def tracked(value):
        calls.append(value)
        return evaluate(value)
    monkeypatch.setattr(adapter, "evaluate", tracked)
    adapted = adapt(industrial)
    assert type(adapted) is EvaluationInput and len(calls) == 1
    assert adapted == prepare(adapted).value
    calls.clear()
    result = evaluate_snapshot(industrial)
    assert len(calls) == 1 and result == evaluate(adapted)
    assert type(result) is Computed and result.score == 1 and type(result.score) is int
    assert result.is_alert is True and result.statistics.mean == 65
    assert result.statistics.sample_std == 1 and result.statistics.threshold == 3
    assert result.statistics.absolute_deviation == 5
    assert result.details["statistics"]["score_semantics"] == "binary_indicator_non_probabilistic"
    assert result.details["availability"]["historical_availability_attested"] is False
    assert result.details["provenance"]["verification"] == "declarations_not_authenticated"
    assert result.asset.company_id == 101 and result.target.measurement_id == 11
    assert result.reference_ids == tuple(range(1, 11)) and industrial == before
    with pytest.raises(FrozenInstanceError): industrial.chain.sensor_id = 1


@pytest.mark.parametrize("count", [0, 3, 9])
def test_missing_history_is_not_filled(industrial, count):
    value = replace(industrial, references=industrial.references[:count])
    assert_abstained(value, A.INSUFFICIENT_HISTORY)


def test_cadence_is_not_repaired_or_rounded(industrial):
    rows = list(industrial.references)
    rows[0] = replace(rows[0], timestamp=rows[0].timestamp + timedelta(microseconds=1))
    assert_abstained(replace(industrial, references=tuple(rows)), A.GAP_OR_CADENCE)


@pytest.mark.parametrize("quality", ["suspect", "bad", "estimated", "missing"])
@pytest.mark.parametrize("where", ["target", "reference"])
def test_bad_quality_is_not_filtered(industrial, quality, where):
    if where == "target": value = replace(industrial, target=replace(industrial.target, quality=quality))
    else: value = replace(industrial, references=(replace(industrial.references[0], quality=quality), *industrial.references[1:]))
    assert_abstained(value, A.INVALID_QUALITY)


@pytest.mark.parametrize("field,value,code", [("unit", "K", A.UNIT_MISMATCH),
    ("unit", "C", A.UNIT_MISMATCH), ("sensor_type", "vibration", A.SENSOR_TYPE_MISMATCH)])
def test_sensor_metadata_is_not_converted(industrial, field, value, code):
    assert_abstained(replace(industrial, chain=replace(industrial.chain, **{field: value})), code)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("where", ["target", "reference"])
def test_nonfinite_values_abstain(industrial, number, where):
    if where == "target": value = replace(industrial, target=replace(industrial.target, value=number))
    else: value = replace(industrial, references=(replace(industrial.references[0], value=number), *industrial.references[1:]))
    assert_abstained(value, A.INVALID_VALUE)


@pytest.mark.parametrize("field", ["site_company_id", "equipment_site_id", "sensor_equipment_id"])
def test_parent_chain_mismatch_rejected(industrial, field):
    assert_rejected(replace(industrial, chain=replace(industrial.chain, **{field: 999})), R.INCONSISTENT_IDENTITY)


@pytest.mark.parametrize("field", ["company_id", "site_id", "site_company_id", "equipment_id",
    "equipment_site_id", "sensor_id", "sensor_equipment_id"])
@pytest.mark.parametrize("value", [True, 0, -1, 2147483648, "101"])
def test_chain_identifiers_are_strict(industrial, field, value):
    assert_rejected(replace(industrial, chain=replace(industrial.chain, **{field: value})), R.INVALID_IDENTITY)


@pytest.mark.parametrize("where", ["target", "reference"])
def test_measurement_must_belong_to_resolved_sensor(industrial, where):
    if where == "target": value = replace(industrial, target=replace(industrial.target, sensor_id=999))
    else: value = replace(industrial, references=(replace(industrial.references[0], sensor_id=999), *industrial.references[1:]))
    assert_rejected(value, R.INCONSISTENT_IDENTITY)


@pytest.mark.parametrize("field,value", [("id", True), ("id", 0), ("id", "11"), ("sensor_id", False)])
def test_measurement_ids_rejected(industrial, field, value):
    assert_rejected(replace(industrial, target=replace(industrial.target, **{field: value})), R.INVALID_IDENTITY)


@pytest.mark.parametrize("provenance", [None, DeclaredProvenance("", "review", True),
    DeclaredProvenance("source", "", True), DeclaredProvenance("source", "review", None)])
def test_provenance_must_be_explicit(industrial, provenance):
    assert_rejected(replace(industrial, provenance=provenance), R.INVALID_PROVENANCE)


def test_non_synthetic_provenance_is_preserved_not_authenticated(industrial):
    value = replace(industrial, provenance=replace(industrial.provenance, synthetic=False))
    result = evaluate_snapshot(value)
    assert type(result) is Computed and result.details["synthetic"] is False
    assert result.details["provenance"]["verification"] == "declarations_not_authenticated"


@pytest.mark.parametrize("change", ["id", "timestamp", "target_id"])
def test_duplicates_are_not_dropped(industrial, change):
    row = industrial.references[0]
    if change == "id": row = replace(row, id=industrial.references[1].id)
    elif change == "timestamp": row = replace(row, timestamp=industrial.references[1].timestamp)
    else: row = replace(row, id=industrial.target.id)
    assert_abstained(replace(industrial, references=(row, *industrial.references[1:])), A.DUPLICATE_OBSERVATION)


def test_future_reference_is_not_filtered(industrial):
    row = replace(industrial.references[0], timestamp=industrial.target.timestamp + timedelta(seconds=1))
    assert_abstained(replace(industrial, references=(row, *industrial.references[1:])), A.FUTURE_REFERENCE)


def test_extra_reference_is_not_selected_away(industrial):
    row = replace(industrial.references[0], id=12, timestamp=industrial.target.timestamp - timedelta(days=11))
    assert_abstained(replace(industrial, references=(*industrial.references, row)), A.REFERENCE_COUNT_MISMATCH)


def test_zero_std_is_delegated_to_calculator(industrial):
    assert_abstained(replace(industrial, references=tuple(replace(row, value=65) for row in industrial.references)), A.ZERO_STD)


def test_cutoff_and_observation_context(industrial):
    assert_abstained(replace(industrial, event_cutoff=industrial.target.timestamp - timedelta(microseconds=1)), A.TARGET_AFTER_CUTOFF)
    assert_rejected(replace(industrial, observed_at=industrial.event_cutoff - timedelta(seconds=1)), R.INVALID_TIME_CONTEXT)


@pytest.mark.parametrize("field", ["event_cutoff", "observed_at", "target"])
def test_naive_dates_are_not_assigned_a_timezone(industrial, field):
    naive = industrial.target.timestamp.replace(tzinfo=None)
    value = replace(industrial, target=replace(industrial.target, timestamp=naive)) if field == "target" else replace(industrial, **{field: naive})
    assert_rejected(value, R.INVALID_TIMESTAMP)


def test_order_and_offset_normalization_preserve_instant_and_fingerprints(industrial):
    offset = timezone(timedelta(hours=2))
    rows = tuple(replace(row, timestamp=row.timestamp.astimezone(offset)) for row in reversed(industrial.references))
    value = replace(industrial, references=rows, target=replace(industrial.target, timestamp=industrial.target.timestamp.astimezone(offset)),
                    event_cutoff=industrial.event_cutoff.astimezone(offset), observed_at=industrial.observed_at.astimezone(offset))
    assert adapt(value) == adapt(industrial)
    assert evaluate_snapshot(value) == evaluate_snapshot(industrial)
    assert industrial.target.timestamp.microsecond == 123456


@pytest.mark.parametrize("value", [None, {}, object()])
def test_untyped_snapshot_rejected(value):
    assert_rejected(value, R.INVALID_INPUT)


def test_malformed_rows_and_unbounded_history_refuse(industrial):
    assert_rejected(replace(industrial, references=list(industrial.references)), R.INVALID_INPUT)
    assert_rejected(replace(industrial, references=(None,)), R.INVALID_INPUT)
    assert_rejected(replace(industrial, references=industrial.references * 4), R.INPUT_LIMIT)
    assert_rejected(replace(industrial, target=replace(industrial.target, value=True)), R.INVALID_INPUT)
