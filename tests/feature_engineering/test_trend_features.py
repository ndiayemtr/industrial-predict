import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.trend_features import TrendFeatureBuilder
from feature_engineering.support import assert_values, interleaved_measurements, measurements


class TrendFeatureTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        for source in (pd.DataFrame(), measurements().iloc[:0]):
            result = TrendFeatureBuilder().build(source)
            self.assertIsNot(result, source)
            assert_frame_equal(result, source)

    def test_slope_partial_and_full_windows_without_sensor_contamination(self):
        source = interleaved_measurements()
        before = source.copy(deep=True)
        result = TrendFeatureBuilder().build(source)
        assert_values(self, result[result.sensor_id == 1].trend_slope, [None, 2, 3, 5])
        assert_values(self, result[result.sensor_id == 2].trend_slope, [None, -100, -150, -250])
        assert_frame_equal(source, before)

    def test_window_size_changes_slope(self):
        result = TrendFeatureBuilder().build(measurements(), window_size=2)
        assert_values(self, result.trend_slope, [None, 2, 4, 6])

    def test_constant_series_and_window_larger_than_series(self):
        result = TrendFeatureBuilder().build(measurements((7, 7, 7)), window_size=10)
        assert_values(self, result.trend_slope, [None, 0, 0])

    def test_invalid_window_size_on_empty_and_nonempty_frames(self):
        for source in (pd.DataFrame(), measurements()):
            for window in (1, 0, -1):
                with self.subTest(empty=source.empty, window=window), self.assertRaisesRegex(ValueError, "window_size"):
                    TrendFeatureBuilder().build(source, window_size=window)

    def test_missing_required_columns(self):
        for column in ("sensor_id", "timestamp", "measurement_id", "value"):
            with self.subTest(column=column), self.assertRaises(KeyError):
                TrendFeatureBuilder().build(measurements().drop(columns=column))
