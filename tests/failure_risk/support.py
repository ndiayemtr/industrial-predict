"""Small deterministic fixtures; no database or external training data."""

from datetime import datetime, timedelta, timezone

import pandas as pd


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
MAINTENANCE_COLUMNS = ["equipment_id", "maintenance_type", "started_at"]


def measurements(hours=(0, 12, 48), equipment=10):
    return pd.DataFrame({
        "measurement_id": range(1, len(hours) + 1), "equipment_id": equipment,
        "timestamp": [START + timedelta(hours=hour) for hour in hours],
        "value": range(10, 10 + len(hours)),
    })


def maintenance(hours=(24,), equipment=10, kind="corrective"):
    return pd.DataFrame([
        {"equipment_id": equipment, "maintenance_type": kind,
         "started_at": START + timedelta(hours=hour)} for hour in hours
    ], columns=MAINTENANCE_COLUMNS)


def training_data():
    # Linearly separable balanced binary data, with nontrivial indices.
    X = pd.DataFrame({"value": [-5., -4., -3., -2., 2., 3., 4., 5.],
                      "constant": 1.0}, index=[19, 3, 8, 2, 17, 6, 4, 11])
    y = pd.Series([0, 0, 0, 0, 1, 1, 1, 1], index=X.index,
                  dtype="int8", name="failure_within_horizon")
    return X, y
