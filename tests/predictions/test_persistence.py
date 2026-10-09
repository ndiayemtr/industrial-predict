from pydantic import ValidationError

from predictions.support import PredictionCase, START, as_utc
from app.anomaly_detection.schemas import AnomalyResult
from app.ml.health_score.schemas import HealthScoreComponents, HealthScoreResult
from app.services.prediction_service import PredictionService


class PersistenceTests(PredictionCase):
    def setUp(self):
        super().setUp()
        self.service = PredictionService(self.db)

    def anomaly(self, **overrides):
        measurement = self.measurement()
        values = dict(equipment_id=1, sensor_id=1, measurement_id=measurement.id,
                      timestamp=START, anomaly_score=0.85, is_anomaly=True,
                      method="unified", reason="robust deviation")
        values.update(overrides)
        return AnomalyResult(**values)

    def test_persist_anomaly_full_mapping(self):
        anomaly = self.anomaly()
        record = self.service.persist_anomaly(anomaly)
        record_id = record.id
        self.db.expunge_all()
        record = self.predictions.get_by_id(record_id)
        for field, expected in dict(equipment_id=1, sensor_id=1, measurement_id=anomaly.measurement_id,
            prediction_type="anomaly", score=0.85, is_alert=True, model_name="unified",
            level=None, model_version=None, horizon_hours=None, details={"reason": "robust deviation"}).items():
            with self.subTest(field=field):
                self.assertEqual(getattr(record, field), expected)
        self.assertEqual(as_utc(record.predicted_at), START)

    def test_persist_anomaly_no_reason_and_false_alert(self):
        record = self.service.persist_anomaly(self.anomaly(reason=None, is_anomaly=False, anomaly_score=0.1))
        self.assertIsNone(record.details)
        self.assertFalse(record.is_alert)
        self.assertEqual(record.score, 0.1)

    def test_persist_anomaly_without_equipment_id(self):
        anomaly = self.anomaly(equipment_id=None)
        with self.assertRaisesRegex(ValueError, "equipment_id"):
            self.service.persist_anomaly(anomaly)
        self.assertEqual(self.predictions.count_all(equipment_id=1), 0)

    def test_persist_anomaly_nonexistent_equipment(self):
        with self.assertRaisesRegex(LookupError, "Equipment not found"):
            self.service.persist_anomaly(self.anomaly(equipment_id=999))

    def failure(self, **overrides):
        values = dict(equipment_id=1, failure_probability=0.75, risk_score=75,
                      risk_level="high", predicted_at=START)
        values.update(overrides)
        return self.service.persist_failure_risk(**values)

    def test_persist_failure_risk_full_mapping(self):
        measurement = self.measurement()
        measurement_id = measurement.id
        record = self.failure(sensor_id=1, measurement_id=measurement_id, model_name="random_forest",
                              model_version="v2", horizon_hours=24)
        record_id = record.id
        self.db.expunge_all()
        record = self.predictions.get_by_id(record_id)
        for field, expected in dict(equipment_id=1, sensor_id=1, measurement_id=measurement_id,
            prediction_type="failure_risk", score=75, level="high", is_alert=None,
            model_name="random_forest", model_version="v2", horizon_hours=24,
            details={"failure_probability": 0.75}).items():
            with self.subTest(field=field):
                self.assertEqual(getattr(record, field), expected)
        self.assertEqual(as_utc(record.predicted_at), START)

    def test_persist_failure_risk_invalid_probability_does_not_write(self):
        for probability in (-0.01, 1.01):
            with self.subTest(probability=probability), self.assertRaisesRegex(ValueError, "failure_probability"):
                self.failure(failure_probability=probability)
        self.assertEqual(self.predictions.count_all(equipment_id=1), 0)

    def test_persist_failure_risk_probability_endpoints_and_optional_defaults(self):
        for probability in (0, 1):
            record = self.failure(failure_probability=probability, risk_score=probability * 100,
                                  risk_level="low" if probability == 0 else "critical")
            self.assertEqual(record.details, {"failure_probability": probability})
            self.assertEqual(record.score, probability * 100)
            for field in ("sensor_id", "measurement_id", "model_name", "model_version", "horizon_hours", "is_alert"):
                self.assertIsNone(getattr(record, field))

    def test_persist_failure_risk_invalid_horizon(self):
        with self.assertRaises(ValidationError):
            self.failure(horizon_hours=0)
        self.assertEqual(self.predictions.count_all(equipment_id=1), 0)

    def test_persist_failure_risk_missing_equipment(self):
        with self.assertRaisesRegex(LookupError, "Equipment not found"):
            self.failure(equipment_id=999)

    def health(self, **overrides):
        values = dict(equipment_id=1, predicted_at=START,
            result=HealthScoreResult(78.5, "good", HealthScoreComponents(80, 90, 70, 60)))
        values.update(overrides)
        return self.service.persist_health_score(**values)

    def test_persist_health_score_mapping_and_components(self):
        record = self.health()
        record_id = record.id
        self.db.expunge_all()
        record = self.predictions.get_by_id(record_id)
        self.assertEqual(record.prediction_type, "health_score")
        self.assertEqual(record.equipment_id, 1)
        self.assertEqual(record.score, 78.5)
        self.assertEqual(record.level, "good")
        self.assertEqual(record.model_name, "health_score")
        self.assertEqual(record.details, {"components": {"failure_health": 80, "anomaly_health": 90,
                                                      "data_quality_health": 70, "maintenance_health": 60}})
        for field in ("sensor_id", "measurement_id", "model_version", "horizon_hours", "is_alert"):
            self.assertIsNone(getattr(record, field))
        self.assertEqual(as_utc(record.predicted_at), START)

    def test_persist_health_score_custom_metadata(self):
        record = self.health(model_name="weighted_health", model_version="v3")
        self.assertEqual(record.model_name, "weighted_health")
        self.assertEqual(record.model_version, "v3")

    def test_persist_health_score_missing_equipment(self):
        with self.assertRaisesRegex(LookupError, "Equipment not found"):
            self.health(equipment_id=999)
