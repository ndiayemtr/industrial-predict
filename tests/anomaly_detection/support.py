"""Deterministic fixtures independent of the database and cleaning pipeline."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SIGNALS = ["statistical_anomaly", "robust_zscore_anomaly", "isolation_forest_anomaly"]
EQUIPMENT_COLUMNS = [
    "equipment_id", "sensor_count", "measurement_count", "anomaly_count",
    "anomaly_ratio", "max_anomaly_score", "mean_anomaly_score", "equipment_anomaly",
]


def sensor_features():
    # A compact normal cloud with nonzero MAD and one distant outlier.
    values = np.concatenate([np.tile([9.8, 9.9, 10.0, 10.1, 10.2], 8), [100.0]])
    return pd.DataFrame({
        "measurement_id": np.arange(1, len(values) + 1),
        "sensor_id": 1, "equipment_id": 10,
        "timestamp": pd.date_range(START, periods=len(values), freq="10s"),
        "value": values, "rolling_mean": 10.0, "rolling_std": 0.2,
        "value_delta": values - 10.0, "rate_of_change": (values - 10.0) / 10,
        "trend_slope": values - 10.0, "rolling_range": 0.4, "rolling_cv": 0.02,
    })
