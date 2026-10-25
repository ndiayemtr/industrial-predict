"""Pure synthetic P101 evaluation. No database, HTTP, training or artifact store."""

from datetime import timedelta
import math
import re
import statistics
import unicodedata
from uuid import UUID

import pandas as pd

from app.anomaly_detection.p101_canonical import (
    bounded_details, finite_value, instant_datetime, manifest_sha256, utc_instant,
)
from app.anomaly_detection.p101_contracts import (
    ASSET, METHOD_VERSION, Abstained, AbstentionCode as Code, Computed,
    LogicalPrediction, Observation, Result, Statistics,
)
from app.anomaly_detection.statistical_detector import StatisticalAnomalyDetector


ROOT_FIELDS = {"schema_version", "dataset_id", "synthetic", "asset", "observations"}
ROW_FIELDS = {"fixture_id", "timestamp", "available_at", "asset", "synthetic",
              "unit", "quality", "value"}
DETAIL_FIELDS = {"schema_version", "synthetic", "run_id", "reason", "producer",
                 "asset", "dataset", "target", "reference", "statistics",
                 "cutoff_utc", "prepared_at"}


def _asset(value):
    if (not isinstance(value, dict) or set(value) != set(ASSET)
            or any(not isinstance(v, str) or not 1 <= len(v) <= 64
                   for v in value.values())):
        raise ValueError("Invalid industrial identity")
    return tuple(sorted(value.items()))


def _parse(manifest):
    if not isinstance(manifest, dict) or set(manifest) != ROOT_FIELDS:
        raise ValueError("Invalid manifest fields")
    if manifest["schema_version"] != "p101-temperature-fixture-v1":
        raise ValueError("Unsupported manifest schema")
    if (not isinstance(manifest["dataset_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", manifest["dataset_id"])):
        raise ValueError("Invalid dataset identity")
    if type(manifest["synthetic"]) is not bool:
        raise ValueError("Invalid synthetic marker")
    _asset(manifest["asset"])
    if not isinstance(manifest["observations"], list) or not manifest["observations"]:
        raise ValueError("Observations are required")
    rows = []
    for row in manifest["observations"]:
        if (not isinstance(row, dict) or set(row) - ROW_FIELDS
                or ROW_FIELDS - {"value"} - set(row)):
            raise ValueError("Invalid observation fields")
        if (not isinstance(row["fixture_id"], str)
                or not re.fullmatch(r"DEMO-M-\d{3,6}", row["fixture_id"])):
            raise ValueError("Invalid observation identity")
        if type(row["synthetic"]) is not bool:
            raise ValueError("Invalid synthetic marker")
        if any(not isinstance(row[key], str) or not 1 <= len(row[key]) <= 64
               for key in ("unit", "quality")):
            raise ValueError("Invalid observation text")
        value = row.get("value")
        if value is not None and type(value) not in (int, float):
            raise ValueError("Temperature must be numeric, not a boolean or string")
        timestamp = utc_instant(row["timestamp"])
        available = utc_instant(row["available_at"])
        if available < timestamp:
            raise ValueError("Availability cannot precede observation time")
        rows.append(Observation(row["fixture_id"], timestamp, available,
                                _asset(row["asset"]), row["synthetic"],
                                unicodedata.normalize("NFC", row["unit"]),
                                row["quality"], value))
    return tuple(rows)


def _observation_dict(row):
    return {"fixture_id": row.fixture_id, "timestamp": row.timestamp,
            "available_at": row.available_at, "asset": dict(row.asset),
            "synthetic": row.synthetic, "unit": row.unit, "quality": row.quality,
            "value": row.value}


def validate_proposal(prediction: LogicalPrediction) -> None:
    """Validate the logical boundary. SQL DTO completion belongs to ML 4."""
    try:
        d = prediction.details
    except (ValueError, TypeError) as exc:
        raise ValueError("Details must be a JSON object") from exc
    if not isinstance(d, dict) or set(d) != DETAIL_FIELDS:
        raise ValueError("Unknown or missing details fields")
    closed = {
        "producer": {"method_version", "code_revision", "revision_status"},
        "asset": set(ASSET), "dataset": {"id", "sha256"},
        "target": {"fixture_id", "timestamp", "available_at", "value", "unit", "quality"},
        "reference": {"count", "ddof", "cadence_seconds", "start_at", "end_at",
                      "sha256", "observations"},
        "statistics": {"mean", "sample_std", "absolute_deviation", "threshold",
                       "multiplier", "comparison", "score_semantics"},
    }
    for key, fields in closed.items():
        if not isinstance(d[key], dict) or set(d[key]) != fields:
            raise ValueError("Invalid nested details fields")
    if (prediction.prediction_type != "anomaly"
            or prediction.model_name != "statistical_deviation"
            or prediction.model_version != METHOD_VERSION
            or type(prediction.score) is not int or prediction.score not in (0, 1)
            or type(prediction.is_alert) is not bool
            or prediction.is_alert != bool(prediction.score)
            or prediction.level is not None or prediction.horizon_hours is not None
            or d["schema_version"] != "p101-anomaly-details-v1"
            or d["synthetic"] is not True or d["asset"] != ASSET
            or prediction.equipment_fixture_id != ASSET["equipment_id"]
            or prediction.sensor_fixture_id != ASSET["sensor_id"]
            or prediction.measurement_fixture_id != d["target"]["fixture_id"]
            or prediction.predicted_at != d["target"]["timestamp"]
            or d["producer"]["method_version"] != METHOD_VERSION):
        raise ValueError("Inconsistent logical prediction")
    if str(UUID(d["run_id"])) != d["run_id"]:
        raise ValueError("Invalid run identity")
    revision = d["producer"]["code_revision"]
    expected_status = "pending_commit" if revision is None else "requires_validation"
    if (d["producer"]["revision_status"] != expected_status
            or revision is not None and not re.fullmatch(r"[0-9a-f]{40}", revision)):
        raise ValueError("Invalid code provenance")
    for digest in (d["dataset"]["sha256"], d["reference"]["sha256"]):
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid digest")
    if (not isinstance(d["dataset"]["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", d["dataset"]["id"])):
        raise ValueError("Invalid dataset identity")
    ref = d["reference"]
    if (ref["count"], ref["ddof"], ref["cadence_seconds"]) != (10, 1, 86400):
        raise ValueError("Invalid reference parameters")
    if not isinstance(ref["observations"], list) or len(ref["observations"]) != 10:
        raise ValueError("Exactly ten references required")
    target_time = instant_datetime(prediction.predicted_at)
    for position, row in enumerate(ref["observations"]):
        if not isinstance(row, dict) or set(row) != {"fixture_id", "timestamp", "available_at", "value", "quality"}:
            raise ValueError("Invalid reference observation")
        if (not isinstance(row["fixture_id"], str)
                or not re.fullmatch(r"DEMO-M-\d{3,6}", row["fixture_id"])
                or utc_instant(row["timestamp"]) != row["timestamp"]
                or utc_instant(row["available_at"]) != row["available_at"]
                or instant_datetime(row["timestamp"]) != target_time - timedelta(days=10-position)
                or not finite_value(row["value"]) or row["quality"] != "good"
                or row["available_at"] > d["cutoff_utc"]
                or row["available_at"] < row["timestamp"]):
            raise ValueError("Invalid reference chronology or value")
    if (len({row["fixture_id"] for row in ref["observations"]}) != 10
            or d["target"]["fixture_id"] in {row["fixture_id"] for row in ref["observations"]}
            or ref["start_at"] != ref["observations"][0]["timestamp"]
            or ref["end_at"] != ref["observations"][-1]["timestamp"]):
        raise ValueError("Invalid reference identity")
    for value in (prediction.predicted_at, d["cutoff_utc"], d["prepared_at"],
                  d["target"]["available_at"]):
        if utc_instant(value) != value:
            raise ValueError("Canonical UTC required")
    t = d["target"]
    s = d["statistics"]
    if (not isinstance(t["fixture_id"], str)
            or not re.fullmatch(r"DEMO-M-\d{3,6}", t["fixture_id"])
            or not finite_value(t["value"]) or t["unit"] != "°C" or t["quality"] != "good"
            or t["timestamp"] > t["available_at"] or t["available_at"] > d["cutoff_utc"]
            or d["prepared_at"] < d["cutoff_utc"]
            or any(not finite_value(s[key]) for key in
                   ("mean", "sample_std", "absolute_deviation", "threshold"))
            or s["sample_std"] <= 0 or s["threshold"] != 3 * s["sample_std"]
            or s["absolute_deviation"] != abs(t["value"] - s["mean"])
            or prediction.is_alert != (s["absolute_deviation"] > s["threshold"])
            or s["multiplier"] != 3 or s["comparison"] != "absolute_deviation>threshold"
            or s["score_semantics"] != "binary_indicator_non_probabilistic"):
        raise ValueError("Invalid statistics or decision")
    expected_reason = (
        "Démonstration synthétique : "
        + ("dépassement" if prediction.is_alert else "absence de dépassement")
        + " statistique, indicateur binaire sans probabilité de panne."
    )
    if d["reason"] != expected_reason:
        raise ValueError("Invalid reason")
    reference_payload = {"observations": [dict(row, asset=dict(ASSET), synthetic=True, unit="°C")
                                           for row in ref["observations"]]}
    if manifest_sha256(reference_payload) != ref["sha256"]:
        raise ValueError("Reference fingerprint does not match observations")
    reference_values = [float(row["value"]) for row in ref["observations"]]
    if (s["mean"] != statistics.mean(reference_values)
            or s["sample_std"] != math.sqrt(statistics.variance(reference_values))):
        raise ValueError("Statistics do not match the ten reference observations")
    bounded_details(d)


def evaluate(manifest: dict, target_id: str, *, cutoff: str, prepared_at: str,
             run_id: str, code_revision: str | None = None) -> Result:
    """Evaluate one synthetic target at an explicit knowledge cutoff.

    No wall clock, filesystem or Git discovery. A supplied revision remains
    unverified; a missing revision is explicitly pending the future code commit.
    """
    cutoff_utc = None

    def abstain(code, rows=()):
        return Abstained(code, target_id if isinstance(target_id, str) else "", cutoff_utc,
                         tuple(row.fixture_id for row in rows),
                         f"Calcul P101 indisponible : {code.value}.")

    try:
        cutoff_utc = utc_instant(cutoff)
        prepared_utc = utc_instant(prepared_at)
        if prepared_utc < cutoff_utc or str(UUID(run_id)) != run_id:
            raise ValueError("Invalid preparation context")
        if code_revision is not None and not re.fullmatch(r"[0-9a-f]{40}", code_revision):
            raise ValueError("Invalid revision")
        rows = _parse(manifest)
        targets = [row for row in rows if row.fixture_id == target_id]
        if not targets:
            raise ValueError("Target absent")
    except (ValueError, TypeError, KeyError, OverflowError):
        return abstain(Code.INVALID_INPUT)

    target = targets[0]
    target_time = instant_datetime(target.timestamp)
    try:
        start = utc_instant((target_time - timedelta(days=10)).isoformat())
    except (ValueError, OverflowError):
        return abstain(Code.INVALID_INPUT)
    # Only knowledge available at C may affect data validation of references.
    # Keep every occurrence of the target id to expose target identity conflicts.
    useful = [row for row in rows if row.fixture_id == target_id or
              start <= row.timestamp <= target.timestamp and row.available_at <= cutoff_utc]
    if (manifest["synthetic"] is not True or manifest["asset"] != ASSET
            or any(not row.synthetic or dict(row.asset) != ASSET for row in useful)):
        return abstain(Code.INCONSISTENT_PARENT, useful)
    if any(row.unit != "°C" for row in useful):
        return abstain(Code.UNIT_MISMATCH, useful)
    if (len({row.fixture_id for row in useful}) != len(useful)
            or len({row.timestamp for row in useful}) != len(useful)):
        return abstain(Code.DUPLICATE_OBSERVATION, useful)
    if target.timestamp > cutoff_utc or target.available_at > cutoff_utc:
        return abstain(Code.TARGET_UNAVAILABLE, (target,))

    available_past = [row for row in rows if row.timestamp < target.timestamp
                      and row.available_at <= cutoff_utc]
    reference = sorted((row for row in useful if row.timestamp < target.timestamp),
                       key=lambda row: row.timestamp)
    # Insufficient startup history is different from a missing interior slot.
    known_start = min((row.timestamp for row in rows if row.timestamp < target.timestamp
                       and row.available_at <= cutoff_utc), default=target.timestamp)
    if len(available_past) < 10 and known_start > start:
        return abstain(Code.INSUFFICIENT_HISTORY, reference)
    expected = [utc_instant((target_time - timedelta(days=day)).isoformat())
                for day in range(10, 0, -1)]
    if (target_time.hour, target_time.minute, target_time.second, target_time.microsecond) != (8, 0, 0, 0):
        return abstain(Code.GAP_OR_CADENCE, (target,))
    if [row.timestamp for row in reference] != expected:
        return abstain(Code.GAP_OR_CADENCE, reference)
    if any(not finite_value(row.value) for row in (*reference, target)):
        return abstain(Code.INVALID_VALUE, (*reference, target))
    if any(row.quality != "good" for row in (*reference, target)):
        return abstain(Code.INVALID_QUALITY, (*reference, target))
    try:
        values = [float(row.value) for row in reference]
        mean = statistics.mean(values)
        # Compute variance without the optional floating xbar path: extreme
        # finite inputs can otherwise trigger an internal statistics error.
        variance = statistics.variance(values)
        if not math.isfinite(variance):
            return abstain(Code.NONFINITE_STATISTIC, reference)
        std = math.sqrt(variance)
        deviation = abs(float(target.value) - mean)
        threshold = 3 * std
    except (OverflowError, ValueError):
        return abstain(Code.NONFINITE_STATISTIC, reference)
    if std == 0:
        return abstain(Code.ZERO_STD, reference)
    if not all(math.isfinite(value) for value in (mean, std, deviation, threshold)):
        return abstain(Code.NONFINITE_STATISTIC, reference)

    # Hash the complete manifest, not just the useful subset. Invalid unrelated
    # data cannot be given a fictitious canonical digest.
    try:
        dataset_digest = manifest_sha256(manifest)
        reference_digest = manifest_sha256({"observations": [
            _observation_dict(row) for row in reference]})
    except (ValueError, TypeError, OverflowError):
        return abstain(Code.INVALID_INPUT)
    detected = StatisticalAnomalyDetector().detect(pd.DataFrame({
        "value": [float(target.value)], "rolling_mean": [mean], "rolling_std": [std],
    }), threshold_std=3.0)
    alert = bool(detected.iloc[0]["statistical_anomaly"])
    details = {
        "schema_version": "p101-anomaly-details-v1", "synthetic": True,
        "run_id": run_id,
        "reason": "Démonstration synthétique : "
                  + ("dépassement" if alert else "absence de dépassement")
                  + " statistique, indicateur binaire sans probabilité de panne.",
        "producer": {"method_version": METHOD_VERSION, "code_revision": code_revision,
                     "revision_status": "pending_commit" if code_revision is None else "requires_validation"},
        "asset": dict(ASSET),
        "dataset": {"id": manifest["dataset_id"], "sha256": dataset_digest},
        "target": {"fixture_id": target.fixture_id, "timestamp": target.timestamp,
                   "available_at": target.available_at, "value": target.value,
                   "unit": target.unit, "quality": target.quality},
        "reference": {"count": 10, "ddof": 1, "cadence_seconds": 86400,
                      "start_at": reference[0].timestamp, "end_at": reference[-1].timestamp,
                      "sha256": reference_digest,
                      "observations": [{"fixture_id": row.fixture_id,
                                        "timestamp": row.timestamp, "available_at": row.available_at,
                                        "value": row.value, "quality": row.quality} for row in reference]},
        "statistics": {"mean": mean, "sample_std": std, "absolute_deviation": deviation,
                       "threshold": threshold, "multiplier": 3,
                       "comparison": "absolute_deviation>threshold",
                       "score_semantics": "binary_indicator_non_probabilistic"},
        "cutoff_utc": cutoff_utc, "prepared_at": prepared_utc,
    }
    proposal = LogicalPrediction(ASSET["equipment_id"], ASSET["sensor_id"],
                                 target.fixture_id, target.timestamp, int(alert), alert,
                                 bounded_details(details))
    validate_proposal(proposal)
    return Computed(proposal, tuple(row.fixture_id for row in reference),
                    Statistics(mean, std, deviation, threshold), dataset_digest, reference_digest)
