import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.supervised_dataset import FailureRiskDatasetBuilder
from failure_risk.support import maintenance, measurements


class SupervisedDatasetTests(unittest.TestCase):
    def test_empty_dataset_is_copied(self):
        for source in (pd.DataFrame(), measurements().iloc[:0]):
            result = FailureRiskDatasetBuilder().build(source, pd.DataFrame())
            self.assertIsNot(result, source)
            assert_frame_equal(result, source)

    def test_missing_feature_columns(self):
        for column in ("equipment_id", "timestamp"):
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                FailureRiskDatasetBuilder().build(measurements().drop(columns=column), maintenance())

    def test_positive_negative_labels_int8_and_features_preserved(self):
        source = measurements()
        before = source.copy(deep=True)
        result = FailureRiskDatasetBuilder().build(source, maintenance(), horizon_hours=12)
        self.assertEqual(result.failure_within_horizon.tolist(), [0, 1, 0])
        self.assertEqual(str(result.failure_within_horizon.dtype), "int8")
        assert_frame_equal(result[source.columns], source)
        assert_frame_equal(source, before)

    def test_summary_counts_and_ratio(self):
        builder = FailureRiskDatasetBuilder()
        result = builder.build(measurements(), maintenance(), horizon_hours=12)
        self.assertEqual(builder.summarize(result), {"row_count": 3, "positive_count": 1,
                                                   "negative_count": 2, "positive_ratio": 1 / 3})

    def test_empty_summary(self):
        self.assertEqual(FailureRiskDatasetBuilder().summarize(pd.DataFrame()),
                         {"row_count": 0, "positive_count": 0, "negative_count": 0, "positive_ratio": 0.0})

    def test_all_positive_and_all_negative_summary(self):
        for labels, expected in (([1, 1], 1.0), ([0, 0], 0.0)):
            with self.subTest(labels=labels):
                result = FailureRiskDatasetBuilder().summarize(pd.DataFrame({"failure_within_horizon": labels}))
                self.assertEqual(result["positive_count"], sum(labels))
                self.assertEqual(result["negative_count"], 2 - sum(labels))
                self.assertEqual(result["positive_ratio"], expected)

    def test_summary_missing_target(self):
        with self.assertRaisesRegex(ValueError, "failure_within_horizon"):
            FailureRiskDatasetBuilder().summarize(measurements())

    def test_invalid_horizon_propagates(self):
        with self.assertRaisesRegex(ValueError, "horizon_hours"):
            FailureRiskDatasetBuilder().build(measurements(), maintenance(), horizon_hours=0)

    def test_repeated_indices_keep_labels_and_summary_correct(self):
        source = pd.concat([measurements((0,), equipment=10), measurements((0,), equipment=20)])
        builder = FailureRiskDatasetBuilder()
        result = builder.build(source, maintenance((1,), equipment=10))
        self.assertEqual(result.failure_within_horizon.tolist(), [1, 0])
        self.assertEqual(str(result.failure_within_horizon.dtype), "int8")
        self.assertEqual(result.index.tolist(), [0, 0])
        self.assertEqual(builder.summarize(result), {"row_count": 2, "positive_count": 1,
                                                   "negative_count": 1, "positive_ratio": 0.5})
