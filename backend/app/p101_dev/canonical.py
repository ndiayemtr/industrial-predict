"""Bounded deterministic projections, never historical fixture or key policies."""

from dataclasses import asdict
import hashlib
import json

from app.anomaly_detection.p101_canonical import bounded_details, decimal_text
from app.p101_persistence.canonical import canonical_projection
from app.p101_dev.contracts import EvaluationInput


def input_fingerprint(value: EvaluationInput) -> str:
    """Normalized, sorted input only; this is not a SQL idempotency key."""
    return canonical_projection({
        "schema_version": "p101-dev-input-v1", **asdict(value),
    }).sha256


def encode_details(details: dict) -> tuple[str, str]:
    """Use the input projection's decimal_text policy, retaining JSON numbers.

    65/65.0 emit 65, signed zeros emit 0, and fractions retain their decimal
    value. No float/int cast or rounding is applied to observations/statistics.
    canonical_projection uses these same decimal tokens as strings for hashing;
    details emit them unquoted to preserve their existing numeric JSON contract.
    Validate the original JSON limits first, then its canonical byte size too:
    expanding an exponent must never bypass the 6000-byte bound.
    """
    validated = json.loads(bounded_details(details))

    def encode(value):
        if type(value) in (int, float):
            return decimal_text(value)
        if isinstance(value, dict):
            return "{" + ",".join(json.dumps(key, ensure_ascii=False) + ":" + encode(value[key])
                                  for key in sorted(value)) + "}"
        if isinstance(value, list):
            return "[" + ",".join(encode(item) for item in value) + "]"
        return json.dumps(value, ensure_ascii=False, allow_nan=False)

    encoded = encode(validated)
    if len(encoded.encode("utf-8")) > 6000:
        raise ValueError("Canonical details exceed 6000 UTF-8 bytes")
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()
