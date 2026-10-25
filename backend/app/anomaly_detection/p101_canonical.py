"""Deterministic manifest encoding and bounded logical JSON, without I/O."""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import re
import unicodedata


INSTANT = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z"
)


def utc_instant(value: str) -> str:
    if not isinstance(value, str) or not INSTANT.fullmatch(value):
        raise ValueError("An offset and at most six fractional digits are required")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return instant.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def instant_datetime(value: str) -> datetime:
    return datetime.fromisoformat(utc_instant(value).replace("Z", "+00:00"))


def finite_value(value: object) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def decimal_text(value: object) -> str:
    if not finite_value(value):
        raise ValueError("A finite numeric temperature is required")
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def canonical_bytes(manifest: dict) -> bytes:
    """Normalize the documented manifest, including availability and all parents.

    This function raises on malformed/nonfinite input; evaluate converts such
    input to an abstention before requesting a digest of a computed result.
    """
    def normalize(value, key=None):
        if key == "value":
            return decimal_text(value)
        if key in ("timestamp", "available_at"):
            return utc_instant(value)
        if isinstance(value, dict):
            return {unicodedata.normalize("NFC", k): normalize(v, k)
                    for k, v in value.items()}
        if isinstance(value, list):
            rows = [normalize(row) for row in value]
            if key == "observations":
                rows.sort(key=lambda row: (row["timestamp"], row["fixture_id"]))
            return rows
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    return json.dumps(normalize(manifest), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def manifest_sha256(manifest: dict) -> str:
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def bounded_details(details: dict) -> str:
    """Serialize already schema-validated logical details; reject, never truncate."""
    def visit(value, depth=0):
        if isinstance(value, (dict, list)):
            if depth >= 6:
                raise ValueError("Details exceed six container levels")
            children = value.values() if isinstance(value, dict) else value
            for child in children:
                visit(child, depth + 1)
        elif isinstance(value, str):
            if len(value) > 240:
                raise ValueError("Details string exceeds 240 characters")
        elif value is not None and type(value) not in (bool, int, float):
            raise ValueError("Not a JSON value")

    visit(details)
    encoded = json.dumps(details, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > 6000:
        raise ValueError("Details exceed 6000 UTF-8 bytes")
    return encoded
