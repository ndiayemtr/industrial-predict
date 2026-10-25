"""T01–T20: pure P101 contracts; no application, DB or HTTP imports."""

import builtins
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path
import socket
from unittest.mock import patch

import pandas as pd
import pytest

from app.anomaly_detection.p101_canonical import (
    bounded_details, canonical_bytes, instant_datetime, manifest_sha256, utc_instant,
)
from app.anomaly_detection.p101_contracts import Abstained, AbstentionCode as Code, Computed
from app.anomaly_detection.p101_core import evaluate, validate_proposal
from app.anomaly_detection.statistical_detector import StatisticalAnomalyDetector


FIXTURE = Path(__file__).parent / "fixtures" / "p101-temperature-v1.json"
RUN_ID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture(autouse=True)
def no_external_pipeline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network, SQL, artifact load or model training allowed")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"sqlalchemy", "psycopg", "httpx", "requests", "joblib", "sklearn"}:
            return forbidden()
        if name.startswith(("app.core.database", "app.main", "app.services", "app.ml")):
            return forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(builtins, "__import__", guarded_import)


@pytest.fixture
def manifest():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def run(manifest, target="DEMO-M-012", **kwargs):
    day = 11 if target == "DEMO-M-011" else 12
    params = dict(cutoff=f"2026-01-{day:02d}T08:01:00Z",
                  prepared_at="2026-02-01T00:00:00Z", run_id=RUN_ID)
    params.update(kwargs)
    return evaluate(manifest, target, **params)


def abstention(result, code):
    assert isinstance(result, Abstained)
    assert result.code == code
    assert result.prediction is None
    assert result.status == "abstained"
    assert "score" not in asdict(result) and "is_alert" not in asdict(result)


def test_t01_normal_and_exact_fixture(manifest):
    assert len(manifest["observations"]) == 12
    assert [r["value"] for r in manifest["observations"]] == [
        65, 63, 67, 64.5, 65.5, 64.5, 65.5, 65, 65, 65, 65, 70]
    for index, row in enumerate(manifest["observations"], 1):
        assert row["fixture_id"] == f"DEMO-M-{index:03d}"
        assert row["timestamp"] == f"2026-01-{index:02d}T08:00:00Z"
        assert row["available_at"] == f"2026-01-{index:02d}T08:01:00Z"
        assert row["asset"] == manifest["asset"]
        assert row["synthetic"] is True and row["unit"] == "°C" and row["quality"] == "good"
    before = deepcopy(manifest)
    result = run(manifest, "DEMO-M-011")
    assert isinstance(result, Computed)
    assert asdict(result.statistics) == dict(mean=65, sample_std=1, absolute_deviation=0, threshold=3)
    assert result.reference_ids == tuple(f"DEMO-M-{i:03d}" for i in range(1, 11))
    assert result.prediction.score == 0 and result.prediction.is_alert is False
    assert manifest == before


def test_t02_positive_and_reference_independent_methods(manifest):
    result = run(manifest)
    assert isinstance(result, Computed)
    assert result.reference_ids == tuple(f"DEMO-M-{i:03d}" for i in range(2, 12))
    # Both independent reference methods use the actual ten past points, not
    # the current target or two different windows with coincidentally equal stats.
    by_id = {row["fixture_id"]: row for row in manifest["observations"]}
    expected_values = [63, 67, 64.5, 65.5, 64.5, 65.5, 65, 65, 65, 65]
    selected = [by_id[key]["value"] for key in result.reference_ids]
    assert selected == expected_values and len(selected) == 10
    manual_mean = sum(selected) / 10
    manual_std = math.sqrt(sum((v - manual_mean) ** 2 for v in selected) / 9)
    series = pd.Series(selected, dtype=float)
    assert manual_mean == series.mean() == result.statistics.mean == 65
    assert manual_std == series.std(ddof=1) == result.statistics.sample_std == 1
    assert result.statistics.threshold == 3 and result.statistics.absolute_deviation == 5
    assert result.prediction.score == 1 and result.prediction.is_alert is True


def test_t03_negative(manifest):
    manifest["dataset_id"] = "p101-temp-negative-v1"
    manifest["observations"][-1]["value"] = 60
    result = run(manifest)
    assert result.statistics.absolute_deviation == 5
    assert result.prediction.score == 1 and result.prediction.is_alert is True


@pytest.mark.parametrize("value", [62, 68])
def test_t04_exact_threshold(manifest, value):
    manifest["observations"][-1]["value"] = value
    result = run(manifest)
    assert result.statistics.absolute_deviation == result.statistics.threshold == 3
    assert result.prediction.score == 0 and result.prediction.is_alert is False


def test_t05_insufficient_history(manifest):
    for target in manifest["observations"][:10]:
        abstention(run(manifest, target["fixture_id"]), Code.INSUFFICIENT_HISTORY)


@pytest.mark.parametrize("target_value", [65, 70])
def test_t06_constant_reference(manifest, target_value):
    for row in manifest["observations"]:
        row["value"] = 65
    manifest["observations"][-1]["value"] = target_value
    with patch.object(StatisticalAnomalyDetector, "detect", side_effect=AssertionError("No detector")):
        abstention(run(manifest), Code.ZERO_STD)


@pytest.mark.parametrize("position", [1, 11])
@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -float("inf"), "65", True, [], {}])
def test_t07_invalid_values_and_types(manifest, position, value):
    manifest["observations"][position]["value"] = value
    code = Code.INVALID_VALUE if value is None or type(value) is float else Code.INVALID_INPUT
    with patch.object(StatisticalAnomalyDetector, "detect", side_effect=AssertionError("No detector")):
        abstention(run(manifest), code)


def test_t07_missing_value(manifest):
    del manifest["observations"][2]["value"]
    abstention(run(manifest), Code.INVALID_VALUE)


@pytest.mark.parametrize("quality", ["suspect", "estimated", "bad", "missing", "unknown"])
@pytest.mark.parametrize("position", [1, 11])
def test_t08_quality(manifest, quality, position):
    manifest["observations"][position]["quality"] = quality
    abstention(run(manifest), Code.INVALID_QUALITY)


@pytest.mark.parametrize("kind", ["id", "time", "offset", "identical"])
def test_t09_duplicates(manifest, kind):
    row = deepcopy(manifest["observations"][3])
    if kind == "id":
        row["timestamp"] = "2026-01-04T09:00:00Z"
        row["available_at"] = "2026-01-04T09:01:00Z"
    elif kind in ("time", "offset"):
        row["fixture_id"] = "DEMO-M-099"
        if kind == "offset":
            row["timestamp"] = "2026-01-04T09:00:00+01:00"
    manifest["observations"].append(row)
    abstention(run(manifest), Code.DUPLICATE_OBSERVATION)


@pytest.mark.parametrize("kind", ["missing", "shifted"])
def test_t10_gap(manifest, kind):
    if kind == "missing":
        del manifest["observations"][4]
    else:
        manifest["observations"][4]["timestamp"] = "2026-01-05T08:00:01Z"
    abstention(run(manifest), Code.GAP_OR_CADENCE)


@pytest.mark.parametrize("unit", ["°F", "K", "C", "Celsius"])
def test_t11_units(manifest, unit):
    manifest["observations"][2]["unit"] = unit
    abstention(run(manifest), Code.UNIT_MISMATCH)


@pytest.mark.parametrize("field", ["company_id", "site_id", "equipment_id", "sensor_id"])
def test_t12_parent(manifest, field):
    manifest["observations"][2]["asset"][field] = "OTHER-DEMO"
    abstention(run(manifest), Code.INCONSISTENT_PARENT)


def test_t12_non_synthetic(manifest):
    manifest["synthetic"] = False
    abstention(run(manifest), Code.INCONSISTENT_PARENT)


def test_t13_future_invariance(manifest):
    original = run(manifest, "DEMO-M-011")
    manifest["observations"][-1]["value"] = 100000
    extra = deepcopy(manifest["observations"][-1])
    extra.update(fixture_id="DEMO-M-013", timestamp="2026-01-13T08:00:00Z",
                 available_at="2026-01-13T08:01:00Z", value=-10000)
    manifest["observations"].append(extra)
    updated = run(manifest, "DEMO-M-011")
    assert original.statistics == updated.statistics
    assert original.reference_ids == updated.reference_ids
    assert original.reference_sha256 == updated.reference_sha256
    assert original.prediction.score == updated.prediction.score == 0
    assert original.dataset_sha256 != updated.dataset_sha256


def test_t14_late_reference(manifest):
    manifest["observations"][4]["available_at"] = "2026-01-12T08:02:00Z"
    abstention(run(manifest), Code.GAP_OR_CADENCE)
    # Arrival later does not rewrite the earlier decision; a later cutoff
    # creates a new proposal, with this observation now available.
    assert isinstance(run(manifest, cutoff="2026-01-12T08:03:00Z"), Computed)


@pytest.mark.parametrize("cutoff", ["2026-01-12T07:59:00Z", "2026-01-12T08:00:30Z"])
def test_t15_target_unavailable(manifest, cutoff):
    abstention(run(manifest, cutoff=cutoff), Code.TARGET_UNAVAILABLE)


def test_t16_current_point_excluded_and_actual_detector_input(manifest):
    original = run(manifest)
    detector = StatisticalAnomalyDetector.detect
    frames = []

    def inspect(self, frame, **kwargs):
        frames.append(frame.copy())
        return detector(self, frame, **kwargs)

    manifest["observations"][-1]["value"] = 100
    with patch.object(StatisticalAnomalyDetector, "detect", inspect):
        updated = run(manifest)
    assert frames[0].to_dict("list") == {"value": [100.0], "rolling_mean": [65.0], "rolling_std": [1.0]}
    assert original.reference_sha256 == updated.reference_sha256
    assert original.statistics.mean == updated.statistics.mean == 65
    assert original.statistics.sample_std == updated.statistics.sample_std == 1
    assert updated.statistics.absolute_deviation == 35


def test_t17_utc_order_offsets(manifest):
    original = run(manifest)
    for row in manifest["observations"]:
        row["timestamp"] = row["timestamp"].replace("08:00:00Z", "09:00:00.000000+01:00")
        row["available_at"] = row["available_at"].replace("08:01:00Z", "09:01:00+01:00")
    manifest["observations"].reverse()
    updated = run(manifest)
    assert updated == original
    assert utc_instant("2026-01-01T09:00:00.123456+01:00") == "2026-01-01T08:00:00.123456Z"


@pytest.mark.parametrize("timestamp", ["2026-01-05T08:00:00", "2026-01-05T08:00:00.1234567Z", "invalid"])
def test_t17_invalid_time(manifest, timestamp):
    manifest["observations"][4]["timestamp"] = timestamp
    abstention(run(manifest), Code.INVALID_INPUT)


def test_t17_microsecond_cadence(manifest):
    manifest["observations"][4]["timestamp"] = "2026-01-05T08:00:00.000001Z"
    abstention(run(manifest), Code.GAP_OR_CADENCE)


def test_t18_canonical_bytes_and_real_hashes(manifest):
    assert canonical_bytes({"observations": [{"fixture_id": "DEMO-M-001",
        "timestamp": "2026-01-01T09:00:00+01:00", "available_at": "2026-01-01T08:01:00Z",
        "value": 65.0}]}) == (
        b'{"observations":[{"available_at":"2026-01-01T08:01:00.000000Z",'
        b'"fixture_id":"DEMO-M-001","timestamp":"2026-01-01T08:00:00.000000Z","value":"65"}]}')
    first = canonical_bytes(manifest)
    reordered = dict(reversed(list(manifest.items())))
    reordered["observations"] = [dict(reversed(list(row.items())))
                                 for row in reversed(manifest["observations"])]
    reordered["observations"][-1]["value"] = 65.0
    assert canonical_bytes(reordered) == first
    assert not first.startswith(b"\xef\xbb\xbf")
    result = run(manifest)
    assert result.dataset_sha256 == hashlib.sha256(first).hexdigest()
    assert result.dataset_sha256 == manifest_sha256(manifest)
    normalized = json.loads(first)
    reference = {"observations": normalized["observations"][1:11]}
    # Independent JSON encoding of the ten canonical past rows.
    ref_bytes = json.dumps(reference, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert result.reference_sha256 == hashlib.sha256(ref_bytes).hexdigest()
    manifest["observations"][4]["value"] += 0.5
    assert manifest_sha256(manifest) != result.dataset_sha256


def test_t19_logical_proposal_and_json_limits(manifest):
    result = run(manifest)
    proposal = result.prediction
    assert not {"id", "created_at", "equipment_id", "sensor_id", "measurement_id"} & asdict(proposal).keys()
    assert proposal.model_name == "statistical_deviation" and proposal.model_version == "p101-stat-v1"
    assert proposal.level is proposal.horizon_hours is None
    assert proposal.predicted_at == "2026-01-12T08:00:00.000000Z"
    assert proposal.details["producer"] == {"method_version": "p101-stat-v1",
        "code_revision": None, "revision_status": "pending_commit"}
    assert len(proposal.details_json.encode()) <= 6000
    validate_proposal(proposal)
    d = proposal.details
    d["unknown"] = "value"
    assert "unknown" not in proposal.details
    with pytest.raises(ValueError):
        validate_proposal(replace(proposal, details_json=json.dumps(d)))
    with pytest.raises(ValueError):
        validate_proposal(replace(proposal, score=0))
    for invalid in ({"x": "x" * 241}, {"x": float("inf")}, {str(i): "x"*240 for i in range(30)},
                    {"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}}):
        with pytest.raises(ValueError):
            bounded_details(invalid)
    for context in ({"run_id": "not-a-uuid"}, {"code_revision": "not-a-sha"},
                    {"prepared_at": "2025-01-01T00:00:00Z"}):
        abstention(run(manifest, **context), Code.INVALID_INPUT)
    supplied = run(manifest, code_revision="a" * 40)
    assert supplied.prediction.details["producer"]["revision_status"] == "requires_validation"


@pytest.mark.parametrize("value,alert", [(math.nextafter(68.0, -math.inf), False),
    (68.0, False), (math.nextafter(68.0, math.inf), True),
    (math.nextafter(62.0, math.inf), False), (62.0, False),
    (math.nextafter(62.0, -math.inf), True)])
def test_t20_numeric_boundary(manifest, value, alert):
    manifest["observations"][-1]["value"] = value
    result = run(manifest)
    assert result.statistics.mean == 65 and result.statistics.sample_std == 1
    assert result.prediction.is_alert is alert


def test_closed_codes_priorities_and_nonfinite_statistic(manifest):
    assert len(Code) == 11
    manifest["observations"][2]["unit"] = "K"
    manifest["observations"][2]["quality"] = "bad"
    abstention(run(manifest), Code.UNIT_MISMATCH)
    manifest["observations"][2]["asset"]["company_id"] = "OTHER"
    abstention(run(manifest), Code.INCONSISTENT_PARENT)
    manifest["observations"][2]["value"] = True
    abstention(run(manifest), Code.INVALID_INPUT)


def test_nonfinite_statistic_and_no_detector(manifest):
    for index, row in enumerate(manifest["observations"]):
        row["value"] = 1e308 if index % 2 else -1e308
    with patch.object(StatisticalAnomalyDetector, "detect", side_effect=AssertionError("No detector")):
        abstention(run(manifest), Code.NONFINITE_STATISTIC)


def test_corrupt_global_manifest_abstains_before_detector(manifest):
    manifest["observations"][-1]["value"] = float("nan")
    with patch.object(StatisticalAnomalyDetector, "detect", side_effect=AssertionError("No detector")):
        abstention(run(manifest, "DEMO-M-011"), Code.INVALID_INPUT)


def test_date_underflow_is_invalid_input(manifest):
    target = manifest["observations"][-1]
    target["timestamp"] = "0001-01-01T08:00:00Z"
    target["available_at"] = "0001-01-01T08:01:00Z"
    abstention(run(manifest), Code.INVALID_INPUT)


def test_details_reject_tampered_reference_and_nonobject(manifest):
    proposal = run(manifest).prediction
    details = proposal.details
    details["reference"]["observations"][0]["value"] += 1
    with pytest.raises(ValueError, match="fingerprint"):
        validate_proposal(replace(proposal, details_json=json.dumps(details)))
    for malformed in ("null", "[]", "bad json"):
        with pytest.raises(ValueError):
            validate_proposal(replace(proposal, details_json=malformed))
