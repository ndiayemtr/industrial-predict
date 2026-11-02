"""Pure evaluation of an explicitly observed snapshot; no SQL or authorization.

Statistics supplies reference mean/sample deviation. The historical detector is
the sole implementation of threshold, absolute deviation and alert comparison.
No clock, Git lookup, environment configuration, destination or available_at is
discovered or invented here. Rejection is not an authorization decision.
"""

from dataclasses import asdict
import statistics

import pandas as pd

from app.anomaly_detection.p101_canonical import finite_value
from app.anomaly_detection.statistical_detector import StatisticalAnomalyDetector
from app.p101_dev.canonical import encode_details
from app.p101_dev.contracts import (
    AVAILABILITY_LIMIT, DETAIL_SCHEMA, MODEL_NAME, MODEL_VERSION,
    Abstained, AbstentionCode as A, Computed, EvaluationInput,
    PreparedEvaluation, ReferenceStatistics, Rejected, RejectionCode as R, Result,
)
from app.p101_dev.preparation import prepare


def _observation(row):
    return {key: getattr(row, key) for key in ("measurement_id", "timestamp", "value", "quality", "unit")}


def evaluate(value: EvaluationInput) -> Result:
    prepared = prepare(value)
    if type(prepared) is not PreparedEvaluation:
        return prepared
    value = prepared.value

    def abstain(code):
        return Abstained(code, value.target.measurement_id, len(value.references),
                         tuple(row.measurement_id for row in value.references))

    try:
        values = [float(row.value) for row in value.references]
        mean, std = statistics.mean(values), statistics.stdev(values)
    except (ValueError, OverflowError, statistics.StatisticsError):
        return abstain(A.NONFINITE_STATISTIC)
    if not finite_value(mean) or not finite_value(std):
        return abstain(A.NONFINITE_STATISTIC)
    if std == 0:
        return abstain(A.ZERO_STD)
    detected = StatisticalAnomalyDetector().detect(pd.DataFrame({
        "value": [float(value.target.value)], "rolling_mean": [mean], "rolling_std": [std],
    }), threshold_std=float(value.policy.multiplier)).iloc[0]
    deviation, threshold = float(detected["statistical_deviation"]), float(detected["statistical_threshold"])
    if not finite_value(deviation) or not finite_value(threshold):
        return abstain(A.NONFINITE_STATISTIC)
    alert = bool(detected["statistical_anomaly"])
    summary = ReferenceStatistics(mean, std, deviation, threshold)
    details = {
        "schema_version": DETAIL_SCHEMA,
        "synthetic": value.provenance.synthetic,
        "model": {"name": MODEL_NAME, "version": MODEL_VERSION},
        "asset": asdict(value.asset),
        "target": _observation(value.target),
        "reference": {"count": 10, "observations": [_observation(row) for row in value.references]},
        "policy": asdict(value.policy),
        "statistics": {**asdict(summary), "comparison": "absolute_deviation>threshold",
                       "score_semantics": "binary_indicator_non_probabilistic"},
        "availability": {"mode": "snapshot_only", "event_cutoff_utc": value.event_cutoff_utc,
                         "snapshot_observed_at": value.snapshot_observed_at,
                         "historical_availability_attested": False, "limitation": AVAILABILITY_LIMIT},
        "provenance": {**asdict(value.provenance),
                       "evidence": [asdict(item) for item in value.provenance.evidence],
                       "verification": "declarations_not_authenticated"},
        "input_sha256": prepared.input_sha256,
        "reason": "Retrospective statistical deviation; binary indicator, not a failure probability.",
    }
    try:
        encoded, digest = encode_details(details)
    except (ValueError, TypeError, OverflowError, RecursionError):
        return Rejected(R.JSON_LIMIT, "details")
    return Computed(value.asset, value.target, value.references, value.policy, value.provenance,
                    int(alert), alert, summary, prepared.input_sha256, encoded, digest)
