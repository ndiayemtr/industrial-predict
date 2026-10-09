"""Shared inputs and independently specified expected outputs."""


def payload(**overrides):
    data = dict(failure_probability=0.2, anomaly_score=0.1, valid_count=6,
                warning_count=2, invalid_count=2, corrective_in_progress=True,
                overdue_maintenance=False, planned_soon=False)
    data.update(overrides)
    return data


def expected_response(equipment_id=1):
    return dict(equipment_id=equipment_id, health_score=78.5, health_level="good",
                components=dict(failure_health=80.0, anomaly_health=90.0,
                                data_quality_health=70.0, maintenance_health=60.0))
