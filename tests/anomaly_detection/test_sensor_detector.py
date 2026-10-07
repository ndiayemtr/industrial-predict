import unittest
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from app.anomaly_detection.sensor_detector import SensorAnomalyDetector
from anomaly_detection.support import sensor_features


class SensorDetectorTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        source = pd.DataFrame()
        result = SensorAnomalyDetector().detect(source)
        self.assertIsNot(result, source)
        assert_frame_equal(result, source)

    def test_real_orchestration_normal_value_and_strong_anomaly(self):
        source = sensor_features()
        before = source.copy(deep=True)
        result = SensorAnomalyDetector().detect(source)
        columns = {
            "statistical_deviation", "statistical_threshold", "statistical_anomaly",
            "z_score", "zscore_anomaly", "robust_z_score", "robust_zscore_anomaly",
            "isolation_forest_score", "isolation_forest_anomaly", "anomaly_score", "is_anomaly",
        }
        self.assertEqual(set(result.columns), set(source.columns) | columns)
        for column in ("statistical_anomaly", "robust_zscore_anomaly", "isolation_forest_anomaly", "is_anomaly"):
            with self.subTest(column=column):
                self.assertFalse(result[column].iloc[2])
                self.assertTrue(result[column].iloc[-1])
        self.assertTrue(result.zscore_anomaly.iloc[-1])
        self.assertEqual(result.anomaly_score.iloc[2], 0)
        self.assertEqual(result.anomaly_score.iloc[-1], 1)
        assert_frame_equal(source, before)

    def test_parameters_and_intermediate_results_forwarded_in_order(self):
        detector = SensorAnomalyDetector()
        source = sensor_features()
        # Distinct frames make incorrect order or bypassing a stage observable.
        statistical = source.assign(statistical_anomaly=False)
        zscore = statistical.assign(robust_zscore_anomaly=False)
        isolation = zscore.assign(isolation_forest_anomaly=False)
        final = isolation.assign(anomaly_score=0.0, is_anomaly=False)
        with patch.object(detector.statistical_detector, "detect", return_value=statistical) as stats, \
             patch.object(detector.zscore_detector, "detect", return_value=zscore) as zscores, \
             patch.object(detector.isolation_forest_detector, "detect", return_value=isolation) as forest, \
             patch.object(detector.unified_scorer, "build", return_value=final) as scorer:
            result = detector.detect(source, threshold_std=2, z_threshold=2.5,
                                     robust_threshold=4, contamination=0.2,
                                     anomaly_threshold=0.7, isolation_features=["value"])
        self.assertIs(result, final)
        for call, expected_frame, expected_kwargs in (
            (stats, source, {"threshold_std": 2}),
            (zscores, statistical, {"z_threshold": 2.5, "robust_threshold": 4}),
            (forest, zscore, {"contamination": 0.2, "features": ["value"]}),
            (scorer, isolation, {"anomaly_threshold": 0.7}),
        ):
            call.assert_called_once()
            self.assertIs(call.call_args.args[0], expected_frame)
            self.assertEqual(call.call_args.kwargs, expected_kwargs)

    def test_custom_isolation_features_with_real_detectors(self):
        source = sensor_features()[["sensor_id", "value", "rolling_mean", "rolling_std"]]
        result = SensorAnomalyDetector().detect(source, isolation_features=["value"])
        self.assertTrue(result.isolation_forest_anomaly.iloc[-1])
        self.assertTrue(result.is_anomaly.iloc[-1])

    def test_invalid_parameters_propagate_for_nonempty_data(self):
        for parameter in ("threshold_std", "z_threshold", "robust_threshold", "contamination"):
            with self.subTest(parameter=parameter), self.assertRaisesRegex(ValueError, parameter):
                SensorAnomalyDetector().detect(sensor_features(), **{parameter: 0})
        with self.assertRaisesRegex(ValueError, "anomaly_threshold"):
            SensorAnomalyDetector().detect(sensor_features(), anomaly_threshold=1.1)
