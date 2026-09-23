from datetime import timedelta, timezone

from dashboard.support import DatabaseCase, START
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import get_db
from app.main import app
from app.models import Company, Equipment, MaintenanceRecord, Measurement, Sensor, Site


END = START + timedelta(days=2)
ROUTES = ("companies", "sites", "equipments", "sensors", "measurements", "maintenance")
SEARCH_ROUTES = ("companies", "sites", "equipments", "sensors", "maintenance")
ORDER = {route: ([4, 3, 2, 1] if route in ("measurements", "maintenance") else [1, 2, 3, 4])
         for route in ROUTES}


class PaginationFilterTests(DatabaseCase):
    """Real route, service and repository; only the database dependency is replaced."""

    def seed_assets(self):
        # Strong references preserve aware fixture datetimes in SQLite's identity
        # map. PostgreSQL execution additionally tests native timestamptz hydration.
        self.records = []
        names = ("Alpha", "Beta", "Alpha West", "Delta")
        for model in (Company, Site, Equipment, Sensor):
            for i, name in enumerate(names, 1):
                data = dict(id=i, name=name, code=f"CODE-{i}", created_at=START, updated_at=START)
                if model is Site:
                    data["company_id"] = 1 if i in (1, 3) else 2
                elif model is Equipment:
                    data.update(site_id=1 if i in (1, 3) else 2,
                                equipment_type="pump" if i == 1 else "motor",
                                status=("operational", "maintenance", "operational", "out_of_service")[i-1],
                                criticality=("high", "low", "high", "critical")[i-1])
                elif model is Sensor:
                    data.update(equipment_id=1 if i in (1, 3) else 2,
                                sensor_type="temperature" if i == 1 else "vibration",
                                unit="C" if i == 1 else "mm/s",
                                status="active" if i in (1, 3) else "inactive")
                self.records.append(model(**data))
            self.db.add_all(self.records)
            self.db.flush()
        for i in range(1, 5):
            timestamp = (START, START, START+timedelta(days=1), END)[i-1]
            self.records.append(Measurement(
                id=i, sensor_id=1 if i in (1, 3) else 2,
                timestamp=timestamp, value=float(i), quality="good" if i in (1, 3) else "bad"))
            self.records.append(MaintenanceRecord(
                id=i, equipment_id=1 if i in (1, 3) else 2,
                title=names[i-1],
                maintenance_type=("preventive", "corrective", "preventive", "predictive")[i-1],
                status=("planned", "completed", "planned", "in_progress")[i-1],
                priority=("low", "high", "low", "critical")[i-1],
                # Different from created_at to detect accidental date-field changes.
                planned_at=END+timedelta(days=10),
                completed_at=END+timedelta(days=11) if i == 2 else None,
                description="desc-only" if i == 1 else None,
                failure_code="failure-only" if i == 2 else None,
                root_cause="cause-only" if i == 3 else None,
                action_taken="action-only" if i == 4 else None,
                technician="tech-only" if i == 1 else None,
                created_at=timestamp, updated_at=timestamp))
        self.db.add_all(self.records)
        self.db.flush()

    def setUp(self):
        super().setUp()
        old_overrides = app.dependency_overrides.copy()
        self.addCleanup(self.restore_overrides, old_overrides)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    @staticmethod
    def restore_overrides(previous):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)

    def request(self, route, **params):
        return self.client.get(f"/api/v1/{route}", params=params)

    def assert_page(self, route, ids, total=None, page=1, page_size=20, **filters):
        response = self.request(route, page=page, page_size=page_size, **filters)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        total = len(ids) if total is None else total
        self.assertEqual(set(body), {"items", "total", "page", "page_size", "pages"})
        self.assertEqual([item["id"] for item in body["items"]], ids)
        self.assertEqual((body["total"], body["page"], body["page_size"], body["pages"]),
                         (total, page, page_size, (total+page_size-1)//page_size))
        return body

    def test_conflicting_filters_are_intersected(self):
        for route, filters in (
            ("sites", {"company_id": 2, "search": "Alpha"}),
            ("equipments", {"site_id": 1, "status": "maintenance"}),
            ("equipments", {"status": "operational", "criticality": "low"}),
            ("sensors", {"equipment_id": 1, "status": "inactive"}),
            ("measurements", {"sensor_id": 1, "quality": "bad"}),
            ("maintenance", {"equipment_id": 1, "maintenance_type": "corrective"}),
            ("maintenance", {"status": "planned", "priority": "high"}),
        ):
            with self.subTest(route=route, filters=filters):
                self.assert_page(route, [], **filters)

    def test_timestamp_order_takes_precedence_over_id(self):
        old = START-timedelta(days=1)
        measurement = Measurement(id=99, sensor_id=1, timestamp=old, value=99, quality="good")
        maintenance = MaintenanceRecord(id=99, equipment_id=1, title="Old",
                                        maintenance_type="preventive", created_at=old, updated_at=old)
        self.records.extend([measurement, maintenance])
        self.db.add_all([measurement, maintenance])
        self.db.flush()
        for route in ("measurements", "maintenance"):
            with self.subTest(route=route):
                self.assert_page(route, [4, 3, 2, 1, 99])
                self.assert_page(route, [99], total=5, page=3, page_size=2)

    def test_postgresql_timezone_offsets_and_fresh_hydration(self):
        if self.engine.dialect.name != "postgresql":
            self.skipTest("Requires DASHBOARD_TEST_DATABASE_URL (PostgreSQL)")
        # Discard identity-map objects to test actual timezone-aware DB results.
        self.db.expunge_all()
        offset = timezone(timedelta(hours=5, minutes=30))
        for route in ("measurements", "maintenance"):
            with self.subTest(route=route):
                self.assert_page(route, [3, 2, 1],
                                 start_time=START.astimezone(offset).isoformat(),
                                 end_time=END.astimezone(offset).isoformat())


def add_case(name, check):
    """One unittest result per route/filter, with descriptive discovery names."""
    check.__name__ = "test_" + name
    setattr(PaginationFilterTests, check.__name__, check)


for route in ROUTES:
    def empty_database(self, route=route):
        # The fixture owns an isolated test database/schema, never the app DB.
        for model in (Measurement, MaintenanceRecord, Sensor, Equipment, Site, Company):
            self.db.execute(delete(model))
        self.assert_page(route, [])
    add_case(f"{route}_empty_database", empty_database)

    def defaults(self, route=route):
        response = self.request(route)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), self.assert_page(route, ORDER[route]))
    add_case(f"{route}_defaults_and_structure", defaults)

    def pages(self, route=route):
        first = self.assert_page(route, ORDER[route][:3], total=4, page_size=3)
        second = self.assert_page(route, ORDER[route][3:], total=4, page=2, page_size=3)
        self.assertEqual(len(first["items"])+len(second["items"]), 4)
        self.assert_page(route, [], total=4, page=3, page_size=3)
    add_case(f"{route}_pages_and_beyond_last_page", pages)

    def bounds(self, route=route):
        for params in ({"page": 0}, {"page": -1}, {"page_size": 0},
                       {"page_size": -1}, {"page_size": 101}, {"page": "abc"}):
            with self.subTest(params=params):
                self.assertEqual(self.request(route, **params).status_code, 422)
        self.assert_page(route, ORDER[route][:1], total=4, page_size=1)
        self.assert_page(route, ORDER[route], page_size=100)
    add_case(f"{route}_pagination_bounds", bounds)

    def stable(self, route=route):
        for _ in range(2):
            observed = []
            for page in range(1, 5):
                body = self.assert_page(route, [ORDER[route][page-1]], total=4, page=page, page_size=1)
                observed.extend(item["id"] for item in body["items"])
            self.assertEqual(observed, ORDER[route])
    add_case(f"{route}_deterministic_order_across_pages_and_ties", stable)


FILTER_CASES = (
    ("companies", "search", {"search": " alpha "}, [1, 3]),
    ("companies", "code_search", {"search": "code-2"}, [2]),
    ("sites", "company_id", {"company_id": 1}, [1, 3]),
    ("sites", "search", {"search": "aLpHa"}, [1, 3]),
    ("sites", "code_search", {"search": "code-2"}, [2]),
    ("equipments", "site_id", {"site_id": 1}, [1, 3]),
    ("equipments", "status", {"status": "operational"}, [1, 3]),
    ("equipments", "criticality", {"criticality": "high"}, [1, 3]),
    ("equipments", "search", {"search": "ALPHA"}, [1, 3]),
    ("equipments", "code_search", {"search": "code-2"}, [2]),
    ("equipments", "type_search", {"search": "pump"}, [1]),
    ("sensors", "equipment_id", {"equipment_id": 1}, [1, 3]),
    ("sensors", "status", {"status": "active"}, [1, 3]),
    ("sensors", "search", {"search": "ALPHA"}, [1, 3]),
    ("sensors", "code_search", {"search": "code-2"}, [2]),
    ("sensors", "type_search", {"search": "temperature"}, [1]),
    ("sensors", "unit_search", {"search": "mm/s"}, [2, 3, 4]),
    ("measurements", "sensor_id", {"sensor_id": 1}, [3, 1]),
    ("measurements", "quality", {"quality": "good"}, [3, 1]),
    ("maintenance", "equipment_id", {"equipment_id": 1}, [3, 1]),
    ("maintenance", "maintenance_type", {"maintenance_type": "preventive"}, [3, 1]),
    ("maintenance", "status", {"status": "planned"}, [3, 1]),
    ("maintenance", "priority", {"priority": "low"}, [3, 1]),
    ("maintenance", "search", {"search": "ALPHA"}, [3, 1]),
    ("maintenance", "description_search", {"search": "desc-only"}, [1]),
    ("maintenance", "failure_search", {"search": "failure-only"}, [2]),
    ("maintenance", "cause_search", {"search": "cause-only"}, [3]),
    ("maintenance", "action_search", {"search": "action-only"}, [4]),
    ("maintenance", "technician_search", {"search": "tech-only"}, [1]),
    ("sites", "combined", {"company_id": 1, "search": "West"}, [3]),
    ("equipments", "combined", {"site_id": 1, "status": "operational", "criticality": "high", "search": "West"}, [3]),
    ("sensors", "combined", {"equipment_id": 1, "status": "active", "search": "West"}, [3]),
    ("measurements", "combined", {"sensor_id": 1, "quality": "good", "start_time": (START+timedelta(days=1)).isoformat(), "end_time": END.isoformat()}, [3]),
    ("maintenance", "combined", {"equipment_id": 1, "maintenance_type": "preventive", "status": "planned", "priority": "low", "search": "West", "start_time": START.isoformat(), "end_time": END.isoformat()}, [3]),
)

for route, label, filters, expected in FILTER_CASES:
    def filtered(self, route=route, filters=filters, expected=expected):
        self.assert_page(route, expected, **filters)
        # Count must use the same filters before applying offset/limit.
        self.assert_page(route, expected[:1], total=len(expected), page_size=1, **filters)
        self.assert_page(route, expected[1:2], total=len(expected), page=2, page_size=1, **filters)
    add_case(f"{route}_filter_{label}_and_filtered_total", filtered)


for route in SEARCH_ROUTES:
    def whitespace(self, route=route):
        for search in ("   ", " \t \n "):
            with self.subTest(search=repr(search)):
                self.assertEqual(self.request(route, search=search).json(), self.request(route).json())
                self.assert_page(route, ORDER[route], search=search)
    add_case(f"{route}_whitespace_search_is_no_filter", whitespace)

    def no_match(self, route=route):
        self.assert_page(route, [], search="no-match-token")
        self.assert_page(route, [], page=2, search="no-match-token")
    add_case(f"{route}_empty_filtered_page", no_match)


for route, field in (("equipments", "status"), ("equipments", "criticality"),
                     ("sensors", "status"), ("measurements", "quality"),
                     ("maintenance", "maintenance_type"), ("maintenance", "status"),
                     ("maintenance", "priority")):
    def invalid_enum(self, route=route, field=field):
        response = self.request(route, **{field: "invalid"})
        self.assertEqual(response.status_code, 422)
        self.assertIn(["query", field], [error["loc"] for error in response.json()["detail"]])
    add_case(f"{route}_invalid_{field}_returns_422", invalid_enum)


for route in ("measurements", "maintenance"):
    def period(self, route=route):
        self.assert_page(route, [3, 2, 1], start_time=START.isoformat(), end_time=END.isoformat())
        self.assert_page(route, [4, 3], start_time=(START+timedelta(days=1)).isoformat())
        self.assert_page(route, [2, 1], end_time=(START+timedelta(days=1)).isoformat())
        self.assert_page(route, [], start_time=(END+timedelta(days=1)).isoformat())
    add_case(f"{route}_half_open_and_one_sided_period", period)

    def invalid_period(self, route=route):
        for end in (START, START-timedelta(seconds=1)):
            with self.subTest(end=end):
                response = self.request(route, start_time=START.isoformat(), end_time=end.isoformat())
                self.assertEqual(response.status_code, 400, response.text)
    add_case(f"{route}_equal_or_reversed_period_returns_400", invalid_period)

    def naive(self, route=route):
        for field in ("start_time", "end_time"):
            with self.subTest(field=field):
                response = self.request(route, **{field: START.replace(tzinfo=None).isoformat()})
                self.assertEqual(response.status_code, 400, response.text)
                self.assertIn("timezone", response.json()["detail"])
    add_case(f"{route}_naive_dates_return_400", naive)

    def no_parent(self, route=route):
        field = "sensor_id" if route == "measurements" else "equipment_id"
        self.assert_page(route, [], **{field: 999})
    add_case(f"{route}_unknown_parent_returns_empty_page", no_parent)
