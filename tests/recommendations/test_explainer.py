import pytest

from app.schemas.recommendation import RecommendationSignals
from app.services.recommendation_explainer import RecommendationExplainer


@pytest.mark.parametrize("signals,reason", [
    ({"rul_hours": 24.}, "remaining useful life is 24 hours or less"),
    ({"failure_probability": .75}, "failure probability is 75% or higher"),
    ({"health_score": 29.}, "equipment health score is below 30"),
])
def test_critical_single_signal_explains_only_the_trigger(signals, reason):
    title, explanation, action = RecommendationExplainer().explain(priority="critical",
        recommendation_type="urgent_maintenance", signals=RecommendationSignals(**signals))
    assert title == "Urgent maintenance required"
    assert explanation == f"Critical maintenance condition detected because {reason}."
    assert "immediately" in action


def test_critical_multiple_signals_are_all_explained():
    title, reason, action = RecommendationExplainer().explain(priority="critical",
        recommendation_type="urgent_maintenance", signals=RecommendationSignals(
            rul_hours=18., failure_probability=.82, health_score=20., anomaly_score=.9))
    for text in ["remaining useful life is 24 hours or less", "failure probability is 75% or higher",
                 "equipment health score is below 30"]:
        assert text in reason
    assert title and action


def test_critical_ignores_nontriggering_signals_in_reason():
    _, reason, _ = RecommendationExplainer().explain(priority="critical",
        recommendation_type="urgent_maintenance", signals=RecommendationSignals(
            rul_hours=24., failure_probability=.74, health_score=30.))
    assert "remaining useful life" in reason
    assert "failure probability" not in reason
    assert "health score" not in reason


@pytest.mark.parametrize("priority,kind,signals,title,reason_fragment,action_fragment", [
    ("high", "planned_maintenance", {"rul_hours": 48.}, "Maintenance should be planned soon",
     "Remaining useful life", "Plan maintenance"),
    ("high", "inspection", {"health_score": 40.}, "Technical inspection recommended",
     "significant degradation", "Inspect"),
    ("medium", "planned_maintenance", {"rul_hours": 100.}, "Maintenance planning recommended",
     "Remaining useful life", "maintenance plan"),
    ("medium", "monitoring", {"anomaly_score": .5}, "Enhanced monitoring recommended",
     "An anomaly signal", "monitoring frequency"),
    ("low", "no_action", {"health_score": 100.}, "No immediate maintenance action required",
     "No significant maintenance risk", "normal equipment monitoring"),
])
def test_explanation_matches_priority_and_action(priority, kind, signals, title, reason_fragment, action_fragment):
    result = RecommendationExplainer().explain(priority=priority, recommendation_type=kind,
                                               signals=RecommendationSignals(**signals))
    assert len(result) == 3
    assert all(isinstance(text, str) and text.strip() for text in result)
    assert result[0] == title
    assert reason_fragment in result[1]
    assert action_fragment in result[2]
