from datetime import datetime

from fastapi.testclient import TestClient

from predictions.support import PredictionCase, START, as_utc
from app.core.database import get_db
from app.main import app


class PredictionRouteTests(PredictionCase):
    def setUp(self):
        super().setUp()
        self.seed_predictions()
        previous = app.dependency_overrides.copy()
        self.addCleanup(self.restore_overrides, previous)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    @staticmethod
    def restore_overrides(previous):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)

    def request(self, equipment_id=1, **params):
        return self.client.get(f"/api/v1/equipments/{equipment_id}/predictions", params=params)

    def test_success_exact_page_and_record_structure(self):
        response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(set(body), {"items", "total", "page", "page_size", "pages"})
        self.assertEqual({key: body[key] for key in ("total", "page", "page_size", "pages")},
                         dict(total=4, page=1, page_size=20, pages=1))
        self.assertEqual([row["id"] for row in body["items"]], self.ids([self.latest, self.tie_last, self.tie_first, self.early]))
        row = body["items"][0]
        self.assertEqual(set(row), {"id", "equipment_id", "sensor_id", "measurement_id", "prediction_type",
            "score", "level", "is_alert", "model_name", "model_version", "horizon_hours", "details", "predicted_at", "created_at"})
        self.assertEqual({key: row[key] for key in ("equipment_id", "prediction_type", "score", "level")},
                         dict(equipment_id=1, prediction_type="health_score", score=85.0, level="good"))
        for key in ("sensor_id", "measurement_id", "is_alert", "model_name", "model_version", "horizon_hours", "details"):
            self.assertIsNone(row[key])
        self.assertEqual(as_utc(datetime.fromisoformat(row["predicted_at"])), as_utc(self.latest.predicted_at))
        self.assertEqual(as_utc(datetime.fromisoformat(row["created_at"])), START)

    def test_pagination_and_empty_page(self):
        response = self.request(page=2, page_size=2)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([row["id"] for row in body["items"]], self.ids([self.tie_first, self.early]))
        self.assertEqual({key: body[key] for key in ("total", "page", "page_size", "pages")}, dict(total=4, page=2, page_size=2, pages=2))
        self.assertEqual(self.request(page=3, page_size=2).json(), dict(items=[], total=4, page=3, page_size=2, pages=2))

    def test_all_filters_including_false_alert_and_inclusive_dates(self):
        for filters, expected in self.filter_cases():
            params = {key: value.isoformat() if isinstance(value, datetime) else value for key, value in filters.items()}
            with self.subTest(filters=params):
                response = self.request(**params)
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual([row["id"] for row in body["items"]], self.ids(expected))
                self.assertEqual(body["total"], len(expected))
                self.assertEqual(body["pages"], 1 if expected else 0)

    def test_filtered_pagination_keeps_filtered_total(self):
        response = self.request(prediction_type="anomaly", page=2, page_size=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)
        self.assertEqual(response.json()["pages"], 2)
        self.assertEqual(response.json()["items"][0]["id"], self.early.id)

    def test_existing_equipment_without_predictions(self):
        response = self.request(equipment_id=3)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), dict(items=[], total=0, page=1, page_size=20, pages=0))

    def test_missing_equipment_returns_404(self):
        response = self.request(equipment_id=999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Equipment not found"})

    def test_invalid_page_and_page_size(self):
        for params in ({"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": -1}, {"page_size": 101}):
            with self.subTest(params=params):
                response = self.request(**params)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"], ["query", next(iter(params))])

    def test_maximum_page_size_is_accepted(self):
        response = self.request(page_size=100)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page_size"], 100)

    def test_invalid_prediction_type(self):
        response = self.request(prediction_type="unknown")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["query", "prediction_type"])

    def test_invalid_optional_filters(self):
        for params in ({"level": ""}, {"level": "x" * 51}, {"is_alert": "invalid"},
                       {"start_time": "not-a-date"}, {"end_time": "not-a-date"}):
            with self.subTest(params=params):
                self.assertEqual(self.request(**params).status_code, 422)
