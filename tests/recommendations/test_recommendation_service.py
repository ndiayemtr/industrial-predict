from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import call, create_autospec

import pytest
from pydantic import ValidationError

from app.schemas.recommendation import RecommendationSignals
from app.schemas.maintenance_recommendation import MaintenanceRecommendationCreate
from app.services.recommendation_engine import RecommendationEngine


def test_supplied_signals_use_equipment_and_engine(recommendation_service):
    service = recommendation_service
    service.engine = create_autospec(RecommendationEngine, instance=True)
    signals = RecommendationSignals(rul_hours=18.)
    result = service.recommend_for_equipment(equipment_id=42, signals=signals)
    service.equipment_repository.get_by_id.assert_called_once_with(42)
    service.engine.recommend.assert_called_once_with(equipment_id=42, signals=signals)
    assert result is service.engine.recommend.return_value
    service.prediction_repository.get_latest_by_equipment_and_type.assert_not_called()


def test_supplied_signals_produce_real_recommendation(recommendation_service):
    result = recommendation_service.recommend_for_equipment(
        equipment_id=42, signals=RecommendationSignals(health_score=40.))
    assert (result.priority, result.recommendation_type) == ("high", "inspection")


@pytest.mark.parametrize("method", ["recommend_for_equipment", "recommend_from_latest_predictions"])
def test_missing_equipment_stops_all_work(recommendation_service, method):
    service = recommendation_service
    service.equipment_repository.get_by_id.return_value = None
    service.engine = create_autospec(RecommendationEngine, instance=True)
    kwargs = dict(equipment_id=999)
    if method == "recommend_for_equipment":
        kwargs["signals"] = RecommendationSignals(rul_hours=18.)
    with pytest.raises(LookupError, match="Equipment not found"):
        getattr(service, method)(**kwargs)
    service.equipment_repository.get_by_id.assert_called_once_with(999)
    service.engine.recommend.assert_not_called()
    service.prediction_repository.get_latest_by_equipment_and_type.assert_not_called()
    service.maintenance_recommendation_repository.create.assert_not_called()


def test_latest_predictions_mapping_and_automatic_persistence(recommendation_service):
    service = recommendation_service
    records = {"anomaly": SimpleNamespace(score=.6),
               "failure_risk": SimpleNamespace(score=82., details={"failure_probability": .82}),
               "health_score": SimpleNamespace(score=42.), "rul": SimpleNamespace(score=18.)}
    service.prediction_repository.get_latest_by_equipment_and_type.side_effect = lambda eid, kind: records[kind]
    before = datetime.now(timezone.utc)
    result = service.recommend_from_latest_predictions(equipment_id=42)
    after = datetime.now(timezone.utc)
    assert result.signals == RecommendationSignals(anomaly_score=.6, failure_probability=.82,
                                                   health_score=42., rul_hours=18.)
    assert (result.priority, result.recommendation_type) == ("critical", "urgent_maintenance")
    assert service.prediction_repository.get_latest_by_equipment_and_type.call_args_list == [
        call(42, kind) for kind in ["anomaly", "failure_risk", "health_score", "rul"]]
    service.maintenance_recommendation_repository.create.assert_called_once()
    data = service.maintenance_recommendation_repository.create.call_args.args[0]
    assert isinstance(data, MaintenanceRecommendationCreate)
    assert data.model_dump(exclude={"generated_at"}) == result.model_dump()
    assert before <= data.generated_at <= after
    assert data.generated_at.tzinfo == timezone.utc


@pytest.mark.parametrize("kind,record,expected", [
    ("anomaly", SimpleNamespace(score=.5), {"anomaly_score": .5}),
    ("anomaly", SimpleNamespace(score=0.), {"anomaly_score": 0.}),
    ("failure_risk", SimpleNamespace(score=99., details={"failure_probability": .75}), {"failure_probability": .75}),
    ("failure_risk", SimpleNamespace(score=99., details={"failure_probability": 0.}), {"failure_probability": 0.}),
    ("health_score", SimpleNamespace(score=30.), {"health_score": 30.}),
    ("rul", SimpleNamespace(score=0.), {"rul_hours": 0.}),
])
def test_partial_predictions_and_zero_values_are_usable(recommendation_service, kind, record, expected):
    service = recommendation_service
    service.prediction_repository.get_latest_by_equipment_and_type.side_effect = (
        lambda eid, requested: record if requested == kind else None)
    result = service.recommend_from_latest_predictions(equipment_id=42)
    assert result.signals == RecommendationSignals(**expected)
    service.maintenance_recommendation_repository.create.assert_called_once()


@pytest.mark.parametrize("details", [None, {}, {"other": .9}])
def test_failure_risk_without_probability_does_not_use_risk_score(recommendation_service, details):
    service = recommendation_service
    service.prediction_repository.get_latest_by_equipment_and_type.side_effect = (
        lambda eid, kind: SimpleNamespace(score=90., details=details) if kind == "failure_risk" else None)
    with pytest.raises(ValueError, match="At least one recommendation signal"):
        service.recommend_from_latest_predictions(equipment_id=42)
    service.maintenance_recommendation_repository.create.assert_not_called()


def test_missing_failure_details_with_other_signal_is_usable(recommendation_service):
    records = {"failure_risk": SimpleNamespace(score=90., details=None),
               "health_score": SimpleNamespace(score=40.)}
    recommendation_service.prediction_repository.get_latest_by_equipment_and_type.side_effect = (
        lambda eid, kind: records.get(kind))
    result = recommendation_service.recommend_from_latest_predictions(equipment_id=42)
    assert result.signals.failure_probability is None
    assert result.priority == "high"


def test_no_predictions_does_not_persist(recommendation_service):
    with pytest.raises(ValueError, match="At least one recommendation signal"):
        recommendation_service.recommend_from_latest_predictions(equipment_id=42)
    recommendation_service.maintenance_recommendation_repository.create.assert_not_called()


def test_no_supplied_signal_raises(recommendation_service):
    with pytest.raises(ValueError, match="At least one recommendation signal"):
        recommendation_service.recommend_for_equipment(equipment_id=42, signals=RecommendationSignals())


def test_invalid_stored_signal_is_rejected_without_persisting(recommendation_service):
    recommendation_service.prediction_repository.get_latest_by_equipment_and_type.side_effect = (
        lambda eid, kind: SimpleNamespace(score=1.5) if kind == "anomaly" else None)
    with pytest.raises(ValidationError):
        recommendation_service.recommend_from_latest_predictions(equipment_id=42)
    recommendation_service.maintenance_recommendation_repository.create.assert_not_called()
