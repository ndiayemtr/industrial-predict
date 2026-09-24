import math
import unittest
from datetime import timedelta, timezone

import pandas as pd
from pandas.testing import assert_frame_equal

from data_pipeline.support import BASE_COLUMNS, FEATURE_COLUMNS, START, frame, row
from app.data_pipeline.dataset_builder import MeasurementDatasetBuilder
from app.data_pipeline.data_quality import DataQualityReport
from app.data_pipeline.time_series import TimeSeriesPreparer
from app.data_pipeline.window_features import WindowFeatureBuilder


class DatasetBuilderTests(unittest.TestCase):
    def test_empty_dataset(self):
        result = MeasurementDatasetBuilder().build([])
        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)
        # Current empty-dataset contract: no columns, not a typed empty frame.
        self.assertEqual(list(result.columns), [])

    def test_expected_columns_and_values(self):
        result = MeasurementDatasetBuilder().build([row(value=42)])
        self.assertEqual(list(result.columns), BASE_COLUMNS)
        self.assertEqual(result.loc[0, "value"], 42)
        self.assertEqual(result.loc[0, "sensor_unit"], "C")
        self.assertEqual(result.loc[0, "company_code"], "CO1")

    def test_timestamps_converted_to_utc(self):
        values = [row(i, timestamp=START.astimezone(timezone(timedelta(hours=offset))))
                  for i, offset in enumerate((0, 5.5, -4), 1)]
        result = MeasurementDatasetBuilder().build(values)
        self.assertEqual(str(result.timestamp.dt.tz), "UTC")
        self.assertTrue((result.timestamp == pd.Timestamp(START)).all())

    def test_sort_sensor_timestamp_then_id_and_reset_index(self):
        result = MeasurementDatasetBuilder().build([
            row(1, sensor_id=2), row(5, seconds=10), row(4), row(3)])
        self.assertEqual(result.measurement_id.tolist(), [3, 4, 5, 1])
        self.assertEqual(result.index.tolist(), [0, 1, 2, 3])

    def test_input_rows_are_unchanged(self):
        values = [row(2), row(1)]
        before = [value.model_dump() for value in values]
        MeasurementDatasetBuilder().build(values)
        self.assertEqual([value.model_dump() for value in values], before)


class QualityReportTests(unittest.TestCase):
    def test_empty_dataset(self):
        self.assertEqual(DataQualityReport().analyze(pd.DataFrame()), {
            "row_count": 0, "missing_values": {}, "duplicate_measurements": 0,
            "invalid_values": 0, "invalid_timestamps": 0, "quality_distribution": {},
        })

    def test_row_count_and_clean_report(self):
        result = DataQualityReport().analyze(frame(row(1), row(2)))
        self.assertEqual(result["row_count"], 2)
        self.assertTrue(all(count == 0 for count in result["missing_values"].values()))
        for key in ("duplicate_measurements", "invalid_values", "invalid_timestamps"):
            self.assertEqual(result[key], 0)

    def test_missing_values_per_column(self):
        data = frame(row(1), row(2), row(3))
        data["value"] = [None, 2, float("nan")]
        data["sensor_unit"] = [None, "C", "C"]
        result = DataQualityReport().analyze(data)
        self.assertEqual(result["missing_values"]["value"], 2)
        self.assertEqual(result["missing_values"]["sensor_unit"], 1)
        self.assertEqual(result["missing_values"]["measurement_id"], 0)

    def test_duplicates_are_extra_rows_with_same_measurement_id(self):
        data = frame(row(1), row(1, sensor_id=2), row(1, value=99), row(2))
        self.assertEqual(DataQualityReport().analyze(data)["duplicate_measurements"], 2)

    def test_numeric_invalid_values_and_numeric_strings(self):
        data = frame(*[row(i) for i in range(6)])
        data["value"] = [1, "2.5", "invalid", "", None, float("nan")]
        self.assertEqual(DataQualityReport().analyze(data)["invalid_values"], 4)

    def test_invalid_timestamps_as_nat(self):
        data = frame(row(1), row(2), row(3))
        data["timestamp"] = pd.to_datetime([START, None, "invalid"], errors="coerce", utc=True)
        self.assertEqual(DataQualityReport().analyze(data)["invalid_timestamps"], 2)

    def test_unparseable_timestamp_is_reported_invalid(self):
        data = frame(row(1), row(2))
        data["timestamp"] = [START.isoformat(), "not-a-timestamp"]
        self.assertEqual(DataQualityReport().analyze(data)["invalid_timestamps"], 1)

    def test_quality_distribution_includes_unknown_and_missing(self):
        data = frame(*[row(i) for i in range(5)])
        data["quality"] = ["good", "good", "bad", "custom", None]
        distribution = DataQualityReport().analyze(data)["quality_distribution"]
        self.assertEqual(distribution["good"], 2)
        self.assertEqual(distribution["bad"], 1)
        self.assertEqual(distribution["custom"], 1)
        self.assertEqual(sum(count for key, count in distribution.items() if pd.isna(key)), 1)
        self.assertEqual(sum(distribution.values()), 5)

    def test_report_does_not_mutate_dataset(self):
        data = frame(row())
        before = data.copy(deep=True)
        DataQualityReport().analyze(data)
        assert_frame_equal(data, before)


class TimeSeriesTests(unittest.TestCase):
    def test_empty_dataset_and_profile(self):
        source = pd.DataFrame()
        preparer = TimeSeriesPreparer()
        result = preparer.prepare(source)
        self.assertIsNot(result, source)
        assert_frame_equal(result, source)
        self.assertEqual(preparer.profile(result), {
            "sensor_count": 0, "measurement_count": 0, "sensors": {}})

    def test_chronological_order_and_intervals_by_sensor(self):
        data = frame(row(4, sensor_id=2, seconds=100), row(3, seconds=30),
                     row(1), row(5, sensor_id=2, seconds=105), row(2, seconds=10))
        before = data.copy(deep=True)
        result = TimeSeriesPreparer().prepare(data)
        self.assertEqual(result.measurement_id.tolist(), [1, 2, 3, 4, 5])
        self.assertTrue(pd.isna(result.loc[0, "time_delta_seconds"]))
        self.assertTrue(pd.isna(result.loc[3, "time_delta_seconds"]))
        self.assertEqual(result.loc[[1, 2, 4], "time_delta_seconds"].tolist(), [10, 20, 5])
        self.assertEqual(str(result.timestamp.dt.tz), "UTC")
        assert_frame_equal(data, before)

    def test_timestamp_ties_have_zero_interval_and_id_order(self):
        result = TimeSeriesPreparer().prepare(frame(row(2), row(1)))
        self.assertEqual(result.measurement_id.tolist(), [1, 2])
        self.assertEqual(result.loc[1, "time_delta_seconds"], 0)

    def test_profile_regular_cadence(self):
        preparer = TimeSeriesPreparer()
        data = preparer.prepare(frame(row(1), row(2, seconds=10), row(3, seconds=20)))
        result = preparer.profile(data)
        self.assertEqual(result["sensor_count"], 1)
        self.assertEqual(result["measurement_count"], 3)
        self.assertEqual(result["sensors"][1], {
            "measurement_count": 3, "start_time": pd.Timestamp(START),
            "end_time": pd.Timestamp(START+timedelta(seconds=20)),
            "min_interval_seconds": 10.0, "max_interval_seconds": 10.0,
            "median_interval_seconds": 10.0,
        })

    def test_profile_irregular_cadence_and_singleton_sensor(self):
        preparer = TimeSeriesPreparer()
        data = preparer.prepare(frame(row(1), row(2, seconds=5), row(3, seconds=20),
                                      row(4, seconds=60), row(5, sensor_id=2, seconds=500)))
        result = preparer.profile(data)
        self.assertEqual((result["sensor_count"], result["measurement_count"]), (2, 5))
        sensor = result["sensors"][1]
        self.assertEqual((sensor["min_interval_seconds"], sensor["max_interval_seconds"],
                          sensor["median_interval_seconds"]), (5, 40, 15))
        for key in ("min_interval_seconds", "max_interval_seconds", "median_interval_seconds"):
            self.assertIsNone(result["sensors"][2][key])


class WindowFeatureTests(unittest.TestCase):
    def setUp(self):
        self.builder = WindowFeatureBuilder()
        self.source = frame(row(3, seconds=20, value=8), row(1, value=2), row(2, seconds=10, value=4))

    def values(self, column, expected):
        actual = self.builder.build(self.source, window_size=2)[column].tolist()
        for observed, wanted in zip(actual, expected, strict=True):
            if wanted is None:
                self.assertTrue(pd.isna(observed))
            else:
                self.assertAlmostEqual(observed, wanted)

    def test_empty_dataset(self):
        source = pd.DataFrame()
        result = self.builder.build(source)
        self.assertIsNot(result, source)
        assert_frame_equal(result, source)

    def test_invalid_window_size_nonempty_dataset(self):
        for size in (0, -1):
            with self.subTest(size=size), self.assertRaises(ValueError):
                self.builder.build(self.source, window_size=size)

    def test_invalid_window_size_empty_dataset(self):
        with self.assertRaises(ValueError):
            self.builder.build(pd.DataFrame(), window_size=0)

    def test_rolling_mean(self):
        self.values("rolling_mean", [2, 3, 6])

    def test_rolling_min(self):
        self.values("rolling_min", [2, 2, 4])

    def test_rolling_max(self):
        self.values("rolling_max", [2, 4, 8])

    def test_rolling_std_uses_sample_deviation(self):
        self.values("rolling_std", [None, math.sqrt(2), math.sqrt(8)])

    def test_rolling_count(self):
        self.values("rolling_count", [1, 2, 2])

    def test_value_delta(self):
        self.values("value_delta", [None, 2, 4])

    def test_window_one(self):
        one = self.builder.build(self.source, window_size=1)
        self.assertEqual(one.rolling_mean.tolist(), [2, 4, 8])
        self.assertEqual(one.rolling_count.tolist(), [1, 1, 1])
        self.assertTrue(one.rolling_std.isna().all())

    def test_window_larger_than_series(self):
        large = self.builder.build(self.source, window_size=10)
        self.assertAlmostEqual(large.rolling_mean.iloc[-1], 14/3)
        self.assertEqual(large.rolling_count.tolist(), [1, 2, 3])

    def test_strict_sensor_separation_and_no_contamination(self):
        other = frame(row(10, sensor_id=2, value=1000), row(11, sensor_id=2, seconds=10, value=2000))
        combined = pd.concat([other.iloc[:1], self.source, other.iloc[1:]], ignore_index=True)
        result = self.builder.build(combined, window_size=2)
        first = result[result.sensor_id == 1].reset_index(drop=True)
        assert_frame_equal(first, self.builder.build(self.source, window_size=2))
        second = result[result.sensor_id == 2].reset_index(drop=True)
        self.assertEqual(second.rolling_mean.tolist(), [1000, 1500])
        self.assertEqual(second.rolling_min.tolist(), [1000, 1000])
        self.assertEqual(second.rolling_max.tolist(), [1000, 2000])
        self.assertEqual(second.rolling_count.tolist(), [1, 2])
        self.assertTrue(pd.isna(second.value_delta.iloc[0]))
        self.assertEqual(second.value_delta.iloc[1], 1000)
        self.assertTrue(pd.isna(second.rolling_std.iloc[0]))
        self.assertAlmostEqual(second.rolling_std.iloc[1], math.sqrt(500000))

    def test_missing_values_are_not_counted_as_observations(self):
        source = self.source.sort_values("measurement_id").reset_index(drop=True)
        source.loc[1, "value"] = float("nan")
        result = self.builder.build(source, window_size=2)
        self.assertEqual(result.rolling_count.tolist(), [1, 1, 1])
        self.assertEqual(result.rolling_mean.tolist(), [2, 2, 8])

    def test_input_is_unchanged_and_features_added(self):
        before = self.source.copy(deep=True)
        result = self.builder.build(self.source)
        self.assertTrue(set(FEATURE_COLUMNS).issubset(result.columns))
        assert_frame_equal(self.source, before)
