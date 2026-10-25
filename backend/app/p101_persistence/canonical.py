"""Canonical key/content encoding; no concurrency guarantee and no I/O."""

from dataclasses import asdict
import hashlib
import json
import re
import unicodedata
from uuid import UUID

from app.anomaly_detection.p101_canonical import decimal_text, utc_instant
from app.p101_persistence.contracts import (
    CanonicalProjection, ContractError, IdempotencyTuple, LogicalIdempotencyKey,
    RetryDisposition, ValidationCode as Code,
)


TIME_FIELDS = {"timestamp", "available_at", "predicted_at", "cutoff_utc", "start_at", "end_at"}


def canonical_projection(value: dict, *, limit: int = 16384) -> CanonicalProjection:
    """Normalize *all* numbers, explicitly including cutoff (unlike manifest JSON).

    Values are strings in the hash projection only. Booleans/null retain their
    JSON types. Reject NFC key collisions, cycles/depth and non-finite values.
    """
    def normalize(item, name=None, depth=0):
        if depth > 6:
            raise ContractError(Code.JSON_LIMIT, "projection.depth")
        if name in TIME_FIELDS:
            return utc_instant(item)
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("JSON keys must be strings")
                normalized_key = unicodedata.normalize("NFC", key)
                if normalized_key in result:
                    raise ValueError("NFC key collision")
                result[normalized_key] = normalize(child, normalized_key, depth + 1)
            return result
        if isinstance(item, (tuple, list)):
            return [normalize(child, depth=depth + 1) for child in item]
        if item is None or type(item) is bool:
            return item
        if type(item) in (int, float):
            return decimal_text(item)
        if isinstance(item, str):
            if len(item) > 240:
                raise ContractError(Code.JSON_LIMIT, "projection.string")
            return unicodedata.normalize("NFC", item)
        raise ValueError("Unsupported JSON type")

    try:
        if not isinstance(value, dict):
            raise ValueError("Object required")
        encoded = json.dumps(normalize(value), ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        raw = encoded.encode("utf-8")
        if len(raw) > limit:
            raise ContractError(Code.JSON_LIMIT, "projection.bytes")
        return CanonicalProjection(encoded, hashlib.sha256(raw).hexdigest())
    except ContractError:
        raise
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise ContractError(Code.INVALID_INPUT, "projection") from exc


def build_key(components: IdempotencyTuple) -> LogicalIdempotencyKey:
    """Encode a versioned identity. Policy/version approval is a separate step."""
    try:
        if type(components) is not IdempotencyTuple:
            raise ValueError("Typed key required")
        if str(UUID(components.instance_uuid)) != components.instance_uuid:
            raise ValueError("Canonical instance UUID required")
        if components.schema_version != "p101-idempotency-v1":
            raise ValueError("Unknown key schema")
        for value, length in ((components.dataset_sha256, 64),
                              (components.reference_sha256, 64), (components.code_revision, 40)):
            if type(value) is not str or re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is None:
                raise ContractError(Code.INVALID_FINGERPRINT, "key.fingerprints")
        if (components.prediction_type != "anomaly" or components.model_name != "statistical_deviation"
                or components.target_id not in ("DEMO-M-011", "DEMO-M-012")
                or not isinstance(components.model_version, str)
                or re.fullmatch(r"p101-stat-v[1-9][0-9]{0,8}", components.model_version) is None
                or components.equipment_code != "MLDEMO-EQ-P101"
                or components.sensor_code != "MLDEMO-SEN-P101-TEMP"
                or components.comparison != "absolute_deviation>threshold"):
            raise ValueError("Invalid key identity")
        for value, expected in ((components.window_count, 10), (components.ddof, 1),
                                (components.cadence_seconds, 86400), (components.multiplier, 3)):
            if type(value) is not int or value != expected:
                raise ValueError("Invalid method parameter")
        if utc_instant(components.cutoff_utc) < utc_instant(components.predicted_at):
            raise ValueError("Cutoff precedes observation")
        projection = canonical_projection(asdict(components), limit=4096)
        return LogicalIdempotencyKey(components, projection)
    except ContractError:
        raise
    except (ValueError, TypeError, AttributeError) as exc:
        raise ContractError(Code.INVALID_INPUT, "key") from exc


def _verify_projection(projection: CanonicalProjection, limit: int) -> None:
    if type(projection) is not CanonicalProjection:
        raise ContractError(Code.INVALID_FINGERPRINT, "projection.type")
    try:
        raw = projection.canonical_json.encode("utf-8")
        if len(raw) > limit or hashlib.sha256(raw).hexdigest() != projection.sha256:
            raise ValueError("Invalid projection digest")
        # A supplied digest does not establish that these bytes are canonical.
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("Duplicate JSON key")
                result[key] = value
            return result
        parsed = json.loads(projection.canonical_json, object_pairs_hook=pairs)
        if canonical_projection(parsed, limit=limit).canonical_json != projection.canonical_json:
            raise ValueError("Noncanonical projection")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ContractError(Code.INVALID_FINGERPRINT, "projection.sha256") from exc


def compare_retry(existing_key: LogicalIdempotencyKey, existing_content: CanonicalProjection,
                  candidate_key: LogicalIdempotencyKey,
                  candidate_content: CanonicalProjection) -> RetryDisposition:
    """Compare bytes as well as hashes; never reserve or write anything."""
    for key in (existing_key, candidate_key):
        if type(key) is not LogicalIdempotencyKey or build_key(key.components) != key:
            raise ContractError(Code.INVALID_FINGERPRINT, "key")
    for content in (existing_content, candidate_content):
        _verify_projection(content, 16384)
    if existing_key.projection.sha256 != candidate_key.projection.sha256:
        return RetryDisposition.DIFFERENT_KEY
    if (existing_key.projection.canonical_json != candidate_key.projection.canonical_json
            or existing_content.sha256 != candidate_content.sha256
            or existing_content.canonical_json != candidate_content.canonical_json):
        return RetryDisposition.CONTENT_CONFLICT
    return RetryDisposition.IDENTICAL_RETRY
