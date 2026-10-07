import math
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.anomaly_detection.zscore_detector import ZScoreAnomalyDetector


def zscore_frame(values=(1, 2, 3, 4, 100), sensor=1):
    return pd.DataFrame({"sensor_id": sensor, "value": list(values)})


class ZScoreDetectorTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        for source in (pd.DataFrame(), zscore_frame().iloc[:0]):
            result = ZScoreAnomalyDetector().detect(source)
            self.assertIsNot(source, result)
            assert_frame_equal(result, source)

    def test_zscore_uses_sample_standard_deviation(self):
        result = ZScoreAnomalyDetector().detect(zscore_frame((1, 2, 3)), z_threshold=0.9)
        self.assertEqual(result.z_score.tolist(), [-1, 0, 1])
        self.assertEqual(result.zscore_anomaly.tolist(), [True, False, True])

    def test_robust_zscore_calculation_and_outlier(self):
        # Median=3, absolute deviations=[2,1,0,1,97], MAD=1.
        result = ZScoreAnomalyDetector().detect(zscore_frame())
        for actual, expected in zip(result.robust_z_score, [-1.349, -0.6745, 0, 0.6745, 65.4265], strict=True):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(result.robust_zscore_anomaly.tolist(), [False] * 4 + [True])
        self.assertFalse(result.zscore_anomaly.any())
        self.assertAlmostEqual(result.z_score.iloc[-1], (100 - 22) / math.sqrt(1902.5))

    def test_constant_variance_and_singleton_have_na_scores(self):
        for values in ((7, 7, 7), (7,)):
            with self.subTest(values=values):
                result = ZScoreAnomalyDetector().detect(zscore_frame(values))
                self.assertTrue(result[["z_score", "robust_z_score"]].isna().all().all())
                self.assertFalse(result[["zscore_anomaly", "robust_zscore_anomaly"]].any().any())

    def test_zero_mad_with_nonconstant_values(self):
        result = ZScoreAnomalyDetector().detect(zscore_frame((1, 1, 1, 1, 100)))
        self.assertTrue(result.robust_z_score.isna().all())
        self.assertFalse(result.robust_zscore_anomaly.any())
        self.assertTrue(result.z_score.notna().all())

    def test_multiple_sensors_with_repeated_indices_do_not_mix(self):
        source = pd.concat([zscore_frame(), zscore_frame((1000, 1100, 1200, 1300, 1400), sensor=2)])
        source = source.iloc[[5, 2, 8, 0, 7, 4, 6, 1, 9, 3]]
        before = source.copy(deep=True)
        result = ZScoreAnomalyDetector().detect(source)
        self.assertEqual(result.index.tolist(), source.index.tolist())
        for sensor in (1, 2):
            with self.subTest(sensor=sensor):
                assert_frame_equal(result[result.sensor_id == sensor],
                                   ZScoreAnomalyDetector().detect(source[source.sensor_id == sensor]))
        self.assertFalse(result[result.sensor_id == 2].robust_zscore_anomaly.any())
        assert_frame_equal(source, before)

    def test_threshold_boundaries_and_custom_robust_threshold(self):
        source = zscore_frame((1, 2, 3))
        result = ZScoreAnomalyDetector().detect(source, z_threshold=1, robust_threshold=0.6745)
        self.assertFalse(result.zscore_anomaly.any())
        self.assertFalse(result.robust_zscore_anomaly.any())
        result = ZScoreAnomalyDetector().detect(source, robust_threshold=0.5)
        self.assertEqual(result.robust_zscore_anomaly.tolist(), [True, False, True])

    def test_nonpositive_thresholds_even_on_empty_frames(self):
        for source in (pd.DataFrame(), zscore_frame()):
            for parameter in ("z_threshold", "robust_threshold"):
                for threshold in (0, -1):
                    with self.subTest(empty=source.empty, parameter=parameter, threshold=threshold), self.assertRaisesRegex(ValueError, parameter):
                        ZScoreAnomalyDetector().detect(source, **{parameter: threshold})

    def test_missing_required_columns(self):
        for column in ("sensor_id", "value"):
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                ZScoreAnomalyDetector().detect(zscore_frame().drop(columns=column))
