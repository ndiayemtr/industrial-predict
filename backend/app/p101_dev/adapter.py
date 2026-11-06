"""Pure industrial projections -> existing DEV engine. No ORM, SQL or authority.

Callers must supply an already loaded, coherent snapshot. These declarations
prove neither database provenance nor B2B access. Every supplied row is retained;
this adapter does not choose a target, filter history, repair dates or fill gaps.
"""

from dataclasses import dataclass
from datetime import datetime

from app.p101_dev.contracts import (
    Abstained, AssetIdentity, Computed, DeclaredProvenance, EvaluationInput,
    Measurement, PreparedEvaluation, Rejected, RejectionCode as R, Result,
)
from app.p101_dev.evaluation import evaluate
from app.p101_dev.preparation import prepare


@dataclass(frozen=True, slots=True, repr=False)
class IndustrialChain:
    """Explicit primary keys and parent FKs, not inferred from a requested ID."""

    company_id: int
    site_id: int
    site_company_id: int
    equipment_id: int
    equipment_site_id: int
    sensor_id: int
    sensor_equipment_id: int
    sensor_type: str
    unit: str


@dataclass(frozen=True, slots=True, repr=False)
class IndustrialMeasurement:
    """Projection of measurements; the unit belongs to its resolved sensor."""

    id: int
    sensor_id: int
    timestamp: datetime
    value: float
    quality: str


@dataclass(frozen=True, slots=True, repr=False)
class IndustrialSnapshot:
    chain: IndustrialChain
    target: IndustrialMeasurement
    references: tuple[IndustrialMeasurement, ...]
    event_cutoff: datetime
    observed_at: datetime
    provenance: DeclaredProvenance


def _positive_id(value):
    return type(value) is int and 1 <= value <= 2147483647


def _timestamp(value):
    # Never attach a timezone to a naive SQL value or round microseconds.
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.isoformat(timespec="microseconds")


def _prepare_snapshot(snapshot):
    try:
        if type(snapshot) is not IndustrialSnapshot or type(snapshot.chain) is not IndustrialChain:
            return Rejected(R.INVALID_INPUT, "snapshot")
        chain = snapshot.chain
        if not all(_positive_id(getattr(chain, name)) for name in (
            "company_id", "site_id", "site_company_id", "equipment_id",
            "equipment_site_id", "sensor_id", "sensor_equipment_id",
        )):
            return Rejected(R.INVALID_IDENTITY, "chain.ids")
        if (chain.site_company_id != chain.company_id or chain.equipment_site_id != chain.site_id
                or chain.sensor_equipment_id != chain.equipment_id):
            return Rejected(R.INCONSISTENT_IDENTITY, "chain.parents")
        if type(snapshot.references) is not tuple:
            return Rejected(R.INVALID_INPUT, "references")
        if len(snapshot.references) > 32:
            return Rejected(R.INPUT_LIMIT, "references")
        asset = AssetIdentity(chain.company_id, chain.site_id, chain.equipment_id, chain.sensor_id)
        observations = []
        for row in (snapshot.target, *snapshot.references):
            if type(row) is not IndustrialMeasurement:
                return Rejected(R.INVALID_INPUT, "measurements")
            if not _positive_id(row.id) or not _positive_id(row.sensor_id):
                return Rejected(R.INVALID_IDENTITY, "measurements.ids")
            if row.sensor_id != chain.sensor_id:
                return Rejected(R.INCONSISTENT_IDENTITY, "measurements.sensor_id")
            timestamp = _timestamp(row.timestamp)
            if timestamp is None:
                return Rejected(R.INVALID_TIMESTAMP, "measurements.timestamp")
            observations.append(Measurement(row.id, asset, timestamp, row.value, row.quality, chain.unit))
        cutoff, observed = _timestamp(snapshot.event_cutoff), _timestamp(snapshot.observed_at)
        if cutoff is None or observed is None:
            return Rejected(R.INVALID_TIMESTAMP, "snapshot.time_context")
        # Existing preparation owns all policy, provenance and temporal rules.
        return prepare(EvaluationInput(asset, chain.sensor_type, observations[0], tuple(observations[1:]),
                                       cutoff, observed, snapshot.provenance))
    except Exception:
        # Constant structural diagnostic: no raw model repr, values or exception.
        return Rejected(R.INVALID_INPUT, "snapshot")


def _review(snapshot):
    prepared = _prepare_snapshot(snapshot)
    if type(prepared) is not PreparedEvaluation:
        return None, prepared
    # Delegate std/threshold checks to the sole existing calculation path.
    return prepared.value, evaluate(prepared.value)


def adapt(snapshot: IndustrialSnapshot) -> EvaluationInput | Abstained | Rejected:
    """Return normalized calculable input, or the engine's abstention/rejection.

    Calculability (including nonzero std) is checked by the existing engine.
    Use evaluate_snapshot when the computed result itself is wanted, avoiding
    a second explicit evaluation by the caller. Neither function performs I/O.
    """
    value, result = _review(snapshot)
    return value if type(result) is Computed else result


def evaluate_snapshot(snapshot: IndustrialSnapshot) -> Result:
    """Adapt and evaluate once, preserving Computed / Abstained / Rejected."""
    return _review(snapshot)[1]
