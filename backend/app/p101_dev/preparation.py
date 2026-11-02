"""Validate every supplied row. No implicit selection, filtering or fabrication.

The future SQL adapter must resolve the industrial chain and supply the target
and exactly ten candidate references. This layer checks declarations only; it
does not authenticate an operator, authorize access or verify a destination.
"""

from dataclasses import fields, replace
from datetime import timedelta
import re
import unicodedata

from app.anomaly_detection.p101_canonical import finite_value, instant_datetime, utc_instant
from app.p101_dev.canonical import input_fingerprint
from app.p101_dev.contracts import (
    Abstained, AbstentionCode as A, AssetIdentity, DeclaredProvenance,
    EvaluationInput, EvidenceReference, Measurement, PreparedEvaluation,
    Rejected, RejectionCode as R, StatisticalPolicy,
)


class _Invalid(ValueError):
    def __init__(self, code, path):
        self.code, self.path = code, path


def _require(condition, code, path):
    if not condition:
        raise _Invalid(code, path)


def _text(value, code, path, limit=120):
    _require(type(value) is str and 0 < len(value) <= limit and value == value.strip()
             and not any(ord(c) < 32 or ord(c) == 127 for c in value), code, path)
    return unicodedata.normalize("NFC", value)


def _asset(value):
    _require(type(value) is AssetIdentity, R.INVALID_IDENTITY, "asset")
    _require(all(type(getattr(value, f.name)) is int and 1 <= getattr(value, f.name) <= 2147483647
                 for f in fields(AssetIdentity)), R.INVALID_IDENTITY, "asset.ids")


def _instant(value, path):
    try:
        return utc_instant(value)
    except (ValueError, TypeError, OverflowError):
        raise _Invalid(R.INVALID_TIMESTAMP, path) from None


def _provenance(value):
    _require(type(value) is DeclaredProvenance, R.INVALID_PROVENANCE, "provenance")
    source = _text(value.source_id, R.INVALID_PROVENANCE, "provenance.source_id")
    declaration = _text(value.declaration_ref, R.INVALID_PROVENANCE, "provenance.declaration_ref")
    _require(type(value.synthetic) is bool, R.INVALID_PROVENANCE, "provenance.synthetic")
    _require(value.code_revision is None or type(value.code_revision) is str
             and re.fullmatch(r"[0-9a-f]{40}", value.code_revision) is not None,
             R.INVALID_PROVENANCE, "provenance.code_revision")
    _require(type(value.evidence) is tuple and len(value.evidence) <= 4,
             R.INVALID_PROVENANCE, "provenance.evidence")
    evidence = []
    for item in value.evidence:
        _require(type(item) is EvidenceReference, R.INVALID_PROVENANCE, "provenance.evidence")
        _require(type(item.kind) is str and item.kind in ("operator_declaration", "source_manifest", "review"),
                 R.INVALID_PROVENANCE, "provenance.evidence.kind")
        reference = _text(item.reference, R.INVALID_PROVENANCE, "provenance.evidence.reference")
        _require(item.sha256 is None or type(item.sha256) is str
                 and re.fullmatch(r"[0-9a-f]{64}", item.sha256) is not None,
                 R.INVALID_PROVENANCE, "provenance.evidence.sha256")
        evidence.append(replace(item, reference=reference))
    # Evidence ordering is not a semantic input. Duplicate declarations are rejected.
    identities = [(item.kind, item.reference) for item in evidence]
    _require(len(set(identities)) == len(identities), R.INVALID_PROVENANCE, "provenance.evidence")
    return replace(value, source_id=source, declaration_ref=declaration,
                   evidence=tuple(sorted(evidence, key=lambda item: (item.kind, item.reference))))


def prepare(value: EvaluationInput) -> PreparedEvaluation | Abstained | Rejected:
    try:
        _require(type(value) is EvaluationInput, R.INVALID_INPUT, "input")
        _asset(value.asset)
        _require(type(value.policy) is StatisticalPolicy and all(
            type(getattr(value.policy, f.name)) is type(getattr(StatisticalPolicy(), f.name))
            and getattr(value.policy, f.name) == getattr(StatisticalPolicy(), f.name)
            for f in fields(StatisticalPolicy)), R.UNSUPPORTED_POLICY, "policy")
        _require(type(value.references) is tuple, R.INVALID_INPUT, "references")
        _require(len(value.references) <= 32, R.INPUT_LIMIT, "references")
        sensor_type = _text(value.sensor_type, R.INVALID_INPUT, "sensor_type")
        provenance = _provenance(value.provenance)
        cutoff = _instant(value.event_cutoff_utc, "event_cutoff_utc")
        observed = _instant(value.snapshot_observed_at, "snapshot_observed_at")
        _require(observed >= cutoff, R.INVALID_TIME_CONTEXT, "snapshot_observed_at")
        rows = []
        for item in (value.target, *value.references):
            _require(type(item) is Measurement, R.INVALID_INPUT, "measurements")
            _asset(item.asset)
            _require(item.asset == value.asset, R.INCONSISTENT_IDENTITY, "measurements.asset")
            _require(type(item.measurement_id) is int and 1 <= item.measurement_id <= 2147483647,
                     R.INVALID_IDENTITY, "measurements.id")
            _require(type(item.value) in (int, float), R.INVALID_INPUT, "measurements.value")
            quality = _text(item.quality, R.INVALID_INPUT, "measurements.quality", 30)
            unit = _text(item.unit, R.INVALID_INPUT, "measurements.unit", 30)
            rows.append(replace(item, timestamp=_instant(item.timestamp, "measurements.timestamp"),
                                quality=quality, unit=unit))
        target, references = rows[0], tuple(sorted(rows[1:], key=lambda row: (row.timestamp, row.measurement_id)))

        def abstain(code, affected=()):
            return Abstained(code, target.measurement_id, len(references),
                             tuple(sorted({row.measurement_id for row in affected}))[:11])

        if sensor_type != "temperature":
            return abstain(A.SENSOR_TYPE_MISMATCH)
        if len({row.measurement_id for row in rows}) != len(rows) or len({row.timestamp for row in rows}) != len(rows):
            return abstain(A.DUPLICATE_OBSERVATION, rows)
        if target.timestamp > cutoff:
            return abstain(A.TARGET_AFTER_CUTOFF, (target,))
        if any(row.timestamp >= target.timestamp for row in references):
            return abstain(A.FUTURE_REFERENCE, references)
        if any(row.unit != "°C" for row in rows):
            return abstain(A.UNIT_MISMATCH, rows)
        if any(row.quality != "good" for row in rows):
            return abstain(A.INVALID_QUALITY, rows)
        if any(not finite_value(row.value) for row in rows):
            return abstain(A.INVALID_VALUE, rows)
        if len(references) < 10:
            return abstain(A.INSUFFICIENT_HISTORY, references)
        if len(references) != 10:
            return abstain(A.REFERENCE_COUNT_MISMATCH, references)
        try:
            target_time = instant_datetime(target.timestamp)
            expected = [target_time - timedelta(days=day) for day in range(10, 0, -1)]
        except (ValueError, OverflowError):
            return Rejected(R.INVALID_TIME_CONTEXT, "target.timestamp")
        if [instant_datetime(row.timestamp) for row in references] != expected:
            return abstain(A.GAP_OR_CADENCE, references)
        normalized = replace(value, sensor_type=sensor_type, target=target, references=references,
                             event_cutoff_utc=cutoff, snapshot_observed_at=observed, provenance=provenance)
        try:
            return PreparedEvaluation(normalized, input_fingerprint(normalized))
        except ValueError:
            return Rejected(R.JSON_LIMIT, "input.projection")
    except _Invalid as exc:
        return Rejected(exc.code, exc.path)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return Rejected(R.INVALID_INPUT, "input")
