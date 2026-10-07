import itertools
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.anomaly_detection.unified_score import UnifiedAnomalyScorer
from anomaly_detection.support import SIGNALS


class UnifiedScorerTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        source = pd.DataFrame()
        result = UnifiedAnomalyScorer().build(source)
        self.assertIsNot(result, source)
        assert_frame_equal(result, source)

    def test_all_signal_combinations_and_default_threshold(self):
        combinations = list(itertools.product((False, True), repeat=3))
        source = pd.DataFrame(combinations, columns=SIGNALS, index=range(10, 18))
        before = source.copy(deep=True)
        result = UnifiedAnomalyScorer().build(source)
        expected = [0, 0.4, 0.35, 0.75, 0.25, 0.65, 0.6, 1]
        for actual, score in zip(result.anomaly_score, expected, strict=True):
            self.assertAlmostEqual(actual, score)
        self.assertEqual(result.is_anomaly.tolist(), [False, False, False, True, False, True, True, True])
        self.assertEqual(result.index.tolist(), source.index.tolist())
        assert_frame_equal(source, before)

    def test_absent_signal_columns_default_to_zero(self):
        result = UnifiedAnomalyScorer().build(pd.DataFrame({"measurement_id": [1, 2]}))
        self.assertEqual(result.anomaly_score.tolist(), [0, 0])
        self.assertFalse(result.is_anomaly.any())
        for column, score in zip(SIGNALS, (0.25, 0.35, 0.4), strict=True):
            with self.subTest(column=column):
                result = UnifiedAnomalyScorer().build(pd.DataFrame({column: [True, False]}))
                self.assertEqual(result.anomaly_score.tolist(), [score, 0])

    def test_na_signals_are_false(self):
        source = pd.DataFrame({column: pd.Series([pd.NA, False], dtype="boolean") for column in SIGNALS})
        result = UnifiedAnomalyScorer().build(source)
        self.assertEqual(result.anomaly_score.tolist(), [0, 0])
        self.assertFalse(result.is_anomaly.any())

    def test_threshold_is_inclusive_and_endpoints_are_allowed(self):
        source = pd.DataFrame({SIGNALS[0]: [False, True], SIGNALS[1]: [False, True], SIGNALS[2]: [False, False]})
        result = UnifiedAnomalyScorer().build(source, anomaly_threshold=0.6)
        self.assertEqual(result.is_anomaly.tolist(), [False, True])
        self.assertTrue(UnifiedAnomalyScorer().build(source, anomaly_threshold=0).is_anomaly.all())
        self.assertFalse(UnifiedAnomalyScorer().build(source, anomaly_threshold=1).is_anomaly.any())

    def test_custom_weights_are_normalized(self):
        source = pd.DataFrame({SIGNALS[0]: [True, False, True], SIGNALS[1]: [True, True, True], SIGNALS[2]: [False, True, True]})
        result = UnifiedAnomalyScorer().build(source, statistical_weight=2, robust_zscore_weight=3, isolation_forest_weight=5)
        self.assertEqual(result.anomaly_score.tolist(), [0.5, 0.8, 1])
        self.assertEqual(result.is_anomaly.tolist(), [False, True, True])

    def test_individual_zero_weights_are_allowed(self):
        result = UnifiedAnomalyScorer().build(pd.DataFrame({SIGNALS[0]: [True, False]}),
                                             statistical_weight=1, robust_zscore_weight=0, isolation_forest_weight=0)
        self.assertEqual(result.anomaly_score.tolist(), [1, 0])

    def test_nonpositive_weight_sum_is_rejected_even_on_empty_frame(self):
        for source in (pd.DataFrame(), pd.DataFrame({SIGNALS[0]: [True]})):
            for weight in (0, -1):
                with self.subTest(empty=source.empty, weight=weight), self.assertRaises(ValueError):
                    UnifiedAnomalyScorer().build(source, statistical_weight=weight,
                                                 robust_zscore_weight=weight, isolation_forest_weight=weight)

    def test_each_negative_weight_is_rejected_despite_positive_total(self):
        for parameter in ("statistical_weight", "robust_zscore_weight", "isolation_forest_weight"):
            for source in (pd.DataFrame(), pd.DataFrame(list(itertools.product((False, True), repeat=3)), columns=SIGNALS)):
                with self.subTest(parameter=parameter, empty=source.empty), self.assertRaisesRegex(ValueError, "weights"):
                    UnifiedAnomalyScorer().build(source, **{parameter: -0.1})

    def test_threshold_outside_closed_interval_is_rejected(self):
        for source in (pd.DataFrame(), pd.DataFrame({SIGNALS[0]: [True]})):
            for threshold in (-0.01, 1.01):
                with self.subTest(empty=source.empty, threshold=threshold), self.assertRaisesRegex(ValueError, "anomaly_threshold"):
                    UnifiedAnomalyScorer().build(source, anomaly_threshold=threshold)
