import math
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.feature_pipeline import MeasurementFeaturePipeline
from feature_engineering.support import QUALITY_COLUMNS, assert_values, interleaved_measurements, measurements


class FeaturePipelineTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        for source in (pd.DataFrame(), measurements().iloc[:0]):
            result = MeasurementFeaturePipeline().build(source)
            self.assertIsNot(result, source)
            assert_frame_equal(result, source)

    def test_complete_pipeline_final_columns_and_numeric_results(self):
        source = measurements().iloc[::-1]
        source["gap_detected"] = source.measurement_id.eq(104)
        source["outlier_detected"] = source.measurement_id.eq(103)
        source["data_quality_status"] = source.measurement_id.map({101: "valid", 102: "warning", 103: "invalid", 104: "valid"})
        before = source.copy(deep=True)
        result = MeasurementFeaturePipeline().build(source)
        final_columns = set(source.columns) | {
            "time_delta_seconds", "rolling_mean", "rolling_min", "rolling_max",
            "rolling_std", "rolling_count", "value_delta", "trend_slope",
            "rolling_range", "rolling_cv", "rate_of_change",
            "value_lag_1", "value_lag_2", "value_lag_3",
        } | set(QUALITY_COLUMNS) | {
            f"rolling_{stat}_{window}" for stat in ("mean", "std") for window in (3, 5, 10)
        }
        self.assertEqual(set(result.columns), final_columns)
        self.assertEqual(result.measurement_id.tolist(), [101, 102, 103, 104])
        self.assertEqual(str(result.timestamp.dt.tz), "UTC")
        assert_values(self, result.time_delta_seconds, [None, 10, 10, 10])
        assert_values(self, result.rolling_mean, [2, 3, 14 / 3, 26 / 3])
        assert_values(self, result.rolling_range, [0, 2, 6, 10])
        assert_values(self, result.rolling_cv, [None, math.sqrt(2) / 3, math.sqrt(28 / 3) / (14 / 3), math.sqrt(76 / 3) / (26 / 3)])
        assert_values(self, result.trend_slope, [None, 2, 3, 5])
        assert_values(self, result.rate_of_change, [None, 0.2, 0.4, 0.6])
        self.assertEqual(result.is_gap.tolist(), [False, False, False, True])
        self.assertEqual(result.is_outlier.tolist(), [False, False, True, False])
        self.assertEqual(result.is_quality_warning.tolist(), [False, True, False, False])
        self.assertEqual(result.is_quality_invalid.tolist(), [False, False, True, False])
        self.assertFalse(result.is_duplicate.any())
        assert_frame_equal(source, before)

    def test_multiple_sensors_match_independent_pipeline_runs(self):
        source = interleaved_measurements()
        before = source.copy(deep=True)
        pipeline = MeasurementFeaturePipeline()
        result = pipeline.build(source)
        self.assertEqual(result.measurement_id.tolist(), [101, 102, 103, 104, 201, 202, 203, 204])
        for sensor in (1, 2):
            with self.subTest(sensor=sensor):
                actual = result[result.sensor_id == sensor].reset_index(drop=True)
                expected = pipeline.build(source[source.sensor_id == sensor])
                assert_frame_equal(actual, expected)
        assert_values(self, result[result.sensor_id == 2].rate_of_change, [None, -20, -20, -20])
        assert_frame_equal(source, before)

    def test_timestamp_ties_are_ordered_by_measurement_id_with_na_rate(self):
        source = measurements((2, 4, 8), seconds=(0, 0, 10)).iloc[[2, 1, 0]]
        result = MeasurementFeaturePipeline().build(source)
        self.assertEqual(result.measurement_id.tolist(), [101, 102, 103])
        self.assertEqual(result.index.tolist(), [0, 1, 2])
        assert_values(self, result.time_delta_seconds, [None, 0, 10])
        assert_values(self, result.rate_of_change, [None, None, 0.4])

    def test_custom_parameters_control_values_and_column_selection(self):
        result = MeasurementFeaturePipeline().build(
            measurements(), window_size=2, lags=(2, 4), multiscale_windows=(1, 2, 4),
        )
        assert_values(self, result.rolling_mean, [2, 3, 6, 11])
        assert_values(self, result.rolling_count, [1, 2, 2, 2])
        assert_values(self, result.trend_slope, [None, 2, 4, 6])
        assert_values(self, result.rolling_range, [0, 2, 4, 6])
        assert_values(self, result.value_lag_2, [None, None, 2, 4])
        self.assertTrue(result.value_lag_4.isna().all())
        assert_values(self, result.rolling_mean_1, [2, 4, 8, 14])
        assert_values(self, result.rolling_mean_2, [2, 3, 6, 11])
        assert_values(self, result.rolling_mean_4, [2, 3, 14 / 3, 7])
        assert_values(self, result.rolling_std_2, [None, math.sqrt(2), math.sqrt(8), math.sqrt(18)])
        for column in ("value_lag_1", "value_lag_3", "rolling_mean_3", "rolling_mean_5", "rolling_mean_10"):
            self.assertNotIn(column, result)

    def test_invalid_parameters_propagate_on_empty_and_nonempty_frames(self):
        for source in (pd.DataFrame(), measurements()):
            for parameters in (
                {"window_size": 1}, {"window_size": 0}, {"window_size": -1},
                {"lags": (0,)}, {"lags": (-1,)},
                {"multiscale_windows": (0,)}, {"multiscale_windows": (-1,)},
            ):
                with self.subTest(empty=source.empty, parameters=parameters), self.assertRaises(ValueError):
                    MeasurementFeaturePipeline().build(source, **parameters)

    def test_missing_required_columns(self):
        for column in ("sensor_id", "timestamp", "measurement_id", "value"):
            with self.subTest(column=column), self.assertRaises(KeyError):
                MeasurementFeaturePipeline().build(measurements().drop(columns=column))

    def test_zero_rolling_mean_produces_na_cv(self):
        result = MeasurementFeaturePipeline().build(measurements((-2, 2, 0)))
        self.assertEqual(result.rolling_mean.iloc[1:].tolist(), [0, 0])
        self.assertTrue(result.rolling_cv.iloc[1:].isna().all())

    def test_missing_quality_flags_default_to_false(self):
        result = MeasurementFeaturePipeline().build(measurements())
        for column in QUALITY_COLUMNS:
            self.assertEqual(result[column].tolist(), [False] * 4)
