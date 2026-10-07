import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.variability_features import VariabilityFeatureBuilder
from feature_engineering.support import assert_values


def rolling_frame():
    return pd.DataFrame({
        "rolling_min": [2, -4, 7], "rolling_max": [8, -2, 7],
        "rolling_mean": [4, -3, 7], "rolling_std": [2, 1, 0],
    }, index=[9, 3, 5])


class VariabilityFeatureTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        for source in (pd.DataFrame(), rolling_frame().iloc[:0]):
            result = VariabilityFeatureBuilder().build(source)
            self.assertIsNot(result, source)
            assert_frame_equal(result, source)

    def test_range_cv_and_input_preservation(self):
        source = rolling_frame()
        before = source.copy(deep=True)
        result = VariabilityFeatureBuilder().build(source)
        assert_values(self, result.rolling_range, [6, 2, 0])
        assert_values(self, result.rolling_cv, [0.5, -1 / 3, 0])
        self.assertEqual(result.index.tolist(), [9, 3, 5])
        assert_frame_equal(source, before)

    def test_zero_mean_and_missing_statistics_produce_na(self):
        source = pd.DataFrame({
            "rolling_min": [-1, 0, 1, 1], "rolling_max": [1, 0, 1, 1],
            "rolling_mean": [0, 0, float("nan"), 1],
            "rolling_std": [1, 0, 1, float("nan")],
        })
        self.assertTrue(VariabilityFeatureBuilder().build(source).rolling_cv.isna().all())

    def test_missing_required_columns(self):
        for column in rolling_frame().columns:
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                VariabilityFeatureBuilder().build(rolling_frame().drop(columns=column))
