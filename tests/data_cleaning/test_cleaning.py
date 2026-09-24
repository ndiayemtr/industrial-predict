import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.quality_rules import DataQualityStatus, MeasurementQualityPolicy
from app.data_pipeline.quality_filter import MeasurementQualityFilter
from app.data_pipeline.duplicate_detector import DuplicateMeasurementDetector
from app.data_pipeline.gap_detector import MeasurementGapDetector
from app.data_pipeline.silent_sensor_detector import SilentSensorDetector
from app.data_pipeline.outlier_detector import MeasurementOutlierDetector
from app.data_pipeline.cleaner import MeasurementDataCleaner
from app.data_pipeline.cleaning_report import MeasurementCleaningReport


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def dataset(values=(1, 2, 3, 4, 100), *, sensor=1, seconds=None, qualities=None, ids=None):
    size = len(values)
    return pd.DataFrame({
        "measurement_id": ids if ids is not None else list(range(1, size+1)),
        "sensor_id": [sensor]*size,
        "timestamp": [START+timedelta(seconds=s) for s in
                      (seconds if seconds is not None else range(0, size*10, 10))],
        "value": list(values),
        "quality": qualities if qualities is not None else ["good"]*size,
    })


class QualityTests(unittest.TestCase):
    def test_all_business_qualities(self):
        for quality, expected in (("good", "valid"), ("suspect", "warning"),
                                  ("estimated", "warning"), ("bad", "invalid"), ("missing", "invalid")):
            with self.subTest(quality=quality):
                result = MeasurementQualityPolicy.classify_quality(quality)
                self.assertIsInstance(result, DataQualityStatus)
                self.assertEqual(result.value, expected)

    def test_unknown_quality_is_invalid(self):
        for quality in ("custom", "", " "):
            with self.subTest(quality=quality):
                self.assertEqual(MeasurementQualityPolicy.classify_quality(quality), DataQualityStatus.INVALID)

    def test_quality_normalization(self):
        self.assertEqual(MeasurementQualityPolicy.classify_quality(" GOOD "), DataQualityStatus.VALID)
        self.assertEqual(MeasurementQualityPolicy.classify_quality(" Suspect "), DataQualityStatus.WARNING)

    def test_finite_numbers(self):
        for value in (0, -12.5, 12.5, 1e300):
            with self.subTest(value=value):
                self.assertTrue(MeasurementQualityPolicy.is_valid_numeric_value(value))

    def test_nonfinite_numbers(self):
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                self.assertFalse(MeasurementQualityPolicy.is_valid_numeric_value(value))

    def test_filter_with_warnings(self):
        source = dataset(range(6), qualities=["good", "suspect", "estimated", "bad", "missing", "custom"])
        result = MeasurementQualityFilter().filter_usable(source)
        self.assertEqual(result.measurement_id.tolist(), [1, 2, 3])
        self.assertEqual(result.data_quality_status.tolist(), ["valid", "warning", "warning"])

    def test_filter_without_warnings(self):
        source = dataset(range(3), qualities=["suspect", "good", "estimated"])
        result = MeasurementQualityFilter().filter_usable(source, include_warnings=False)
        self.assertEqual(result.measurement_id.tolist(), [2])
        self.assertEqual(result.index.tolist(), [0])

    def test_empty_filter(self):
        result = MeasurementQualityFilter().filter_usable(pd.DataFrame())
        self.assertTrue(result.empty)
        self.assertIn("data_quality_status", result.columns)

    def test_classification_does_not_mutate_input(self):
        source = dataset()
        before = source.copy(deep=True)
        result = MeasurementQualityFilter().classify(source)
        self.assertEqual(result.data_quality_status.tolist(), ["valid"]*5)
        assert_frame_equal(source, before)


class DuplicateTests(unittest.TestCase):
    def test_duplicate_measurement_ids_mark_all_members(self):
        result = DuplicateMeasurementDetector().detect(dataset(ids=[1, 1, 3, 4, 5]))
        self.assertEqual(result.duplicate_measurement_id.tolist(), [True, True, False, False, False])
        self.assertFalse(result.duplicate_sensor_timestamp.any())

    def test_duplicate_sensor_timestamp_with_distinct_ids(self):
        result = DuplicateMeasurementDetector().detect(dataset(seconds=[0, 0, 10, 20, 30]))
        self.assertEqual(result.duplicate_sensor_timestamp.tolist(), [True, True, False, False, False])
        self.assertFalse(result.duplicate_measurement_id.any())

    def test_identical_timestamp_on_different_sensors_is_not_duplicate(self):
        source = pd.concat([dataset((1,), sensor=1, ids=[1]), dataset((2,), sensor=2, ids=[2])], ignore_index=True)
        self.assertFalse(DuplicateMeasurementDetector().detect(source).duplicate_sensor_timestamp.any())

    def test_summary_counts_all_flagged_rows_not_extra_copies(self):
        result = DuplicateMeasurementDetector().summarize(dataset(ids=[1, 1, 3, 4, 5], seconds=[0, 0, 10, 20, 30]))
        self.assertEqual(result, {"duplicate_measurement_id_count": 2, "duplicate_sensor_timestamp_count": 2})

    def test_empty_duplicates(self):
        detector = DuplicateMeasurementDetector()
        result = detector.detect(pd.DataFrame())
        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), ["duplicate_measurement_id", "duplicate_sensor_timestamp"])
        self.assertEqual(detector.summarize(pd.DataFrame()),
                         {"duplicate_measurement_id_count": 0, "duplicate_sensor_timestamp_count": 0})


class GapTests(unittest.TestCase):
    def test_regular_cadence_has_no_gaps(self):
        result = MeasurementGapDetector().detect(dataset())
        self.assertEqual(result.expected_interval_seconds.tolist(), [10]*5)
        self.assertFalse(result.gap_detected.any())

    def test_gap_after_missing_observations(self):
        source = dataset(seconds=[0, 10, 20, 50, 60]).iloc[::-1]
        result = MeasurementGapDetector().detect(source)
        self.assertEqual(result.measurement_id.tolist(), [1, 2, 3, 4, 5])
        self.assertEqual(result.gap_detected.tolist(), [False, False, False, True, False])
        self.assertEqual(MeasurementGapDetector().summarize(source), {"gap_count": 1, "sensors_with_gaps": 1})

    def test_multi_sensor_cadences_are_separate(self):
        source = pd.concat([dataset(seconds=[0, 10, 20, 50, 60]),
                            dataset(sensor=2, seconds=[0, 100, 200, 300, 400])], ignore_index=True)
        result = MeasurementGapDetector().detect(source)
        self.assertEqual(result[result.sensor_id == 2].expected_interval_seconds.tolist(), [100]*5)
        self.assertFalse(result[result.sensor_id == 2].gap_detected.any())
        self.assertEqual(MeasurementGapDetector().summarize(source), {"gap_count": 1, "sensors_with_gaps": 1})

    def test_exact_threshold_is_not_gap(self):
        result = MeasurementGapDetector().detect(dataset(seconds=[0, 10, 20, 35, 45]), gap_multiplier=1.5)
        self.assertFalse(result.gap_detected.any())

    def test_invalid_multiplier_even_on_empty_data(self):
        for source in (pd.DataFrame(), dataset()):
            for multiplier in (1, 0, -1):
                with self.subTest(empty=source.empty, multiplier=multiplier), self.assertRaises(ValueError):
                    MeasurementGapDetector().detect(source, gap_multiplier=multiplier)

    def test_empty_gaps(self):
        detector = MeasurementGapDetector()
        self.assertTrue(detector.detect(pd.DataFrame()).empty)
        self.assertEqual(detector.summarize(pd.DataFrame()), {"gap_count": 0, "sensors_with_gaps": 0})

    def test_single_measurement_has_no_inferred_cadence(self):
        result = MeasurementGapDetector().detect(dataset((1,)))
        self.assertTrue(pd.isna(result.expected_interval_seconds.iloc[0]))
        self.assertFalse(result.gap_detected.iloc[0])


class SilenceTests(unittest.TestCase):
    def test_silent_sensor(self):
        result = SilentSensorDetector().detect(dataset(), reference_time=START+timedelta(seconds=80))
        self.assertEqual(result.silence_seconds.tolist(), [40])
        self.assertTrue(result.silent.iloc[0])

    def test_non_silent_and_exact_threshold(self):
        for seconds in (50, 70):
            with self.subTest(seconds=seconds):
                result = SilentSensorDetector().detect(dataset(), reference_time=START+timedelta(seconds=seconds))
                self.assertFalse(result.silent.iloc[0])

    def test_multiple_sensors_have_independent_cadence(self):
        source = pd.concat([dataset(), dataset(sensor=2, seconds=[0, 100, 200, 300, 400])], ignore_index=True)
        detector = SilentSensorDetector()
        result = detector.detect(source, reference_time=START+timedelta(seconds=420)).set_index("sensor_id")
        self.assertTrue(result.loc[1, "silent"])
        self.assertFalse(result.loc[2, "silent"])
        self.assertEqual(result.expected_interval_seconds.tolist(), [10, 100])
        self.assertEqual(detector.summarize(source, reference_time=START+timedelta(seconds=420)),
                         {"sensor_count": 2, "silent_sensor_count": 1})

    def test_reference_timezone_required(self):
        with self.assertRaises(ValueError):
            SilentSensorDetector().detect(dataset(), reference_time=START.replace(tzinfo=None))

    def test_reference_timezone_required_even_on_empty_data(self):
        with self.assertRaises(ValueError):
            SilentSensorDetector().detect(pd.DataFrame(), reference_time=START.replace(tzinfo=None))

    def test_reference_offset_is_normalized(self):
        instant = START+timedelta(seconds=80)
        detector = SilentSensorDetector()
        assert_frame_equal(detector.detect(dataset(), reference_time=instant), detector.detect(
            dataset(), reference_time=instant.astimezone(timezone(timedelta(hours=5, minutes=30)))))

    def test_invalid_multiplier_even_on_empty_data(self):
        for source in (pd.DataFrame(), dataset()):
            for multiplier in (1, 0, -1):
                with self.subTest(empty=source.empty, multiplier=multiplier), self.assertRaises(ValueError):
                    SilentSensorDetector().detect(source, reference_time=START, silence_multiplier=multiplier)

    def test_empty_silence_report(self):
        detector = SilentSensorDetector()
        result = detector.detect(pd.DataFrame(), reference_time=START)
        self.assertEqual(list(result.columns), ["sensor_id", "last_measurement_time",
                         "expected_interval_seconds", "silence_seconds", "silent"])
        self.assertTrue(result.empty)
        self.assertEqual(detector.summarize(pd.DataFrame(), reference_time=START),
                         {"sensor_count": 0, "silent_sensor_count": 0})


class OutlierTests(unittest.TestCase):
    def test_iqr_bounds_and_outlier(self):
        result = MeasurementOutlierDetector().detect(dataset())
        # Q1=2, Q3=4, IQR=2; bounds [-1, 7].
        self.assertEqual(result.outlier_lower_bound.tolist(), [-1]*5)
        self.assertEqual(result.outlier_upper_bound.tolist(), [7]*5)
        self.assertEqual(result.outlier_detected.tolist(), [False, False, False, False, True])
        self.assertEqual(MeasurementOutlierDetector().summarize(dataset()),
                         {"outlier_count": 1, "sensors_with_outliers": 1})

    def test_strict_sensor_separation(self):
        source = pd.concat([dataset(), dataset((1000, 1001, 1002, 1003, 1004), sensor=2)], ignore_index=True)
        result = MeasurementOutlierDetector().detect(source)
        self.assertEqual(result[result.sensor_id == 1].outlier_detected.tolist(), [False]*4+[True])
        self.assertFalse(result[result.sensor_id == 2].outlier_detected.any())
        self.assertEqual(result[result.sensor_id == 2].outlier_lower_bound.tolist(), [998]*5)

    def test_duplicate_dataframe_indexes_do_not_mix_sensors(self):
        # concat commonly preserves each frame's original index.
        source = pd.concat([dataset(), dataset((1000, 1001, 1002, 1003, 1004), sensor=2)])
        result = MeasurementOutlierDetector().detect(source)
        self.assertEqual(result[result.sensor_id == 1].outlier_upper_bound.tolist(), [7]*5)
        self.assertFalse(result[result.sensor_id == 2].outlier_detected.any())

    def test_constant_values_are_not_outliers(self):
        result = MeasurementOutlierDetector().detect(dataset((4, 4, 4, 4)))
        self.assertFalse(result.outlier_detected.any())

    def test_multiplier_controls_detection(self):
        result = MeasurementOutlierDetector().detect(dataset(), iqr_multiplier=100)
        self.assertFalse(result.outlier_detected.any())

    def test_invalid_multiplier_even_on_empty_data(self):
        for source in (pd.DataFrame(), dataset()):
            for multiplier in (0, -1):
                with self.subTest(empty=source.empty, multiplier=multiplier), self.assertRaises(ValueError):
                    MeasurementOutlierDetector().detect(source, iqr_multiplier=multiplier)

    def test_empty_outliers(self):
        detector = MeasurementOutlierDetector()
        self.assertTrue(detector.detect(pd.DataFrame()).empty)
        self.assertEqual(detector.summarize(pd.DataFrame()), {"outlier_count": 0, "sensors_with_outliers": 0})


class CleanerTests(unittest.TestCase):
    def test_invalid_qualities_removed(self):
        source = dataset(range(6), qualities=["good", "bad", "missing", "unknown", "suspect", "estimated"])
        result = MeasurementDataCleaner().clean(source)
        self.assertEqual(result.measurement_id.tolist(), [1, 5, 6])

    def test_warning_option(self):
        source = dataset((1, 2, 3), qualities=["good", "suspect", "estimated"])
        self.assertEqual(MeasurementDataCleaner().clean(source, include_warnings=False).measurement_id.tolist(), [1])

    def test_duplicate_id_removal_can_be_disabled(self):
        source = dataset(ids=[1, 1, 3, 4, 5])
        cleaner = MeasurementDataCleaner()
        self.assertEqual(cleaner.clean(source).measurement_id.tolist(), [3, 4, 5])
        self.assertEqual(cleaner.clean(source, remove_duplicate_measurement_ids=False).measurement_id.tolist(), [1, 1, 3, 4, 5])

    def test_duplicate_timestamp_removal_can_be_disabled(self):
        source = dataset(seconds=[0, 0, 10, 20, 30])
        cleaner = MeasurementDataCleaner()
        self.assertEqual(cleaner.clean(source).measurement_id.tolist(), [3, 4, 5])
        self.assertEqual(cleaner.clean(source, remove_duplicate_sensor_timestamps=False).measurement_id.tolist(), [1, 2, 3, 4, 5])

    def test_outliers_kept_by_default_and_explicit_false(self):
        cleaner = MeasurementDataCleaner()
        self.assertEqual(cleaner.clean(dataset()).value.tolist(), [1, 2, 3, 4, 100])
        self.assertEqual(cleaner.clean(dataset(), remove_outliers=False).value.tolist(), [1, 2, 3, 4, 100])

    def test_outlier_removal_and_multiplier(self):
        cleaner = MeasurementDataCleaner()
        self.assertEqual(cleaner.clean(dataset(), remove_outliers=True).value.tolist(), [1, 2, 3, 4])
        self.assertEqual(len(cleaner.clean(dataset(), remove_outliers=True, iqr_multiplier=100)), 5)

    def test_all_optional_removals_disabled(self):
        source = dataset(ids=[1, 1, 3, 4, 5], seconds=[0, 0, 10, 20, 30])
        result = MeasurementDataCleaner().clean(source, remove_duplicate_measurement_ids=False,
                                                remove_duplicate_sensor_timestamps=False, remove_outliers=False)
        self.assertEqual(result.measurement_id.tolist(), [1, 1, 3, 4, 5])

    def test_quality_filter_runs_before_duplicates(self):
        source = dataset((1, 99), ids=[1, 1], qualities=["good", "bad"])
        self.assertEqual(MeasurementDataCleaner().clean(source).value.tolist(), [1])

    def test_empty_and_all_invalid_data(self):
        cleaner = MeasurementDataCleaner()
        self.assertTrue(cleaner.clean(pd.DataFrame()).empty)
        source = dataset((1, 2), qualities=["bad", "missing"])
        self.assertTrue(cleaner.clean(source, remove_outliers=True).empty)

    def test_cleaning_does_not_mutate_source(self):
        source = dataset()
        before = source.copy(deep=True)
        result = MeasurementDataCleaner().clean(source, remove_outliers=True)
        assert_frame_equal(source, before)
        self.assertEqual(result.index.tolist(), [0, 1, 2, 3])


class CleaningReportTests(unittest.TestCase):
    def test_empty_report(self):
        self.assertEqual(MeasurementCleaningReport().build(pd.DataFrame()), {
            "initial_row_count": 0, "final_row_count": 0, "removed_row_count": 0,
            "invalid_quality_count": 0, "duplicate_measurement_id_count": 0,
            "duplicate_sensor_timestamp_count": 0, "outlier_count": 0})

    def test_report_counts_overlapping_reasons_without_double_removal(self):
        source = dataset((1, 2, 3, 4, 100, 0, 8, 9), ids=[1, 2, 3, 4, 5, 6, 7, 7],
                         seconds=[0, 10, 20, 30, 40, 50, 60, 60],
                         qualities=["good"]*5+["bad", "good", "good"])
        result = MeasurementCleaningReport().build(source, remove_outliers=True)
        self.assertEqual(result, {"initial_row_count": 8, "final_row_count": 4, "removed_row_count": 4,
                                 "invalid_quality_count": 1, "duplicate_measurement_id_count": 2,
                                 "duplicate_sensor_timestamp_count": 2, "outlier_count": 1})

    def test_outlier_count_is_detection_not_removal_count(self):
        result = MeasurementCleaningReport().build(dataset(), remove_outliers=False)
        self.assertEqual((result["outlier_count"], result["removed_row_count"], result["final_row_count"]), (1, 0, 5))

    def test_report_matches_cleaner_for_all_boolean_options(self):
        from itertools import product
        source = dataset((1, 2, 3, 4, 100, 9, 9, 0), ids=[1, 2, 3, 4, 5, 6, 6, 8],
                         seconds=[0, 10, 20, 30, 40, 50, 50, 60],
                         qualities=["good", "suspect", "estimated", "good", "good", "good", "good", "bad"])
        names = ("include_warnings", "remove_duplicate_measurement_ids", "remove_duplicate_sensor_timestamps", "remove_outliers")
        for flags in product((False, True), repeat=4):
            options = dict(zip(names, flags))
            with self.subTest(options=options):
                report = MeasurementCleaningReport().build(source, **options)
                self.assertEqual(report["initial_row_count"], 8)
                self.assertEqual(report["final_row_count"], len(MeasurementDataCleaner().clean(source, **options)))
                self.assertEqual(report["removed_row_count"], 8-report["final_row_count"])
                self.assertGreaterEqual(report["removed_row_count"], 0)
