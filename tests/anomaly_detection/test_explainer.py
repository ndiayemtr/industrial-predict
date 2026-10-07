import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.anomaly_detection.explainer import AnomalyExplainer


REASONS = {
    "statistical_anomaly": "statistical deviation",
    "robust_zscore_anomaly": "robust z-score anomaly",
    "isolation_forest_anomaly": "isolation forest anomaly",
    "is_gap": "measurement gap",
    "is_outlier": "statistical outlier",
}


class ExplainerTests(unittest.TestCase):
    def test_empty_frame_adds_reason_column(self):
        for source in (pd.DataFrame(), pd.DataFrame(columns=["measurement_id"])):
            before = source.copy(deep=True)
            result = AnomalyExplainer().explain(source)
            self.assertTrue(result.empty)
            self.assertEqual(result.columns.tolist(), source.columns.tolist() + ["anomaly_reason"])
            assert_frame_equal(source, before)

    def test_no_signal_has_na_reason(self):
        source = pd.DataFrame({column: [False, False] for column in REASONS})
        source["is_anomaly"] = False
        self.assertTrue(AnomalyExplainer().explain(source).anomaly_reason.isna().all())

    def test_each_reason_individually_with_other_columns_absent(self):
        for column, reason in REASONS.items():
            with self.subTest(column=column):
                source = pd.DataFrame({column: [True, False]}, index=[7, 2])
                result = AnomalyExplainer().explain(source)
                self.assertEqual(result.anomaly_reason.iloc[0], reason)
                self.assertTrue(pd.isna(result.anomaly_reason.iloc[1]))
                self.assertEqual(result.index.tolist(), [7, 2])

    def test_combined_reasons_order_and_input_preservation(self):
        source = pd.DataFrame({column: [True, column in ("is_gap", "is_outlier")] for column in REASONS})
        before = source.copy(deep=True)
        result = AnomalyExplainer().explain(source)
        self.assertEqual(result.anomaly_reason.tolist(), [", ".join(REASONS.values()), "measurement gap, statistical outlier"])
        assert_frame_equal(source, before)

    def test_all_optional_columns_absent(self):
        source = pd.DataFrame({"measurement_id": [1, 2]})
        result = AnomalyExplainer().explain(source)
        self.assertTrue(result.anomaly_reason.isna().all())
