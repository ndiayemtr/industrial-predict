from datetime import datetime, timedelta, timezone

import pandas as pd

from app.data_pipeline.schemas import MeasurementDataRow


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
BASE_COLUMNS = [
    "measurement_id", "timestamp", "value", "quality", "sensor_id", "sensor_code",
    "sensor_type", "sensor_unit", "sensor_status", "equipment_id", "equipment_code",
    "equipment_type", "equipment_status", "equipment_criticality", "site_id",
    "site_code", "company_id", "company_code",
]
FEATURE_COLUMNS = ["rolling_mean", "rolling_min", "rolling_max", "rolling_std",
                   "rolling_count", "value_delta"]


def row(measurement_id=1, sensor_id=1, seconds=0, value=1.0, **overrides):
    values = dict(
        measurement_id=measurement_id, timestamp=START+timedelta(seconds=seconds),
        value=value, quality="good", sensor_id=sensor_id, sensor_code=f"S{sensor_id}",
        sensor_type="temperature", sensor_unit="C", sensor_status="active",
        equipment_id=1, equipment_code="E1", equipment_type="pump",
        equipment_status="operational", equipment_criticality="high",
        site_id=1, site_code="SITE1", company_id=1, company_code="CO1",
    )
    return MeasurementDataRow(**(values | overrides))


def frame(*rows):
    """Raw input, without calling the production dataset builder."""
    return pd.DataFrame([item.model_dump() for item in rows])
