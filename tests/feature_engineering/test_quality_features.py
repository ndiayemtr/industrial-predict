import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.quality_features import QualityFeatureBuilder
from feature_engineering.support import QUALITY_COLUMNS, measurements


class QualityFeatureTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        for source in (pd.DataFrame(), measurements().iloc[:0]):
            result = QualityFeatureBuilder().build(source)
            self.assertIsNot(result, source)
            assert_frame_equal(result, source)

    def test_flags_and_duplicate_or_truth_table(self):
        source = measurements()
        source["gap_detected"] = [False, True, False, True]
        source["data_quality_status"] = ["valid", "warning", "invalid", "unknown"]
        source["duplicate_measurement_id"] = [False, False, True, True]
        source["duplicate_sensor_timestamp"] = [False, True, False, True]
        source["outlier_detected"] = [True, False, False, True]
        source.index = [8, 2, 9, 3]
        before = source.copy(deep=True)
        result = QualityFeatureBuilder().build(source)
        for column, expected in (
            ("is_gap", [False, True, False, True]),
            ("is_quality_warning", [False, True, False, False]),
            ("is_quality_invalid", [False, False, True, False]),
            ("is_duplicate", [False, True, True, True]),
            ("is_outlier", [True, False, False, True]),
        ):
            with self.subTest(column=column):
                self.assertEqual(result[column].tolist(), expected)
        self.assertEqual(result.index.tolist(), [8, 2, 9, 3])
        assert_frame_equal(source, before)

    def test_all_absent_flags_default_to_false(self):
        result = QualityFeatureBuilder().build(measurements())
        for column in QUALITY_COLUMNS:
            self.assertEqual(result[column].tolist(), [False] * 4)
            self.assertEqual(result[column].dtype, bool)

    def test_each_optional_flag_can_be_present_alone(self):
        for source_column, target in (
            ("gap_detected", "is_gap"), ("outlier_detected", "is_outlier"),
            ("duplicate_measurement_id", "is_duplicate"),
            ("duplicate_sensor_timestamp", "is_duplicate"),
        ):
            with self.subTest(column=source_column):
                source = measurements((1, 2))
                source[source_column] = [False, True]
                result = QualityFeatureBuilder().build(source)
                self.assertEqual(result[target].tolist(), [False, True])
                for column in set(QUALITY_COLUMNS) - {target}:
                    self.assertFalse(result[column].any())
