from itertools import product

import pytest

from app.schemas.recommendation import RecommendationRead, RecommendationSignals
from app.services.recommendation_engine import RecommendationEngine
from app.services.recommendation_priority import RecommendationPriorityResolver


@pytest.mark.parametrize("signals,expected", [
    ({"rul_hours": 0}, "critical"), ({"rul_hours": 23.99}, "critical"),
    ({"rul_hours": 24}, "critical"), ({"rul_hours": 24.01}, "high"),
    ({"rul_hours": 71.99}, "high"), ({"rul_hours": 72}, "high"),
    ({"rul_hours": 72.01}, "medium"), ({"rul_hours": 167.99}, "medium"),
    ({"rul_hours": 168}, "medium"), ({"rul_hours": 168.01}, "low"),
    ({"failure_probability": .7499}, "low"), ({"failure_probability": .75}, "critical"),
    ({"failure_probability": .7501}, "critical"),
    ({"health_score": 29.99}, "critical"), ({"health_score": 30}, "high"),
    ({"health_score": 30.01}, "high"), ({"health_score": 49.99}, "high"),
    ({"health_score": 50}, "low"), ({"health_score": 50.01}, "low"),
    ({"anomaly_score": .4999}, "low"), ({"anomaly_score": .50}, "medium"),
    ({"anomaly_score": .5001}, "medium"), ({}, "low"),
])
def test_exact_priority_boundaries(signals, expected):
    assert RecommendationPriorityResolver().resolve(RecommendationSignals(**signals)) == expected


# Independently specified severities, including critical signals appearing after RUL
# in the resolver, catch accidental early returns for a less severe signal.
@pytest.mark.parametrize("rul,failure,health,anomaly", list(product(
    [(18., "critical"), (48., "high"), (100., "medium"), (200., "low")],
    [(.8, "critical"), (.1, "low")],
    [(20., "critical"), (40., "high"), (90., "low")],
    [(.6, "medium"), (.1, "low")])))
def test_most_severe_signal_always_wins(rul, failure, health, anomaly):
    ranking = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    expected = min([rul[1], failure[1], health[1], anomaly[1]], key=ranking.get)
    signals = RecommendationSignals(rul_hours=rul[0], failure_probability=failure[0],
                                    health_score=health[0], anomaly_score=anomaly[0])
    result = RecommendationEngine().recommend(equipment_id=42, signals=signals)
    assert result.priority == expected
    allowed_types = {"critical": {"urgent_maintenance"}, "high": {"inspection", "planned_maintenance"},
                     "medium": {"monitoring", "planned_maintenance"}, "low": {"no_action"}}
    assert result.recommendation_type in allowed_types[expected]


@pytest.mark.parametrize("signals,priority,kind", [
    ({"rul_hours": 24.}, "critical", "urgent_maintenance"),
    ({"failure_probability": .75}, "critical", "urgent_maintenance"),
    ({"health_score": 20.}, "critical", "urgent_maintenance"),
    ({"rul_hours": 72.}, "high", "planned_maintenance"),
    ({"health_score": 30.}, "high", "inspection"),
    ({"rul_hours": 168.}, "medium", "planned_maintenance"),
    ({"anomaly_score": .5}, "medium", "monitoring"),
    ({"rul_hours": 200.}, "low", "no_action"),
    ({"anomaly_score": 0.}, "low", "no_action"),
    ({"failure_probability": 0.}, "low", "no_action"),
    ({"rul_hours": 18., "health_score": 100., "failure_probability": 0.}, "critical", "urgent_maintenance"),
    ({"rul_hours": 200., "failure_probability": .8}, "critical", "urgent_maintenance"),
    ({"rul_hours": 100., "health_score": 40., "anomaly_score": .8}, "high", "inspection"),
    ({"rul_hours": 48., "health_score": 40.}, "high", "planned_maintenance"),
    ({"rul_hours": 100., "anomaly_score": .8}, "medium", "planned_maintenance"),
])
def test_engine_returns_one_coherent_deterministic_recommendation(signals, priority, kind):
    engine = RecommendationEngine()
    inputs = RecommendationSignals(**signals)
    before = inputs.model_dump()
    result = engine.recommend(equipment_id=42, signals=inputs)
    assert isinstance(result, RecommendationRead)
    assert result.equipment_id == 42
    assert result.priority == priority
    assert result.recommendation_type == kind
    assert result.signals == inputs
    assert all(text.strip() for text in [result.title, result.reason, result.recommended_action])
    assert engine.recommend(equipment_id=42, signals=inputs) == result
    assert inputs.model_dump() == before


def test_engine_rejects_no_signals():
    with pytest.raises(ValueError, match="At least one recommendation signal is required"):
        RecommendationEngine().recommend(equipment_id=42, signals=RecommendationSignals())
