import unittest

from pydantic import ValidationError

from predictions.support import START, create_data
from app.core.enums import PredictionType
from app.models.prediction_record import PredictionRecord
from app.schemas.prediction_record import PredictionRecordRead


class PredictionSchemaTests(unittest.TestCase):
    def test_valid_create_with_all_fields(self):
        data = create_data(sensor_id=2, measurement_id=3, level="high", is_alert=True,
            model_name="unified", model_version="v1", horizon_hours=24,
            details={"reason": "deviation", "nested": {"values": [1, 2]}})
        self.assertEqual(data.prediction_type, PredictionType.ANOMALY)
        self.assertEqual(data.model_dump(mode="json"), dict(equipment_id=1, sensor_id=2,
            measurement_id=3, prediction_type="anomaly", score=0.8, level="high", is_alert=True,
            model_name="unified", model_version="v1", horizon_hours=24.0,
            details={"reason": "deviation", "nested": {"values": [1, 2]}}, predicted_at="2026-01-01T00:00:00Z"))

    def test_each_invalid_identifier(self):
        for field in ("equipment_id", "sensor_id", "measurement_id"):
            for value in (0, -1):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError) as caught:
                    create_data(**{field: value})
                self.assertEqual(caught.exception.errors()[0]["loc"], (field,))

    def test_invalid_horizon(self):
        for value in (0, -0.1):
            with self.subTest(value=value), self.assertRaises(ValidationError) as caught:
                create_data(horizon_hours=value)
            self.assertEqual(caught.exception.errors()[0]["loc"], ("horizon_hours",))

    def test_optional_identifiers_horizon_and_details_default_to_none(self):
        data = create_data()
        for field in ("sensor_id", "measurement_id", "horizon_hours", "details", "level",
                      "is_alert", "model_name", "model_version"):
            self.assertIsNone(getattr(data, field))
        self.assertEqual(create_data(horizon_hours=0.5).horizon_hours, 0.5)

    def test_all_prediction_types_and_invalid_type(self):
        self.assertEqual([member.value for member in PredictionType], ["anomaly", "failure_risk", "health_score"])
        for kind in PredictionType:
            self.assertEqual(create_data(prediction_type=kind).prediction_type, kind)
        with self.assertRaises(ValidationError):
            create_data(prediction_type="unknown")

    def test_read_from_model_attributes(self):
        data = create_data()
        model = PredictionRecord(id=7, created_at=START, **data.model_dump(mode="python"))
        result = PredictionRecordRead.model_validate(model)
        self.assertEqual(result.id, 7)
        self.assertEqual(result.created_at, START)
        self.assertEqual(result.model_dump(exclude={"id", "created_at"}), data.model_dump())
