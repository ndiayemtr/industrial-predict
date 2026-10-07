import math
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.multiscale_features import MultiScaleFeatureBuilder
from feature_engineering.support import assert_values, interleaved_measurements, measurements


class MultiScaleFeatureTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        for source in (pd.DataFrame(), measurements().iloc[:0]):
            result = MultiScaleFeatureBuilder().build(source)
            self.assertIsNot(result, source)
            assert_frame_equal(result, source)

    def test_default_windows_and_sample_standard_deviations(self):
        result = MultiScaleFeatureBuilder().build(measurements())
        assert_values(self, result.rolling_mean_3, [2, 3, 14 / 3, 26 / 3])
        assert_values(self, result.rolling_std_3, [None, math.sqrt(2), math.sqrt(28 / 3), math.sqrt(76 / 3)])
        for window in (5, 10):
            assert_values(self, result[f"rolling_mean_{window}"], [2, 3, 14 / 3, 7])
            assert_values(self, result[f"rolling_std_{window}"], [None, math.sqrt(2), math.sqrt(28 / 3), math.sqrt(28)])

    def test_custom_windows_and_sensor_isolation(self):
        source = interleaved_measurements()
        before = source.copy(deep=True)
        result = MultiScaleFeatureBuilder().build(source, windows=(1, 2))
        for sensor, means, deviations in (
            (1, [2, 3, 6, 11], [None, math.sqrt(2), math.sqrt(8), math.sqrt(18)]),
            (2, [1000, 950, 800, 550], [None, math.sqrt(5000), math.sqrt(20000), math.sqrt(45000)]),
        ):
            group = result[result.sensor_id == sensor]
            assert_values(self, group.rolling_mean_2, means)
            assert_values(self, group.rolling_std_2, deviations)
            assert_values(self, group.rolling_mean_1, group.value.tolist())
            self.assertTrue(group.rolling_std_1.isna().all())
        self.assertNotIn("rolling_mean_3", result)
        assert_frame_equal(source, before)

    def test_invalid_windows_on_empty_and_nonempty_frames(self):
        for source in (pd.DataFrame(), measurements()):
            for windows in ((0,), (-1,), (3, 0, 5)):
                with self.subTest(empty=source.empty, windows=windows), self.assertRaisesRegex(ValueError, "windows"):
                    MultiScaleFeatureBuilder().build(source, windows=windows)

    def test_empty_window_selection(self):
        source = measurements()
        assert_frame_equal(MultiScaleFeatureBuilder().build(source, windows=()), source)

    def test_missing_required_columns(self):
        for column in ("sensor_id", "timestamp", "measurement_id", "value"):
            with self.subTest(column=column), self.assertRaises(KeyError):
                MultiScaleFeatureBuilder().build(measurements().drop(columns=column))
