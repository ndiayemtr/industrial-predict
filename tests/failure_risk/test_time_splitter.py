import unittest
from datetime import timedelta, timezone

import pandas as pd
from pandas.testing import assert_frame_equal

from app.ml.time_splitter import TemporalDatasetSplitter
from failure_risk.support import START, measurements


class TemporalSplitterTests(unittest.TestCase):
    def test_empty_dataset_returns_independent_copies(self):
        source = measurements().iloc[:0]
        parts = TemporalDatasetSplitter().split(source)
        for part in parts:
            self.assertIsNot(part, source)
            assert_frame_equal(part, source)
        self.assertEqual(len({id(part) for part in parts}), 3)

    def test_unsorted_data_has_chronological_train_validation_test(self):
        source = measurements(tuple(range(10))).iloc[[8, 0, 4, 9, 1, 7, 3, 5, 2, 6]]
        before = source.copy(deep=True)
        train, validation, test = TemporalDatasetSplitter().split(source)
        self.assertEqual([len(train), len(validation), len(test)], [6, 2, 2])
        self.assertEqual(train.measurement_id.tolist(), [1, 2, 3, 4, 5, 6])
        self.assertEqual(validation.measurement_id.tolist(), [7, 8])
        self.assertEqual(test.measurement_id.tolist(), [9, 10])
        self.assertLess(train.timestamp.max(), validation.timestamp.min())
        self.assertLess(validation.timestamp.max(), test.timestamp.min())
        assert_frame_equal(pd.concat([train, validation, test]), measurements(tuple(range(10))))
        assert_frame_equal(source, before)

    def test_custom_ratios_and_zero_validation(self):
        source = measurements(tuple(range(10)))
        self.assertEqual([len(part) for part in TemporalDatasetSplitter().split(source, train_ratio=0.5, validation_ratio=0.3)], [5, 3, 2])
        self.assertEqual([len(part) for part in TemporalDatasetSplitter().split(source, train_ratio=0.5, validation_ratio=0)], [5, 0, 5])

    def test_fractional_split_uses_floor_and_keeps_every_row(self):
        parts = TemporalDatasetSplitter().split(measurements(tuple(range(7))))
        self.assertEqual([len(part) for part in parts], [4, 1, 2])
        self.assertEqual(pd.concat(parts).measurement_id.tolist(), list(range(1, 8)))

    def test_invalid_ratios(self):
        for parameters in ({"train_ratio": 0}, {"train_ratio": -0.1}, {"train_ratio": 1},
                           {"validation_ratio": -0.1}, {"validation_ratio": 1},
                           {"train_ratio": 0.7, "validation_ratio": 0.3},
                           {"train_ratio": 0.8, "validation_ratio": 0.3}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                TemporalDatasetSplitter().split(measurements(), **parameters)

    def test_missing_timestamp_column(self):
        with self.assertRaisesRegex(ValueError, "timestamp"):
            TemporalDatasetSplitter().split(measurements().drop(columns="timestamp"))

    def test_mixed_timezones_sorted_by_instant_and_normalized_to_utc(self):
        source = measurements(tuple(range(10)))
        source["timestamp"] = [
            (START + timedelta(hours=hour)).astimezone(timezone(timedelta(hours=5 if hour % 2 else -7)))
            for hour in range(10)
        ]
        parts = TemporalDatasetSplitter().split(source.iloc[::-1])
        result = pd.concat(parts)
        self.assertEqual(str(result.timestamp.dt.tz), "UTC")
        self.assertEqual(result.timestamp.tolist(), [pd.Timestamp(START + timedelta(hours=h)) for h in range(10)])
