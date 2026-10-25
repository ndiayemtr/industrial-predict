"""Pure final mapping and validation. No model/session imports."""

from dataclasses import dataclass
from datetime import datetime
import json
import math
from decimal import Decimal

from app.anomaly_detection.p101_canonical import bounded_details, utc_instant
from app.anomaly_detection.p101_contracts import ASSET, Computed, LogicalPrediction, Statistics
from app.p101_persistence.contracts import PreparationDossier, PreparationPolicy, ValidatedPreparation
from app.p101_persistence.preparation import prepare_batch
from app.p101_postgres.runtime import PersistenceError


def instant(value):
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise PersistenceError("Timezone required")
        value = value.isoformat()
    return utc_instant(value)


def sql_id(value):
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise PersistenceError("Invalid PostgreSQL INTEGER identity")
    return value


def validate_dossier(dossier: PreparationDossier) -> None:
    """Rebuild the offline result, so a frozen dataclass is not trusted by type alone."""
    try:
        if type(dossier) is not PreparationDossier:
            raise PersistenceError("Validated pair required")
        manifest = json.loads(dossier.manifest_canonical_json)
        for row in manifest["observations"]:
            row["value"] = float(row["value"])
        proposals = []
        for target in dossier.targets:
            plan = target.read_plan
            d = plan.details.candidate
            d.pop("idempotency_key")
            d["producer"]["revision_status"] = "requires_validation"
            p = LogicalPrediction(ASSET["equipment_id"], ASSET["sensor_id"], target.identity,
                plan.predicted_at, plan.score, plan.is_alert, bounded_details(d),
                plan.prediction_type, plan.model_name, plan.model_version, plan.level, plan.horizon_hours)
            proposals.append(Computed(p, tuple(row["fixture_id"] for row in d["reference"]["observations"]),
                Statistics(**{key: d["statistics"][key] for key in
                    ("mean", "sample_std", "absolute_deviation", "threshold")}),
                d["dataset"]["sha256"], d["reference"]["sha256"]))
        result = prepare_batch(tuple(proposals), manifest,
            policy=PreparationPolicy(dossier.destination, dossier.provenance.review_uuid),
            provenance=dossier.provenance, authorization=dossier.authorization)
        if type(result) is not ValidatedPreparation or result.dossier != dossier:
            raise PersistenceError("Offline preparation does not match its content")
    except PersistenceError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise PersistenceError("Invalid offline preparation") from None


@dataclass(frozen=True)
class SourceMapping:
    company_id: int
    site_id: int
    equipment_id: int
    sensor_id: int
    measurement_ids: tuple[tuple[str, int], ...]


def validate_sources(dossier: PreparationDossier, rows: tuple[dict, ...]) -> SourceMapping:
    """Validate the locked SQL snapshot against all twelve canonical observations."""
    try:
        parents = {row["kind"]: row for row in rows if row["kind"] != "measurement"}
        if len(rows) != 16 or len(parents) != 4:
            raise PersistenceError("Incomplete or ambiguous source snapshot")
        for kind in ("company", "site", "equipment", "sensor"):
            row = parents[kind]
            sql_id(row["id"])
            if row["payload"]["code"] != ASSET[f"{kind}_code"]:
                raise PersistenceError("Industrial code mismatch")
        company, site, equipment, sensor = (parents[k] for k in ("company", "site", "equipment", "sensor"))
        if (site["payload"]["company_id"] != company["id"]
                or equipment["payload"]["site_id"] != site["id"]
                or sensor["payload"]["equipment_id"] != equipment["id"]
                or equipment["payload"]["equipment_type"] != "pump"
                or sensor["payload"]["sensor_type"] != "temperature" or sensor["payload"]["unit"] != "°C"
                or "synthétique" not in equipment["payload"]["name"]):
            raise PersistenceError("Industrial parent or unit mismatch")
        expected = {row["timestamp"]: row for row in json.loads(dossier.manifest_canonical_json)["observations"]}
        mapping = []
        ids, timestamps = set(), set()
        for row in rows:
            if row["kind"] != "measurement":
                continue
            sql_id(row["id"])
            p = row["payload"]
            stamp = instant(p["timestamp"])
            observation = expected[stamp]
            if (row["id"] in ids or stamp in timestamps or p["sensor_id"] != sensor["id"]
                    or type(p["value"]) not in (int, float) or not math.isfinite(p["value"])
                    or Decimal(str(p["value"])) != Decimal(observation["value"])
                    or p["quality"] != "good"):
                raise PersistenceError("Measurement mismatch or duplicate")
            ids.add(row["id"])
            timestamps.add(stamp)
            mapping.append((observation["fixture_id"], row["id"]))
        if timestamps != set(expected):
            raise PersistenceError("Incomplete reference window")
        return SourceMapping(company["id"], site["id"], equipment["id"], sensor["id"], tuple(sorted(mapping)))
    except PersistenceError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise PersistenceError("Invalid SQL source snapshot") from None


def map_prediction(dossier, target, sources: SourceMapping, prediction_id: int, created_at) -> dict:
    plan = target.read_plan
    ids = dict(sources.measurement_ids)
    d = plan.details.candidate
    d["asset"] = {key: ASSET[key] for key in ("company_code", "site_code", "equipment_code", "sensor_code")}
    d["asset"].update(equipment_id=sources.equipment_id, sensor_id=sources.sensor_id)
    d["target"]["measurement_id"] = ids[target.identity]
    for row in d["reference"]["observations"]:
        row["measurement_id"] = ids[row["fixture_id"]]
    row = dict(id=sql_id(prediction_id), equipment_id=sql_id(sources.equipment_id),
        sensor_id=sql_id(sources.sensor_id), measurement_id=sql_id(ids[target.identity]),
        prediction_type=plan.prediction_type, score=plan.score, level=plan.level,
        is_alert=plan.is_alert, model_name=plan.model_name, model_version=plan.model_version,
        horizon_hours=plan.horizon_hours, details=json.loads(bounded_details(d)),
        predicted_at=instant(plan.predicted_at), created_at=instant(created_at))
    validate_read(dossier, target, sources, row)
    return row


def validate_read(dossier, target, sources, row: dict) -> None:
    expected_fields = {"id", "equipment_id", "sensor_id", "measurement_id", "prediction_type", "score",
        "level", "is_alert", "model_name", "model_version", "horizon_hours", "details", "predicted_at", "created_at"}
    try:
        if set(row) != expected_fields:
            raise PersistenceError("Exactly fourteen Read fields required")
        for name in ("id", "equipment_id", "sensor_id", "measurement_id"):
            sql_id(row[name])
        plan = target.read_plan
        if (row["equipment_id"] != sources.equipment_id or row["sensor_id"] != sources.sensor_id
                or row["measurement_id"] != dict(sources.measurement_ids)[target.identity]
                or type(row["score"]) not in (int, float) or row["score"] != plan.score
                or type(row["is_alert"]) is not bool or row["is_alert"] != plan.is_alert
                or row["prediction_type"] != "anomaly" or row["model_name"] != "statistical_deviation"
                or row["model_version"] != "p101-stat-v1" or row["level"] is not None
                or row["horizon_hours"] is not None or instant(row["predicted_at"]) != plan.predicted_at):
            raise PersistenceError("Read mapping mismatch")
        d = row["details"]
        for value in (d["asset"]["equipment_id"], d["asset"]["sensor_id"], d["target"]["measurement_id"]):
            sql_id(value)
        for reference in d["reference"]["observations"]:
            sql_id(reference["measurement_id"])
        expected = plan.details.candidate
        # Existing retries keep the first run/prepared_at, not the new attempt.
        original_run, original_prepared = d["run_id"], d["prepared_at"]
        from uuid import UUID
        if str(UUID(original_run)) != original_run:
            raise PersistenceError("Invalid original run")
        expected["run_id"] = original_run
        expected["prepared_at"] = original_prepared
        expected["asset"] = {key: ASSET[key] for key in ("company_code", "site_code", "equipment_code", "sensor_code")}
        expected["asset"].update(equipment_id=sources.equipment_id, sensor_id=sources.sensor_id)
        expected["target"]["measurement_id"] = dict(sources.measurement_ids)[target.identity]
        for ref in expected["reference"]["observations"]:
            ref["measurement_id"] = dict(sources.measurement_ids)[ref["fixture_id"]]
        if (d != expected or bounded_details(d) != bounded_details(expected)
                or original_prepared != instant(original_prepared)
                or instant(row["created_at"]) < instant(original_prepared)
                or instant(original_prepared) < d["cutoff_utc"]):
            raise PersistenceError("Final details or first-write chronology mismatch")
    except PersistenceError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise PersistenceError("Invalid final Read/details") from None
