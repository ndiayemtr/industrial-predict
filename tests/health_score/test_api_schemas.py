import unittest

from pydantic import ValidationError

from app.schemas.health_score import HealthScoreRead, HealthScoreRequest
from health_score.support import expected_response, payload


class ApiSchemaTests(unittest.TestCase):
    def test_valid_payload_and_optional_defaults(self):
        self.assertEqual(HealthScoreRequest(**payload()).model_dump(), payload())
        request = HealthScoreRequest(failure_probability=0, anomaly_score=1,
                                    valid_count=0, warning_count=1, invalid_count=0)
        self.assertFalse(request.corrective_in_progress)
        self.assertFalse(request.overdue_maintenance)
        self.assertFalse(request.planned_soon)

    def test_probability_and_anomaly_closed_intervals(self):
        for field in ("failure_probability", "anomaly_score"):
            for value in (0, 1):
                with self.subTest(field=field, value=value):
                    self.assertEqual(getattr(HealthScoreRequest(**payload(**{field: value})), field), value)
            for value in (-0.01, 1.01):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError) as caught:
                    HealthScoreRequest(**payload(**{field: value}))
                self.assertEqual(caught.exception.errors()[0]["loc"], (field,))

    def test_each_negative_count_rejected(self):
        for field in ("valid_count", "warning_count", "invalid_count"):
            with self.subTest(field=field), self.assertRaises(ValidationError) as caught:
                HealthScoreRequest(**payload(**{field: -1}))
            self.assertEqual(caught.exception.errors()[0]["loc"], (field,))

    def test_quality_total_must_be_positive(self):
        with self.assertRaises(ValidationError):
            HealthScoreRequest(**payload(valid_count=0, warning_count=0, invalid_count=0))
        for field in ("valid_count", "warning_count", "invalid_count"):
            counts = dict(valid_count=0, warning_count=0, invalid_count=0)
            counts[field] = 1
            with self.subTest(field=field):
                HealthScoreRequest(**payload(**counts))

    def test_required_fields(self):
        for field in ("failure_probability", "anomaly_score", "valid_count", "warning_count", "invalid_count"):
            data = payload()
            del data[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                HealthScoreRequest(**data)

    def test_read_serialization_exact_structure(self):
        result = HealthScoreRead(**expected_response())
        self.assertEqual(result.model_dump(), expected_response())
