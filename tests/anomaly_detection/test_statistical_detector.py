import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.anomaly_detection.statistical_detector import StatisticalAnomalyDetector


def statistical_frame():
    return pd.DataFrame({"value": [10, 11, 30], "rolling_mean": [10, 10, 10],
                         "rolling_std": [2, 2, 2]}, index=[8, 2, 5])


class StatisticalDetectorTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        for source in (pd.DataFrame(), statistical_frame().iloc[:0]):
            result = StatisticalAnomalyDetector().detect(source)
            self.assertIsNot(source, result)
            assert_frame_equal(result, source)

    def test_normal_values_and_obvious_anomaly(self):
        source = statistical_frame()
        before = source.copy(deep=True)
        result = StatisticalAnomalyDetector().detect(source)
        self.assertEqual(result.statistical_deviation.tolist(), [0, 1, 20])
        self.assertEqual(result.statistical_threshold.tolist(), [6, 6, 6])
        self.assertEqual(result.statistical_anomaly.tolist(), [False, False, True])
        self.assertEqual(result.index.tolist(), [8, 2, 5])
        assert_frame_equal(source, before)

    def test_exact_threshold_is_not_anomalous(self):
        source = pd.DataFrame({"value": [16, 4, 16.1], "rolling_mean": 10, "rolling_std": 2})
        self.assertEqual(StatisticalAnomalyDetector().detect(source).statistical_anomaly.tolist(),
                         [False, False, True])

    def test_nan_std_has_no_signal(self):
        source = statistical_frame()
        source["rolling_std"] = float("nan")
        result = StatisticalAnomalyDetector().detect(source)
        self.assertTrue(result.statistical_threshold.isna().all())
        self.assertFalse(result.statistical_anomaly.any())

    def test_zero_std_flags_only_nonzero_deviation(self):
        source = statistical_frame()
        source["rolling_std"] = 0
        result = StatisticalAnomalyDetector().detect(source)
        self.assertEqual(result.statistical_threshold.tolist(), [0, 0, 0])
        self.assertEqual(result.statistical_anomaly.tolist(), [False, True, True])

    def test_custom_threshold_changes_detection(self):
        result = StatisticalAnomalyDetector().detect(statistical_frame(), threshold_std=20)
        self.assertFalse(result.statistical_anomaly.any())

    def test_invalid_thresholds_even_on_empty_frame(self):
        for source in (pd.DataFrame(), statistical_frame()):
            for threshold in (0, -1):
                with self.subTest(empty=source.empty, threshold=threshold), self.assertRaisesRegex(ValueError, "threshold_std"):
                    StatisticalAnomalyDetector().detect(source, threshold_std=threshold)

    def test_missing_required_columns(self):
        for column in statistical_frame().columns:
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                StatisticalAnomalyDetector().detect(statistical_frame().drop(columns=column))
