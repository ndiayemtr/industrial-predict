import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from sklearn.ensemble import IsolationForest

from app.anomaly_detection.isolation_forest_detector import IsolationForestAnomalyDetector
from anomaly_detection.support import sensor_features


MODEL_PATH = "app.anomaly_detection.isolation_forest_detector.IsolationForest"


class IsolationForestDetectorTests(unittest.TestCase):
    def test_empty_frame_is_copied_without_fit(self):
        with patch(MODEL_PATH) as model:
            for source in (pd.DataFrame(), sensor_features().iloc[:0]):
                result = IsolationForestAnomalyDetector().detect(source)
                self.assertIsNot(source, result)
                assert_frame_equal(result, source)
            model.assert_not_called()

    def test_obvious_outlier_with_real_model(self):
        source = sensor_features()
        before = source.copy(deep=True)
        result = IsolationForestAnomalyDetector().detect(source)
        self.assertTrue(result.isolation_forest_anomaly.iloc[-1])
        self.assertFalse(result.isolation_forest_anomaly.iloc[2])
        self.assertTrue(result.isolation_forest_score.notna().all())
        self.assertEqual(result.isolation_forest_score.idxmax(), result.index[-1])
        assert_frame_equal(source, before)

    def test_custom_features_need_no_default_columns(self):
        source = sensor_features()[["value"]].rename(columns={"value": "custom_value"})
        source["unused"] = float("nan")
        with patch(MODEL_PATH, wraps=IsolationForest) as model:
            result = IsolationForestAnomalyDetector().detect(source, features=["custom_value"], contamination=0.1)
            model.assert_called_once_with(contamination=0.1, random_state=42)
        self.assertTrue(result.isolation_forest_anomaly.iloc[-1])
        self.assertTrue(result.isolation_forest_score.notna().all())

    def test_missing_default_features(self):
        for column in IsolationForestAnomalyDetector.DEFAULT_FEATURES:
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                IsolationForestAnomalyDetector().detect(sensor_features().drop(columns=column))

    def test_missing_custom_feature(self):
        with self.assertRaisesRegex(ValueError, "missing_feature"):
            IsolationForestAnomalyDetector().detect(sensor_features(), features=["value", "missing_feature"])

    def test_nan_and_nonnumeric_rows_excluded_from_fit_and_scoring(self):
        source = pd.DataFrame({"x": [1, "not-numeric", "2", None, 100],
                               "y": [2, 3, 4, 5, 200]}, index=[9, 9, 3, 2, 7])
        before = source.copy(deep=True)
        with patch(MODEL_PATH) as model_class:
            model = model_class.return_value
            model.fit_predict.return_value = np.array([1, 1, -1])
            model.score_samples.return_value = np.array([-0.1, -0.2, -0.9])
            result = IsolationForestAnomalyDetector().detect(source, features=["x", "y"])
            expected = pd.DataFrame({"x": [1.0, 2.0, 100.0], "y": [2, 4, 200]}, index=[9, 3, 7])
            assert_frame_equal(model.fit_predict.call_args.args[0], expected)
            assert_frame_equal(model.score_samples.call_args.args[0], expected)
        self.assertTrue(result.isolation_forest_score.iloc[[1, 3]].isna().all())
        self.assertEqual(result.isolation_forest_anomaly.tolist(), [False, False, False, False, True])
        self.assertEqual(result.isolation_forest_score.iloc[[0, 2, 4]].tolist(), [0.1, 0.2, 0.9])
        assert_frame_equal(source, before)

    def test_fewer_than_two_valid_rows_skip_model(self):
        for values in ([None, None], [1, None], [1]):
            with self.subTest(values=values), patch(MODEL_PATH) as model:
                result = IsolationForestAnomalyDetector().detect(pd.DataFrame({"x": values}), features=["x"])
                model.assert_not_called()
                self.assertTrue(result.isolation_forest_score.isna().all())
                self.assertFalse(result.isolation_forest_anomaly.any())

    def test_two_valid_rows_and_maximum_contamination_are_accepted(self):
        result = IsolationForestAnomalyDetector().detect(pd.DataFrame({"x": [1, 10]}), features=["x"], contamination=0.5)
        self.assertTrue(result.isolation_forest_score.notna().all())

    def test_invalid_contamination_even_on_empty_frames(self):
        for source in (pd.DataFrame(), sensor_features()):
            for contamination in (0, -0.1, 0.5001, 1):
                with self.subTest(empty=source.empty, contamination=contamination), self.assertRaisesRegex(ValueError, "contamination"):
                    IsolationForestAnomalyDetector().detect(source, contamination=contamination)

    def test_random_state_is_forwarded_and_reproducible(self):
        detector = IsolationForestAnomalyDetector()
        with patch(MODEL_PATH, wraps=IsolationForest) as model:
            first = detector.detect(sensor_features(), random_state=17)
            model.assert_called_once_with(contamination=0.05, random_state=17)
        second = detector.detect(sensor_features(), random_state=17)
        assert_frame_equal(first, second)
