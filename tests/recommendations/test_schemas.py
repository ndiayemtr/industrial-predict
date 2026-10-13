import pytest
from pydantic import ValidationError

from app.schemas.recommendation import RecommendationRead, RecommendationSignals
from app.schemas.maintenance_recommendation import MaintenanceRecommendationRead
from recommendations.support import create_data


@pytest.mark.parametrize("field,values", [
    ("anomaly_score", [0., 1.]), ("failure_probability", [0., 1.]),
    ("health_score", [0., 100.]), ("rul_hours", [0., 10000.]),
])
def test_signal_bounds_are_inclusive(field, values):
    for value in values:
        assert getattr(RecommendationSignals(**{field: value}), field) == value


@pytest.mark.parametrize("field,value", [
    ("anomaly_score", -.01), ("anomaly_score", 1.01),
    ("failure_probability", -.01), ("failure_probability", 1.01),
    ("health_score", -.01), ("health_score", 100.01), ("rul_hours", -.01),
])
def test_out_of_range_signals_rejected(field, value):
    with pytest.raises(ValidationError) as caught:
        RecommendationSignals(**{field: value})
    assert caught.value.errors()[0]["loc"] == (field,)


def test_all_signals_default_to_none():
    assert RecommendationSignals().model_dump() == dict(anomaly_score=None,
        failure_probability=None, health_score=None, rul_hours=None)


@pytest.mark.parametrize("priority", ["critical", "high", "medium", "low"])
def test_allowed_priorities(priority):
    data = create_data(priority=priority).model_dump(exclude={"generated_at"})
    assert RecommendationRead(**data).priority == priority


@pytest.mark.parametrize("kind", ["urgent_maintenance", "inspection", "planned_maintenance", "monitoring", "no_action"])
def test_allowed_recommendation_types(kind):
    data = create_data(recommendation_type=kind).model_dump(exclude={"generated_at"})
    assert RecommendationRead(**data).recommendation_type == kind


@pytest.mark.parametrize("override,field", [({"priority": "urgent"}, "priority"),
    ({"recommendation_type": "shutdown"}, "recommendation_type"),
    ({"equipment_id": 0}, "equipment_id"), ({"equipment_id": -1}, "equipment_id")])
def test_invalid_read_values(override, field):
    data = create_data().model_dump(exclude={"generated_at"})
    data.update(override)
    with pytest.raises(ValidationError) as caught:
        RecommendationRead(**data)
    assert caught.value.errors()[0]["loc"] == (field,)


def test_stored_read_validates_orm_and_nested_signals(repository):
    record = repository.create(create_data())
    result = MaintenanceRecommendationRead.model_validate(record)
    assert result.id == record.id
    assert result.signals == RecommendationSignals(rul_hours=18.)
    assert result.created_at == record.created_at
