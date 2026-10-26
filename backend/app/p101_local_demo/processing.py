"""Pure SQL-snapshot-to-Computed pair; no persistence or automatic calculation."""

from dataclasses import asdict
import json
from uuid import UUID

from app.anomaly_detection.p101_canonical import utc_instant
from app.anomaly_detection.p101_contracts import Computed
from app.anomaly_detection.p101_core import evaluate, validate_proposal
from app.p101_persistence.contracts import CALCULATION_REVISION, FIXTURE_SHA256
from app.p101_local_demo.contracts import (
    CUTOFFS, TARGETS, CalculationContext, ComputedPair, ErrorCode, LocalDemoError,
)
from app.p101_local_demo.reader import adapt_rows, read_rows, validate_fixture


def validate_context(context):
    try:
        if (type(context) is not CalculationContext or str(UUID(context.run_id)) != context.run_id
                or context.code_revision != CALCULATION_REVISION or type(context.cutoffs) is not tuple
                or len(context.cutoffs) != 2 or tuple(utc_instant(c) for c in context.cutoffs) != CUTOFFS
                or utc_instant(context.prepared_at) < max(CUTOFFS)):
            raise LocalDemoError(ErrorCode.CONTEXT)
    except (ValueError, TypeError, AttributeError):
        raise LocalDemoError(ErrorCode.CONTEXT) from None


def process_rows(rows, reference, context):
    validate_context(context)
    adapted = adapt_rows(rows, reference)
    manifest = json.loads(adapted.manifest_json)
    results = []
    try:
        for target, cutoff in zip(TARGETS, CUTOFFS):
            result = evaluate(manifest, target, cutoff=cutoff, prepared_at=utc_instant(context.prepared_at),
                              run_id=context.run_id, code_revision=context.code_revision)
            if type(result) is not Computed or result.status != "computed":
                raise LocalDemoError(ErrorCode.CALCULATION)
            validate_proposal(result.prediction)
            details = result.prediction.details
            expected_refs = tuple(f"DEMO-M-{i:03d}" for i in range(int(target[-3:]) - 10, int(target[-3:])))
            if (result.prediction.measurement_fixture_id != target or result.reference_ids != expected_refs
                    or result.dataset_sha256 != FIXTURE_SHA256 or result.reference_sha256 != details["reference"]["sha256"]
                    or details["dataset"]["sha256"] != result.dataset_sha256 or details["cutoff_utc"] != cutoff
                    or details["run_id"] != context.run_id or details["prepared_at"] != utc_instant(context.prepared_at)
                    or details["producer"]["code_revision"] != context.code_revision
                    or asdict(result.statistics) != {k: details["statistics"][k] for k in
                        ("mean", "sample_std", "absolute_deviation", "threshold")}):
                raise LocalDemoError(ErrorCode.CALCULATION)
            results.append(result)
        return ComputedPair(tuple(results), adapted.identities)
    except LocalDemoError:
        raise
    except Exception:
        raise LocalDemoError(ErrorCode.CALCULATION) from None


def read_and_evaluate(connection, destination, reference, context):
    """Explicit opt-in call only; caller supplies a transaction and approved inputs."""
    validate_context(context)
    validate_fixture(reference)
    return process_rows(read_rows(connection, destination), reference, context)
