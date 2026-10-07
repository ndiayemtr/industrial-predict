import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.anomaly_detection.equipment_detector import EquipmentAnomalyDetector
from anomaly_detection.support import EQUIPMENT_COLUMNS


def equipment_frame():
    return pd.DataFrame({
        "equipment_id": [20, 10, 10, 30, 10, 20], "sensor_id": [3, 1, 1, 4, 2, 3],
        "anomaly_score": [0.4, 0.6, 0.1, 1.0, 0.8, 0.0],
        "is_anomaly": [False, True, False, True, True, False],
    }, index=[8, 2, 9, 4, 6, 1])


class EquipmentDetectorTests(unittest.TestCase):
    def test_empty_frame_has_summary_schema(self):
        for source in (pd.DataFrame(), equipment_frame().iloc[:0]):
            result = EquipmentAnomalyDetector().summarize(source)
            self.assertTrue(result.empty)
            self.assertEqual(result.columns.tolist(), EQUIPMENT_COLUMNS)

    def test_multiple_equipment_counts_ratios_scores_and_flags(self):
        source = equipment_frame()
        before = source.copy(deep=True)
        result = EquipmentAnomalyDetector().summarize(source)
        self.assertEqual(result.columns.tolist(), EQUIPMENT_COLUMNS)
        self.assertEqual(result.equipment_id.tolist(), [10, 20, 30])
        self.assertEqual(result.sensor_count.tolist(), [2, 1, 1])
        self.assertEqual(result.measurement_count.tolist(), [3, 2, 1])
        self.assertEqual(result.anomaly_count.tolist(), [2, 0, 1])
        self.assertEqual(result.anomaly_ratio.tolist(), [2 / 3, 0, 1])
        self.assertEqual(result.max_anomaly_score.tolist(), [0.8, 0.4, 1])
        self.assertEqual(result.mean_anomaly_score.tolist(), [0.5, 0.2, 1])
        self.assertEqual(result.equipment_anomaly.tolist(), [True, False, True])
        assert_frame_equal(source, before)

    def test_missing_required_columns(self):
        for column in equipment_frame().columns:
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                EquipmentAnomalyDetector().summarize(equipment_frame().drop(columns=column))
