from unittest.mock import patch

from dashboard.support import END, START, ServiceCase
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app


class DashboardRouteTests(ServiceCase):
    def setUp(self):
        super().setUp()
        previous = app.dependency_overrides.copy()
        self.addCleanup(self.restore_overrides, previous)
        app.dependency_overrides[get_db] = lambda: self.db
        # Keep real validation/builders; only aggregates are stubbed as in service tests.
        factory = patch("app.api.routes.dashboard.DashboardService", return_value=self.service)
        factory.start()
        self.addCleanup(factory.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    @staticmethod
    def restore_overrides(previous):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)

    def request(self, **kwargs):
        params = dict(company_id=1, start_time=START.isoformat(), end_time=END.isoformat())
        params.update(kwargs)
        return self.client.get("/api/v1/dashboard", params=params)

    def test_success_serializes_dashboard_and_nullable_ratios(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["scope"]["company_id"], 1)
        self.assertEqual(body["assets"]["equipments"], 0)
        self.assertIsNone(body["sensor_coverage"]["coverage"]["percentage"])
        self.assertEqual(len(body["measurements"]["daily_volume"]), 3)

    def test_foreign_site_returns_400(self):
        response = self.request(site_id=3)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Site does not belong to company")

    def test_wrong_equipment_site_returns_400(self):
        response = self.request(site_id=1, equipment_id=3)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Equipment does not belong to site")

    def test_missing_company_returns_404(self):
        response = self.request(company_id=999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Company not found")

    def test_invalid_period_returns_400(self):
        response = self.request(end_time=START.isoformat())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "start_time must be before end_time")

    def test_naive_period_returns_400(self):
        response = self.request(start_time=START.replace(tzinfo=None).isoformat())
        self.assertEqual(response.status_code, 400)
        self.assertIn("timezone", response.json()["detail"])

    def test_invalid_query_returns_422(self):
        for params in ({"company_id": 0}, {"site_id": -1}, {"equipment_id": 0},
                       {"start_time": "not-a-date"}):
            with self.subTest(params=params):
                self.assertEqual(self.request(**params).status_code, 422)
