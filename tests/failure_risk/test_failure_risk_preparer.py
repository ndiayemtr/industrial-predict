import unittest

import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from app.ml.failure_risk_preparer import FailureRiskPreparer


# Explicit specification rather than deriving expectations from EXCLUDED_COLUMNS.
EXCLUDED = [
    "next_failure_at", "time_to_failure_hours", "measurement_id", "sensor_id",
    "equipment_id", "site_id", "company_id", "timestamp", "sensor_code",
    "equipment_code", "site_code", "company_code", "root_cause", "action_taken",
    "failure_code", "completed_at", "downtime_minutes", "cost",
]


class PreparerTests(unittest.TestCase):
    def test_empty_dataset_returns_empty_x_and_named_int8_y(self):
        for source in (pd.DataFrame(), pd.DataFrame(columns=["value", "failure_within_horizon"])):
            X, y = FailureRiskPreparer().prepare(source)
            self.assertTrue(X.empty)
            self.assertTrue(y.empty)
            self.assertEqual(y.name, "failure_within_horizon")
            self.assertEqual(str(y.dtype), "int8")

    def test_separation_numeric_boolean_features_and_text_exclusion(self):
        source = pd.DataFrame({"failure_within_horizon": [0, 1], "value": [1.5, 2.5],
                               "rolling_count": [2, 3], "is_gap": [False, True],
                               "description": ["normal", "warning"], "numeric_text": ["1", "2"]}, index=[8, 3])
        source["nullable_number"] = pd.array([1, None], dtype="Int64")
        source["nullable_flag"] = pd.array([True, None], dtype="boolean")
        before = source.copy(deep=True)
        X, y = FailureRiskPreparer().prepare(source)
        assert_frame_equal(X, source[["value", "rolling_count", "is_gap", "nullable_number", "nullable_flag"]])
        assert_series_equal(y, source.failure_within_horizon.astype("int8"))
        assert_frame_equal(source, before)
        X.iloc[0, 0] = 999
        y.iloc[0] = 1
        assert_frame_equal(source, before)

    def test_strict_leakage_id_timestamp_and_code_exclusion_even_if_numeric(self):
        # Numeric encoding must not sneak labels/maintenance outcomes into X.
        source = pd.DataFrame({column: [100, 200] for column in EXCLUDED})
        source["failure_within_horizon"] = [0, 1]
        source["value"] = [2., 3.]
        X, y = FailureRiskPreparer().prepare(source)
        self.assertEqual(X.columns.tolist(), ["value"])
        self.assertTrue(set(EXCLUDED).isdisjoint(X.columns))
        self.assertEqual(y.tolist(), [0, 1])

    def test_datetime_leakage_columns_are_excluded(self):
        source = pd.DataFrame({"failure_within_horizon": [1], "value": [10.],
                               "timestamp": [pd.Timestamp("2026-01-01T00:00:00Z")],
                               "next_failure_at": [pd.Timestamp("2026-01-01T01:00:00+02:00")],
                               "completed_at": [pd.Timestamp("2026-01-02T00:00:00Z")],
                               "time_to_failure_hours": [1.]})
        X, _ = FailureRiskPreparer().prepare(source)
        self.assertEqual(X.columns.tolist(), ["value"])

    def test_missing_target(self):
        with self.assertRaisesRegex(ValueError, "failure_within_horizon"):
            FailureRiskPreparer().prepare(pd.DataFrame({"value": [1]}))

    def test_only_excluded_columns_leaves_zero_features(self):
        X, y = FailureRiskPreparer().prepare(pd.DataFrame({"failure_within_horizon": [0, 1], "sensor_id": [1, 2]}))
        self.assertEqual(X.shape, (2, 0))
        self.assertEqual(y.tolist(), [0, 1])
