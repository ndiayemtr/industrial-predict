from dashboard.support import DatabaseCase
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from health_score.support import expected_response, payload


class HealthScoreRouteTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        previous = app.dependency_overrides.copy()
        self.addCleanup(self.restore_overrides, previous)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    @staticmethod
    def restore_overrides(previous):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)

    def request(self, equipment_id=1, **overrides):
        return self.client.post(f"/api/v1/equipments/{equipment_id}/health-score", json=payload(**overrides))

    def test_valid_payload_returns_200_with_exact_response(self):
        response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), expected_response())

    def test_missing_equipment_returns_404(self):
        response = self.request(equipment_id=999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Equipment not found"})

    def test_invalid_failure_probability_returns_422(self):
        for value in (-0.01, 1.01):
            with self.subTest(value=value):
                response = self.request(failure_probability=value)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"], ["body", "failure_probability"])

    def test_invalid_anomaly_score_returns_422(self):
        for value in (-0.01, 1.01):
            with self.subTest(value=value):
                response = self.request(anomaly_score=value)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"], ["body", "anomaly_score"])

    def test_each_negative_count_returns_422(self):
        for field in ("valid_count", "warning_count", "invalid_count"):
            with self.subTest(field=field):
                response = self.request(**{field: -1})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"], ["body", field])

    def test_zero_quality_total_returns_422(self):
        response = self.request(valid_count=0, warning_count=0, invalid_count=0)
        self.assertEqual(response.status_code, 422)
        self.assertIn("At least one quality observation", response.json()["detail"][0]["msg"])

    def test_optional_maintenance_flags_default_to_false(self):
        data = payload()
        for field in ("corrective_in_progress", "overdue_maintenance", "planned_soon"):
            del data[field]
        response = self.client.post("/api/v1/equipments/1/health-score", json=data)
        self.assertEqual(response.status_code, 200, response.text)
        expected = expected_response()
        expected["components"]["maintenance_health"] = 100
        expected["health_score"] = 84.5
        self.assertEqual(response.json(), expected)
