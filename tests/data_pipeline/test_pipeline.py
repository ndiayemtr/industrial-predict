import unittest
from datetime import timedelta
from unittest.mock import create_autospec

# Reuse the test environment setup before importing modules that load the DB.
from dashboard.support import DatabaseCase
from data_pipeline.support import BASE_COLUMNS, FEATURE_COLUMNS, START, row
from app.data_pipeline.extractor import MeasurementDataExtractor
from app.data_pipeline.pipeline import MeasurementDataPipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = MeasurementDataPipeline(None)
        self.extractor = create_autospec(MeasurementDataExtractor, instance=True)
        self.pipeline.extractor = self.extractor
        self.extractor.extract.return_value = [row(3, seconds=20, value=8),
                                               row(1, value=2), row(2, seconds=10, value=4)]

    def test_complete_transform_orchestration_and_derived_columns(self):
        result = self.pipeline.build()
        self.assertEqual(list(result.columns), BASE_COLUMNS+["time_delta_seconds"]+FEATURE_COLUMNS)
        self.assertEqual(result.measurement_id.tolist(), [1, 2, 3])
        self.assertEqual(result.time_delta_seconds.iloc[1:].tolist(), [10, 10])
        self.assertEqual(result.rolling_count.tolist(), [1, 2, 3])
        self.assertAlmostEqual(result.rolling_mean.iloc[-1], 14/3)
        self.assertEqual(str(result.timestamp.dt.tz), "UTC")

    def test_every_filter_forwarded_to_extractor(self):
        filters = dict(company_id=11, site_id=12, equipment_id=13, sensor_id=14,
                       start_time=START, end_time=START+timedelta(days=1))
        self.pipeline.build(**filters, window_size=2)
        self.extractor.extract.assert_called_once_with(**filters)

    def test_optional_filters_default_to_none(self):
        self.pipeline.build()
        self.extractor.extract.assert_called_once_with(
            company_id=None, site_id=None, equipment_id=None, sensor_id=None,
            start_time=None, end_time=None)

    def test_window_size_controls_final_values(self):
        result = self.pipeline.build(window_size=2)
        self.assertEqual(result.rolling_mean.tolist(), [2, 3, 6])
        self.assertEqual(result.rolling_count.tolist(), [1, 2, 2])
        self.assertEqual(result.value_delta.iloc[1:].tolist(), [2, 4])

    def test_invalid_window_size_propagates(self):
        with self.assertRaises(ValueError):
            self.pipeline.build(window_size=-1)

    def test_empty_extraction(self):
        self.extractor.extract.return_value = []
        result = self.pipeline.build()
        self.assertTrue(result.empty)
        self.assertEqual(self.pipeline.analyze_quality(result)["row_count"], 0)
        self.assertEqual(self.pipeline.profile_time_series(result)["sensor_count"], 0)

    def test_quality_and_temporal_profile_of_final_dataset(self):
        result = self.pipeline.build()
        report = self.pipeline.analyze_quality(result)
        profile = self.pipeline.profile_time_series(result)
        self.assertEqual(report["row_count"], 3)
        self.assertEqual(report["quality_distribution"], {"good": 3})
        self.assertEqual(profile["measurement_count"], 3)
        self.assertEqual(profile["sensors"][1]["median_interval_seconds"], 10)


class PipelineSQLIntegrationTests(DatabaseCase):
    def test_sql_extraction_through_final_features(self):
        self.measurement(sensor_id=1, timestamp=START, value=2)
        self.measurement(sensor_id=1, timestamp=START+timedelta(seconds=10), value=4)
        self.measurement(sensor_id=2, timestamp=START, value=1000)
        self.measurement(sensor_id=5, timestamp=START, value=9999)
        pipeline = MeasurementDataPipeline(self.db)
        result = pipeline.build(company_id=1, site_id=1, equipment_id=1, window_size=2)
        self.assertEqual(result.sensor_id.tolist(), [1, 1, 2])
        self.assertEqual(result.rolling_mean.tolist(), [2, 3, 1000])
        self.assertEqual(result.rolling_count.tolist(), [1, 2, 1])
        self.assertTrue(set(FEATURE_COLUMNS+["time_delta_seconds"]).issubset(result.columns))
