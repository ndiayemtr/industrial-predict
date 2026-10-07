import math
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.equipment_features import EquipmentFeatureBuilder
from app.data_pipeline.quality_features import QualityFeatureBuilder
from feature_engineering.support import EQUIPMENT_COLUMNS, measurements


class EquipmentFeatureTests(unittest.TestCase):
    def test_empty_frame_has_aggregation_schema(self):
        for source in (pd.DataFrame(), measurements().iloc[:0]):
            result = EquipmentFeatureBuilder().build(source)
            self.assertTrue(result.empty)
            self.assertEqual(result.columns.tolist(), EQUIPMENT_COLUMNS)

    def test_counts_statistics_and_ratios_per_equipment(self):
        source = pd.concat([
            measurements((2, 4)), measurements((6, 8), sensor=2),
            measurements((100,), sensor=3, equipment=20),
        ]).iloc[[4, 2, 0, 3, 1]]
        source["is_outlier"] = source.measurement_id.isin([101, 301])
        source["is_gap"] = source.measurement_id.isin([102, 201])
        source["is_quality_invalid"] = source.measurement_id.isin([202, 301])
        before = source.copy(deep=True)
        result = EquipmentFeatureBuilder().build(source)
        self.assertEqual(result.columns.tolist(), EQUIPMENT_COLUMNS)
        self.assertEqual(result.equipment_id.tolist(), [10, 20])
        group = result.set_index("equipment_id")
        self.assertEqual(group.sensor_count.tolist(), [2, 1])
        self.assertEqual(group.measurement_count.tolist(), [4, 1])
        self.assertEqual(group.value_mean.tolist(), [5, 100])
        self.assertAlmostEqual(group.loc[10, "value_std"], math.sqrt(20 / 3))
        self.assertTrue(pd.isna(group.loc[20, "value_std"]))
        self.assertEqual(group.outlier_ratio.tolist(), [0.25, 1])
        self.assertEqual(group.gap_ratio.tolist(), [0.5, 0])
        self.assertEqual(group.invalid_quality_ratio.tolist(), [0.25, 1])
        assert_frame_equal(source, before)

    def test_absent_flags_default_to_zero_ratios(self):
        result = EquipmentFeatureBuilder().build(measurements())
        for column in ("outlier_ratio", "gap_ratio", "invalid_quality_ratio"):
            self.assertEqual(result[column].tolist(), [0])

    def test_quality_flags_feed_equipment_ratios(self):
        source = measurements()
        source["gap_detected"] = [True, False, True, False]
        source["outlier_detected"] = [False, True, False, False]
        source["data_quality_status"] = ["valid", "warning", "invalid", "invalid"]
        result = EquipmentFeatureBuilder().build(QualityFeatureBuilder().build(source))
        self.assertEqual(result.outlier_ratio.tolist(), [0.25])
        self.assertEqual(result.gap_ratio.tolist(), [0.5])
        self.assertEqual(result.invalid_quality_ratio.tolist(), [0.5])

    def test_missing_required_columns(self):
        for column in ("equipment_id", "sensor_id", "value"):
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                EquipmentFeatureBuilder().build(measurements().drop(columns=column))
