"""Small deterministic datasets, independent of SQL and cleaning fixtures."""

import math
from datetime import datetime, timedelta, timezone

import pandas as pd


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
QUALITY_COLUMNS = [
    "is_gap", "is_quality_warning", "is_quality_invalid", "is_duplicate", "is_outlier",
]
EQUIPMENT_COLUMNS = [
    "equipment_id", "sensor_count", "measurement_count", "value_mean", "value_std",
    "outlier_ratio", "gap_ratio", "invalid_quality_ratio",
]


def measurements(values=(2, 4, 8, 14), *, sensor=1, equipment=10, seconds=None):
    if seconds is None:
        seconds = range(0, 10 * len(values), 10)
    return pd.DataFrame([
        dict(measurement_id=sensor * 100 + i, sensor_id=sensor,
             equipment_id=equipment, timestamp=START + timedelta(seconds=second), value=value)
        for i, (value, second) in enumerate(zip(values, seconds, strict=True), 1)
    ])


def interleaved_measurements():
    # Different scales/cadences and repeated DataFrame indices expose leakage.
    return pd.concat([
        measurements(),
        measurements((1000, 900, 700, 400), sensor=2, seconds=(0, 5, 15, 30)),
    ]).iloc[[6, 2, 4, 0, 7, 3, 5, 1]]


def assert_values(case, actual, expected):
    case.assertEqual(len(actual), len(expected))
    for observed, wanted in zip(actual, expected, strict=True):
        if wanted is None:
            case.assertTrue(pd.isna(observed), repr(observed))
        else:
            case.assertTrue(math.isfinite(observed), repr(observed))
            case.assertAlmostEqual(observed, wanted)
