import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.lag_features import LagFeatureBuilder
from feature_engineering.support import assert_values, interleaved_measurements, measurements


class LagFeatureTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        for source in (pd.DataFrame(), measurements().iloc[:0]):
            with self.subTest(columns=list(source.columns)):
                result = LagFeatureBuilder().build(source)
                self.assertIsNot(result, source)
                assert_frame_equal(result, source)

    def test_lags_one_two_three_and_sensor_isolation(self):
        source = interleaved_measurements()
        before = source.copy(deep=True)
        result = LagFeatureBuilder().build(source)
        for sensor, values in ((1, (2, 4, 8, 14)), (2, (1000, 900, 700, 400))):
            group = result[result.sensor_id == sensor]
            for lag in (1, 2, 3):
                with self.subTest(sensor=sensor, lag=lag):
                    assert_values(self, group[f"value_lag_{lag}"], [None] * lag + list(values[:-lag]))
        self.assertEqual(result.measurement_id.tolist(), [101, 102, 103, 104, 201, 202, 203, 204])
        assert_frame_equal(source, before)

    def test_invalid_lags_on_empty_and_nonempty_frames(self):
        for source in (pd.DataFrame(), measurements()):
            for lags in ((0,), (-1,), (1, 0, 3)):
                with self.subTest(empty=source.empty, lags=lags), self.assertRaisesRegex(ValueError, "lags"):
                    LagFeatureBuilder().build(source, lags=lags)

    def test_custom_lags_and_lag_longer_than_series(self):
        result = LagFeatureBuilder().build(measurements(), lags=(2, 5))
        assert_values(self, result.value_lag_2, [None, None, 2, 4])
        self.assertTrue(result.value_lag_5.isna().all())
        self.assertNotIn("value_lag_1", result)

    def test_empty_lag_selection(self):
        source = measurements()
        assert_frame_equal(LagFeatureBuilder().build(source, lags=()), source)

    def test_missing_required_columns(self):
        for column in ("sensor_id", "timestamp", "measurement_id", "value"):
            with self.subTest(column=column), self.assertRaises(KeyError):
                LagFeatureBuilder().build(measurements().drop(columns=column))
