from datetime import timedelta

from dashboard.support import START
from app.schemas.maintenance_recommendation import MaintenanceRecommendationCreate
from app.schemas.recommendation import RecommendationSignals


def create_data(**overrides):
    values = dict(equipment_id=1, priority="critical", recommendation_type="urgent_maintenance",
                  title="Urgent maintenance required", reason="Short remaining useful life",
                  recommended_action="Inspect immediately", signals=RecommendationSignals(rul_hours=18.),
                  generated_at=START)
    values.update(overrides)
    return MaintenanceRecommendationCreate(**values)


def seed_history(repository):
    """Deliberately insert out of time order; include an id tie and another equipment."""
    latest = repository.create(create_data(generated_at=START + timedelta(hours=3)))
    early = repository.create(create_data(priority="low", recommendation_type="no_action"))
    tie_first = repository.create(create_data(priority="high", recommendation_type="inspection",
                                              generated_at=START + timedelta(hours=1)))
    tie_last = repository.create(create_data(priority="medium", recommendation_type="monitoring",
                                             generated_at=START + timedelta(hours=1)))
    foreign = repository.create(create_data(equipment_id=2, generated_at=START + timedelta(days=1)))
    return dict(latest=latest, early=early, tie_first=tie_first, tie_last=tie_last, foreign=foreign)


def filter_cases():
    return [
        ({}, ["latest", "tie_last", "tie_first", "early"]),
        ({"priority": "high"}, ["tie_first"]),
        ({"priority": "critical"}, ["latest"]),
        ({"recommendation_type": "monitoring"}, ["tie_last"]),
        ({"start_time": START + timedelta(hours=1)}, ["latest", "tie_last", "tie_first"]),
        ({"end_time": START + timedelta(hours=1)}, ["tie_last", "tie_first", "early"]),
        ({"start_time": START + timedelta(hours=1), "end_time": START + timedelta(hours=1)},
         ["tie_last", "tie_first"]),
        ({"priority": "high", "recommendation_type": "inspection", "start_time": START,
          "end_time": START + timedelta(hours=1)}, ["tie_first"]),
        ({"priority": "high", "recommendation_type": "no_action"}, []),
        ({"start_time": START + timedelta(days=2)}, []),
        ({"end_time": START - timedelta(seconds=1)}, []),
    ]
