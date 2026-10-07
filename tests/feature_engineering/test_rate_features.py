import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.rate_features import RateFeatureBuilder
from feature_engineering.support import assert_values


class RateFeatureTests(unittest.TestCase):
    def test_empty_frame_is_copied(self):
        for source in (pd.DataFrame(), pd.DataFrame(columns=["value_delta", "time_delta_seconds"])):
            result = RateFeatureBuilder().build(source)
            self.assertIsNot(result, source)
            assert_frame_equal(result, source)

    def test_rate_of_change_and_input_preservation(self):
        source = pd.DataFrame({"value_delta": [10, -6, 0], "time_delta_seconds": [2, 3, 4]}, index=[5, 1, 9])
        before = source.copy(deep=True)
        result = RateFeatureBuilder().build(source)
        assert_values(self, result.rate_of_change, [5, -2, 0])
        self.assertEqual(result.index.tolist(), [5, 1, 9])
        assert_frame_equal(source, before)

    def test_nonpositive_intervals_and_missing_values_produce_na(self):
        source = pd.DataFrame({
            "value_delta": [1, 0, 2, 3, None],
            "time_delta_seconds": [0, 0, -1, None, 10],
        })
        self.assertTrue(RateFeatureBuilder().build(source).rate_of_change.isna().all())

    def test_missing_required_columns(self):
        source = pd.DataFrame({"value_delta": [1], "time_delta_seconds": [10]})
        for column in source.columns:
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                RateFeatureBuilder().build(source.drop(columns=column))
