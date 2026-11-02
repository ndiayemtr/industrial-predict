"""Constructed snapshots only. No SQL fixtures, manifests, services or training."""

import ast
import builtins
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import socket

import pandas as pd
import pytest

from app.anomaly_detection.statistical_detector import StatisticalAnomalyDetector
from app.p101_dev.canonical import encode_details
from app.p101_dev.contracts import (
    Abstained, AbstentionCode as A, AssetIdentity, Computed, DeclaredProvenance,
    EvaluationInput, EvidenceReference, Measurement, Rejected, RejectionCode as R,
    StatisticalPolicy,
)
from app.p101_dev.evaluation import evaluate


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    original = builtins.__import__

    def forbidden(*a, **k):
        pytest.fail("Pure DEV evaluation must not access external infrastructure")

    def guarded(name, *a, **k):
        if name.split(".")[0] in {"sqlalchemy", "psycopg", "httpx", "requests", "joblib", "sklearn"}:
            forbidden()
        if name.startswith(("app.core", "app.main", "app.models", "app.services", "app.repositories",
                            "app.p101_local_demo", "app.p101_postgres", "app.anomaly_detection.p101_core")):
            forbidden()
        return original(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.fixture
def snapshot_input():
    asset = AssetIdentity(101, 202, 303, 404)
    time = datetime(2026, 4, 11, 13, 47, 2, 123456, tzinfo=timezone.utc)
    values = (65, 63, 67, 64.5, 65.5, 64.5, 65.5, 65, 65, 65)
    refs = tuple(Measurement(i + 1, asset, (time - timedelta(days=10-i)).isoformat(),
                             value, "good", "°C") for i, value in enumerate(values))
    target = Measurement(11, asset, time.isoformat(), 65, "good", "°C")
    return EvaluationInput(asset, "temperature", target, refs, time.isoformat(),
                           (time + timedelta(days=5)).isoformat(),
                           DeclaredProvenance("constructed-test-data", "test-review-1", True))


def abstained(value, code):
    result = evaluate(value)
    assert type(result) is Abstained and result.status == "abstained" and result.code is code
    assert result.prediction is None and not hasattr(result, "score") and not hasattr(result, "is_alert")
    assert len(result.affected_ids) <= 11 and len(result.diagnostic) <= 240
    return result


def rejected(value, code):
    result = evaluate(value)
    assert type(result) is Rejected and result.status == "rejected" and result.code is code
    assert not hasattr(result, "score") and not hasattr(result, "is_alert")
    assert len(result.field) <= 120
    return result


@pytest.mark.parametrize("target,score", [(65, 0), (70, 1), (68, 0), (68.000001, 1), (62, 0), (61.999999, 1)])
def test_binary_result_and_strict_threshold(snapshot_input, target, score):
    value = replace(snapshot_input, target=replace(snapshot_input.target, value=target))
    before = deepcopy(value)
    result = evaluate(value)
    assert type(result) is Computed and result.status == "computed"
    assert result.score == score and type(result.score) is int and result.is_alert is bool(score)
    assert result.statistics.mean == 65 and result.statistics.sample_std == 1
    assert result.statistics.threshold == 3 and result.statistics.absolute_deviation == abs(target - 65)
    assert result.model_name == "statistical_deviation" and result.model_version == "p101-dev-stat-v1"
    assert result.details["schema_version"] == "p101-dev-anomaly-details-v1"
    assert result.reference_ids == tuple(range(1, 11)) and result.target.measurement_id == 11
    assert value == before


def test_existing_detector_receives_reference_only_statistics(snapshot_input, monkeypatch):
    original = StatisticalAnomalyDetector.detect
    captured = []

    def capture(self, dataframe, **kwargs):
        captured.append((dataframe.copy(), kwargs))
        return original(self, dataframe, **kwargs)

    monkeypatch.setattr(StatisticalAnomalyDetector, "detect", capture)
    result = evaluate(replace(snapshot_input, target=replace(snapshot_input.target, value=1000)))
    assert type(result) is Computed and len(captured) == 1
    pd.testing.assert_frame_equal(captured[0][0], pd.DataFrame({
        "value": [1000.0], "rolling_mean": [65.0], "rolling_std": [1.0],
    }))
    assert captured[0][1] == {"threshold_std": 3.0}


@pytest.mark.parametrize("count", [0, 1, 9])
def test_insufficient_history_never_filled(snapshot_input, count):
    result = abstained(replace(snapshot_input, references=snapshot_input.references[:count]), A.INSUFFICIENT_HISTORY)
    assert result.reference_count == count


def test_extra_reference_is_not_silently_dropped(snapshot_input):
    extra = replace(snapshot_input.references[0], measurement_id=12, timestamp="2026-03-31T13:47:02.123456Z")
    abstained(replace(snapshot_input, references=(extra, *snapshot_input.references)), A.REFERENCE_COUNT_MISMATCH)


@pytest.mark.parametrize("change", ["id", "timestamp", "target_id", "offset_duplicate"])
def test_duplicates_are_explicit(snapshot_input, change):
    refs = list(snapshot_input.references)
    if change == "id": refs[1] = replace(refs[1], measurement_id=refs[0].measurement_id)
    elif change == "timestamp": refs[1] = replace(refs[1], timestamp=refs[0].timestamp)
    elif change == "target_id": refs[0] = replace(refs[0], measurement_id=snapshot_input.target.measurement_id)
    else:
        shifted = datetime.fromisoformat(refs[0].timestamp).astimezone(timezone(timedelta(hours=5, minutes=30)))
        refs[1] = replace(refs[1], timestamp=shifted.isoformat())
    abstained(replace(snapshot_input, references=tuple(refs)), A.DUPLICATE_OBSERVATION)


@pytest.mark.parametrize("delta", [timedelta(seconds=1), timedelta(days=1)])
def test_future_reference_is_not_filtered(snapshot_input, delta):
    future = (datetime.fromisoformat(snapshot_input.target.timestamp) + delta).isoformat()
    refs = (*snapshot_input.references[:-1], replace(snapshot_input.references[-1], timestamp=future))
    abstained(replace(snapshot_input, references=refs), A.FUTURE_REFERENCE)


@pytest.mark.parametrize("delta", [timedelta(microseconds=1), timedelta(seconds=1), timedelta(days=1)])
def test_exact_cadence_no_resampling(snapshot_input, delta):
    row = snapshot_input.references[0]
    changed = replace(row, timestamp=(datetime.fromisoformat(row.timestamp) - delta).isoformat())
    abstained(replace(snapshot_input, references=(changed, *snapshot_input.references[1:])), A.GAP_OR_CADENCE)


@pytest.mark.parametrize("where", ["target", "reference"])
@pytest.mark.parametrize("field,value,code", [
    ("quality", "suspect", A.INVALID_QUALITY), ("quality", "bad", A.INVALID_QUALITY),
    ("quality", "estimated", A.INVALID_QUALITY), ("unit", "C", A.UNIT_MISMATCH),
    ("unit", "°F", A.UNIT_MISMATCH), ("value", float("nan"), A.INVALID_VALUE),
    ("value", float("inf"), A.INVALID_VALUE), ("value", float("-inf"), A.INVALID_VALUE),
    ("value", 10**400, A.INVALID_VALUE),
])
def test_incompatible_observation_is_not_discarded(snapshot_input, where, field, value, code):
    if where == "target": snapshot_input = replace(snapshot_input, target=replace(snapshot_input.target, **{field: value}))
    else: snapshot_input = replace(snapshot_input, references=(replace(snapshot_input.references[0], **{field: value}), *snapshot_input.references[1:]))
    abstained(snapshot_input, code)


def test_constant_history_abstains(snapshot_input):
    abstained(replace(snapshot_input, references=tuple(replace(row, value=65) for row in snapshot_input.references)), A.ZERO_STD)


def test_extreme_finite_values_have_explicit_outcome(snapshot_input):
    refs = tuple(replace(row, value=1e308 if i % 2 else -1e308) for i, row in enumerate(snapshot_input.references))
    abstained(replace(snapshot_input, references=refs), A.NONFINITE_STATISTIC)


def test_sensor_type_and_target_cutoff(snapshot_input):
    abstained(replace(snapshot_input, sensor_type="vibration"), A.SENSOR_TYPE_MISMATCH)
    abstained(replace(snapshot_input, event_cutoff_utc=snapshot_input.references[-1].timestamp), A.TARGET_AFTER_CUTOFF)


def test_offsets_order_and_arbitrary_target_time_are_normalized(snapshot_input):
    shifted = lambda value: datetime.fromisoformat(value).astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()
    reordered = replace(snapshot_input, references=tuple(replace(row, timestamp=shifted(row.timestamp)) for row in reversed(snapshot_input.references)),
                        target=replace(snapshot_input.target, timestamp=shifted(snapshot_input.target.timestamp)),
                        event_cutoff_utc=shifted(snapshot_input.event_cutoff_utc),
                        snapshot_observed_at=shifted(snapshot_input.snapshot_observed_at))
    first, second = evaluate(snapshot_input), evaluate(reordered)
    assert type(first) is Computed and first == second
    assert first.target.timestamp.endswith("13:47:02.123456Z")


@pytest.mark.parametrize("field", ["company_id", "site_id", "equipment_id", "sensor_id"])
def test_every_industrial_identity_is_checked(snapshot_input, field):
    bad_asset = replace(snapshot_input.asset, **{field: 999})
    rejected(replace(snapshot_input, references=(replace(snapshot_input.references[0], asset=bad_asset), *snapshot_input.references[1:])),
             R.INCONSISTENT_IDENTITY)


@pytest.mark.parametrize("value", [0, -1, True, "1", 2147483648])
def test_invalid_identity_never_coerced(snapshot_input, value):
    rejected(replace(snapshot_input, asset=replace(snapshot_input.asset, company_id=value)), R.INVALID_IDENTITY)
    rejected(replace(snapshot_input, target=replace(snapshot_input.target, measurement_id=value)), R.INVALID_IDENTITY)


@pytest.mark.parametrize("value", [True, "65", None, [], {}])
def test_malformed_value_is_rejected_not_abstained(snapshot_input, value):
    rejected(replace(snapshot_input, target=replace(snapshot_input.target, value=value)), R.INVALID_INPUT)


@pytest.mark.parametrize("timestamp", ["2026-04-11T13:47:02", "not-a-date", "2026-02-30T00:00:00Z", None])
def test_invalid_timestamps(snapshot_input, timestamp):
    rejected(replace(snapshot_input, target=replace(snapshot_input.target, timestamp=timestamp)), R.INVALID_TIMESTAMP)


def test_invalid_snapshot_time_and_input_shape(snapshot_input):
    rejected(replace(snapshot_input, snapshot_observed_at="2026-01-01T00:00:00Z"), R.INVALID_TIME_CONTEXT)
    rejected(replace(snapshot_input, references=list(snapshot_input.references)), R.INVALID_INPUT)
    rejected(asdict(snapshot_input), R.INVALID_INPUT)
    rejected(None, R.INVALID_INPUT)
    rejected(replace(snapshot_input, references=snapshot_input.references * 4), R.INPUT_LIMIT)


@pytest.mark.parametrize("field,value", [("reference_count", 9), ("cadence_seconds", 3600), ("ddof", True),
                                       ("multiplier", 3.0), ("tolerance_seconds", 1),
                                       ("selection", "latest_ten"), ("availability_mode", "historical")])
def test_historical_policy_cannot_be_silently_relaxed(snapshot_input, field, value):
    rejected(replace(snapshot_input, policy=replace(StatisticalPolicy(), **{field: value})), R.UNSUPPORTED_POLICY)


def test_explicit_provenance_never_inferred_from_environment(snapshot_input):
    provenance = DeclaredProvenance("industrial_predict_dev", "source-review", False,
                                   (EvidenceReference("source_manifest", "reviewable-manifest", "a"*64),), "b"*40)
    result = evaluate(replace(snapshot_input, provenance=provenance))
    assert type(result) is Computed
    assert result.details["synthetic"] is False and result.provenance.synthetic is False
    assert result.details["provenance"]["verification"] == "declarations_not_authenticated"
    availability = result.details["availability"]
    assert availability["mode"] == "snapshot_only" and availability["historical_availability_attested"] is False
    assert availability["event_cutoff_utc"] != availability["snapshot_observed_at"]
    assert "not attested" in availability["limitation"]
    assert "available_at" not in result.details_json
    assert "probability" in result.details["reason"]


@pytest.mark.parametrize("provenance", [None, DeclaredProvenance("", "review", True),
    DeclaredProvenance("source", "review", 1), DeclaredProvenance("source", "review", True, code_revision="bad"),
    DeclaredProvenance("source", "review", True, (EvidenceReference("review", "x", "bad"),)),
    DeclaredProvenance("source", "review", True, (EvidenceReference("cryptographically_verified", "x"),)),
    DeclaredProvenance("source", "review", True, (EvidenceReference("review", "x"),)*2),
    DeclaredProvenance("source", "review", True, tuple(EvidenceReference("review", str(i)) for i in range(5))),
])
def test_invalid_provenance_is_a_contract_rejection(snapshot_input, provenance):
    rejected(replace(snapshot_input, provenance=provenance), R.INVALID_PROVENANCE)


def test_determinism_fingerprints_and_immutable_results(snapshot_input):
    first, second = evaluate(snapshot_input), evaluate(snapshot_input)
    assert type(first) is Computed and first == second
    assert first.details_sha256 == hashlib.sha256(first.details_json.encode("utf-8")).hexdigest()
    assert len(first.input_sha256) == 64
    assert first.input_sha256 != evaluate(replace(snapshot_input, target=replace(snapshot_input.target, value=66))).input_sha256
    assert first.input_sha256 != evaluate(replace(snapshot_input, provenance=replace(snapshot_input.provenance, synthetic=False))).input_sha256
    assert first.input_sha256 != evaluate(replace(snapshot_input, snapshot_observed_at="2026-04-17T00:00:00Z")).input_sha256
    details = first.details
    details["asset"]["company_id"] = 999
    assert first.details["asset"]["company_id"] == 101
    with pytest.raises(FrozenInstanceError): first.score = 1
    with pytest.raises(FrozenInstanceError): first.references[0].value = 999
    assert len(first.details_json.encode("utf-8")) <= 6000
    assert json.loads(first.details_json)["statistics"]["score_semantics"] == "binary_indicator_non_probabilistic"


def test_evidence_order_is_not_semantic(snapshot_input):
    evidence = (EvidenceReference("review", "second"), EvidenceReference("source_manifest", "first"))
    first = evaluate(replace(snapshot_input, provenance=replace(snapshot_input.provenance, evidence=evidence)))
    second = evaluate(replace(snapshot_input, provenance=replace(snapshot_input.provenance, evidence=tuple(reversed(evidence)))))
    assert type(first) is Computed and first == second


@pytest.mark.parametrize("where", ["target", "references", "both"])
def test_equivalent_integer_float_observations_have_identical_canonical_results(snapshot_input, where):
    changed = snapshot_input
    if where in ("target", "both"):
        changed = replace(changed, target=replace(changed.target, value=65.0))
    if where in ("references", "both"):
        changed = replace(changed, references=tuple(replace(row, value=float(row.value)) for row in changed.references))
    first, second = evaluate(snapshot_input), evaluate(changed)
    assert type(first) is Computed and type(second) is Computed
    assert first.input_sha256 == second.input_sha256
    assert first.details_json == second.details_json and first.details_sha256 == second.details_sha256
    assert first.statistics == second.statistics and first.score == second.score and first.is_alert == second.is_alert
    assert first == second
    assert '"value":65.0' not in first.details_json


def test_signed_zeros_have_identical_canonical_results(snapshot_input):
    positive = replace(snapshot_input, target=replace(snapshot_input.target, value=0.0),
                       references=(replace(snapshot_input.references[0], value=0.0), *snapshot_input.references[1:]))
    negative = replace(positive, target=replace(positive.target, value=-0.0),
                       references=(replace(positive.references[0], value=-0.0), *positive.references[1:]))
    first, second = evaluate(positive), evaluate(negative)
    assert type(first) is Computed and first == second
    assert first.input_sha256 == second.input_sha256
    assert first.details_json == second.details_json and first.details_sha256 == second.details_sha256
    assert first.details["target"]["value"] == 0
    assert '"value":-0.0' not in first.details_json and '"value":0.0' not in first.details_json


def test_numeric_representation_does_not_change_abstention(snapshot_input):
    positive = replace(snapshot_input, references=tuple(replace(row, value=0.0) for row in snapshot_input.references))
    negative = replace(positive, references=tuple(replace(row, value=-0.0) for row in positive.references))
    assert abstained(positive, A.ZERO_STD) == abstained(negative, A.ZERO_STD)


def test_fractional_observations_and_statistics_are_preserved(snapshot_input):
    value = replace(snapshot_input, target=replace(snapshot_input.target, value=65.125))
    before = deepcopy(value)
    result = evaluate(value)
    assert type(result) is Computed and value == before
    assert result.target.value == result.details["target"]["value"] == 65.125
    assert result.references[3].value == result.details["reference"]["observations"][3]["value"] == 64.5
    assert result.statistics.mean == 65 and result.statistics.sample_std == 1
    assert result.statistics.absolute_deviation == result.details["statistics"]["absolute_deviation"] == 0.125
    assert result.score == 0 and result.is_alert is False


@pytest.mark.parametrize("value,token", [(65, "65"), (65.0, "65"), (0.0, "0"), (-0.0, "0"),
    (65.125, "65.125"), (-0.125, "-0.125"), (1e-7, "0.0000001"),
    (9007199254740993, "9007199254740993"), (1.2345678901234567, "1.2345678901234567")])
def test_decimal_policy_emits_exact_numeric_tokens(value, token):
    details = {"value": value, "is_alert": False, "optional": None, "text": "65.0"}
    before = deepcopy(details)
    encoded, digest = encode_details(details)
    assert encoded == '{"is_alert":false,"optional":null,"text":"65.0","value":' + token + '}'
    parsed = json.loads(encoded, parse_int=Decimal, parse_float=Decimal)
    assert parsed["value"] == Decimal(str(value))  # Decimal value, not a lossy float roundtrip.
    assert type(json.loads(encoded)["value"]) in (int, float)
    assert digest == hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    assert details == before and parsed["is_alert"] is False and parsed["text"] == "65.0"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_details_do_not_admit_nonfinite_numbers(value):
    with pytest.raises(ValueError): encode_details({"value": value})


def test_expanded_decimal_tokens_still_obey_json_byte_limit():
    # Compact exponent notation fits, expanded canonical decimals do not.
    details = {"values": [1e-300] * 20}
    assert len(json.dumps(details).encode("utf-8")) < 6000
    with pytest.raises(ValueError, match="6000"):
        encode_details(details)


@pytest.mark.parametrize("details", [{"text": "x"*241}, {"text": ["x"*240]*30},
                                     {"a": {"b": {"c": {"d": {"e": {"f": {}}}}}}}, {"x": float("nan")}])
def test_details_reject_bounds_without_truncation(details):
    with pytest.raises(ValueError): encode_details(details)


def test_oversized_provenance_is_rejected_without_echo(snapshot_input):
    canary = "sensitive-canary-"*20
    result = rejected(replace(snapshot_input, provenance=replace(snapshot_input.provenance, source_id=canary)), R.INVALID_PROVENANCE)
    assert "canary" not in repr(result)


def test_package_has_no_runtime_or_io_entrypoints():
    package = Path(__file__).resolve().parents[2]/"backend/app/p101_dev"
    forbidden = {"sqlalchemy", "psycopg", "httpx", "requests", "os", "socket", "pathlib", "subprocess"}
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] not in forbidden for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module.split(".")[0] not in forbidden
                assert not node.module.startswith(("app.p101_local_demo", "app.p101_postgres", "app.core", "app.data_pipeline"))
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                assert name not in {"open", "read_text", "connect", "execute", "commit", "now", "utcnow", "getenv"}
