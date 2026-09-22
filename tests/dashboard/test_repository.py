from datetime import timedelta
from unittest.mock import Mock, patch

from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from dashboard.support import DatabaseCase, END, FixedDatetime, NOW, START
from app.repositories.dashboard_repository import DashboardRepository
from app.services.dashboard_service import DashboardService


class DashboardRepositoryTests(DatabaseCase):
    def test_company_site_equipment_isolation(self):
        for sensor in (1, 4, 5):
            self.measurement(sensor_id=sensor)
        for equipment in (1, 3, 4):
            self.maintenance(equipment_id=equipment, cost=equipment)
        for scope, expected in (({}, (3, 3, 5, 2, 4)),
                                ({"site_id": 1}, (1, 2, 4, 1, 1)),
                                ({"equipment_id": 3}, (1, 1, 1, 1, 3)),
                                ({"site_id": 1, "equipment_id": 1}, (1, 1, 4, 1, 1))):
            with self.subTest(scope=scope):
                actual = (self.repo.count_sites(1, **scope),
                          self.repo.count_equipments(1, **scope),
                          self.repo.count_sensors(1, **scope),
                          self.repo.count_measurements(1, START, END, **scope),
                          self.repo.get_completed_cost_aggregate(1, START, END, **scope)["valid_sum"])
                self.assertEqual(actual, expected)

    def test_inconsistent_scope_returns_empty_without_widening(self):
        self.measurement(sensor_id=5)
        self.maintenance(equipment_id=4, cost=999)
        for scope in ({"site_id": 3}, {"equipment_id": 4},
                      {"site_id": 2, "equipment_id": 1}, {"site_id": 0}):
            with self.subTest(scope=scope):
                self.assertEqual(self.repo.count_sites(1, **scope), 0)
                self.assertEqual(self.repo.count_equipments(1, **scope), 0)
                self.assertEqual(self.repo.count_sensors(1, **scope), 0)
                self.assertEqual(self.repo.count_measurements(1, START, END, **scope), 0)
                self.assertEqual(self.repo.get_last_measurements(1, NOW, **scope), [])
                self.assertEqual(self.repo.get_completed_cost_aggregate(
                    1, START, END, **scope)["eligible_records"], 0)

    def test_empty_site_and_equipment_without_sensor_are_counted(self):
        self.assertEqual(self.repo.count_sites(1, site_id=4), 1)
        self.assertEqual(self.repo.count_equipments(1, equipment_id=2), 1)
        self.assertEqual(self.repo.count_sensors(1, equipment_id=2), 0)

    def test_active_sensor_coverage_counts_equipment_once(self):
        self.assertEqual(self.repo.count_equipments_with_active_sensor(1, site_id=1), 1)
        self.assertEqual(self.repo.count_equipments(1, site_id=1), 2)

    def test_raw_categories_are_preserved(self):
        self.assertEqual(self.counts(self.repo.get_equipment_status_counts(1)),
                         {"operational": 1, "custom": 1, "maintenance": 1})
        self.assertEqual(self.counts(self.repo.get_equipment_criticality_counts(1)),
                         {"high": 1, "custom": 1, "critical": 1})
        self.assertEqual(self.counts(self.repo.get_sensor_status_counts(1)),
                         {"active": 3, "inactive": 1, "custom": 1})
        self.assertEqual(self.repo.count_high_critical_unavailable(1), 1)

    def test_measurement_quality_and_half_open_period(self):
        for timestamp, quality in ((START-timedelta(microseconds=1), "good"),
                                   (START, "good"), (START, "good"),
                                   (END-timedelta(microseconds=1), "bad"),
                                   (START, "custom"), (END, "good")):
            self.measurement(timestamp=timestamp, quality=quality)
        self.measurement(sensor_id=5)
        self.assertEqual(self.repo.count_measurements(1, START, END), 4)
        self.assertEqual(self.counts(self.repo.get_measurement_quality_counts(1, START, END)),
                         {"good": 2, "bad": 1, "custom": 1})

    def test_reporting_counts_currently_active_sensors_once(self):
        self.measurement()
        self.measurement(quality="bad")
        self.measurement(sensor_id=3)
        self.measurement(sensor_id=5)
        self.measurement(sensor_id=2, timestamp=END)
        self.assertEqual(self.repo.count_active_sensors_with_measurement(1, START, END), 1)

    def test_latest_orders_timestamp_before_id_and_breaks_ties(self):
        self.measurement(id=10, timestamp=START, value=10)
        self.measurement(id=11, timestamp=START, value=11)
        self.measurement(id=100, timestamp=START-timedelta(days=1), value=100)
        self.measurement(id=101, timestamp=NOW+timedelta(seconds=1), value=101)
        rows = self.repo.get_last_measurements(1, NOW, equipment_id=1)
        self.assertEqual(rows[0]["measurement_id"], 11)
        self.assertEqual(rows[0]["value"], 11)
        self.measurement(id=102, timestamp=NOW, value=102)
        self.assertEqual(self.repo.get_last_measurements(1, NOW)[0]["measurement_id"], 102)

    def test_sensor_without_measurement_is_kept(self):
        rows = self.repo.get_last_measurements(1, NOW, equipment_id=1)
        self.assertEqual({r["sensor_id"] for r in rows}, {1, 2, 3, 6})
        for row in rows:
            self.assertIsNone(row["measurement_id"])
            self.assertIsNone(row["timestamp"])
            self.assertIsNone(row["value"])
            self.assertIsNone(row["quality"])

    def test_open_maintenance_status_and_priority(self):
        for status, priority in (("planned", "high"), ("in_progress", "custom"),
                                 ("completed", "critical"), ("cancelled", "critical")):
            self.maintenance(status=status, priority=priority)
        self.maintenance(equipment_id=4, status="planned")
        self.assertEqual(self.counts(self.repo.get_open_maintenance_status_counts(1)),
                         {"planned": 1, "in_progress": 1})
        self.assertEqual(self.counts(self.repo.get_open_maintenance_priority_counts(1)),
                         {"high": 1, "custom": 1})

    def test_overdue_requires_planned_past_date_and_no_start(self):
        for values in (dict(planned_at=NOW-timedelta(seconds=1)),
                       dict(planned_at=NOW), dict(planned_at=NOW+timedelta(seconds=1)),
                       dict(planned_at=None), dict(planned_at=START, started_at=START),
                       dict(planned_at=START, status="in_progress"),
                       dict(planned_at=START, status="cancelled")):
            self.maintenance(**(dict(status="planned") | values))
        self.maintenance(equipment_id=4, status="planned", planned_at=START)
        self.assertEqual(self.repo.count_overdue_maintenance(1, NOW), 1)
        self.assertEqual(self.repo.count_planned_maintenance_without_planned_at(1), 1)

    def test_completed_types_use_half_open_period_and_status(self):
        self.maintenance(maintenance_type="corrective", completed_at=START)
        self.maintenance(maintenance_type="custom", completed_at=END-timedelta(microseconds=1))
        self.maintenance(completed_at=START-timedelta(microseconds=1))
        self.maintenance(completed_at=END)
        self.maintenance(status="cancelled")
        self.maintenance(equipment_id=4)
        self.assertEqual(self.counts(self.repo.get_completed_maintenance_type_counts(1, START, END)),
                         {"corrective": 1, "custom": 1})

    def test_completed_without_date_is_separate_from_period(self):
        self.maintenance(completed_at=None)
        self.maintenance(status="planned", completed_at=None)
        self.maintenance(equipment_id=4, completed_at=None)
        self.assertEqual(self.repo.count_completed_maintenance_without_completed_at(1), 1)
        self.assertEqual(self.repo.get_completed_maintenance_type_counts(1, START, END), [])

    def test_downtime_30_zero_and_missing(self):
        for value in (30, 0, None):
            self.maintenance(downtime_minutes=value)
        self.assertEqual(dict(self.repo.get_completed_downtime_aggregate(1, START, END)),
                         {"eligible_records": 3, "valid_values": 2, "valid_sum": 30})

    def test_cost_partial_coverage_and_invalid_values(self):
        for value in (100.5, 0, None, -10, float("inf")):
            self.maintenance(cost=value)
        self.assertEqual(dict(self.repo.get_completed_cost_aggregate(1, START, END)),
                         {"eligible_records": 5, "valid_values": 2, "valid_sum": 100.5})

    def test_negative_downtime_is_not_valid(self):
        self.maintenance(downtime_minutes=-1)
        self.assertEqual(dict(self.repo.get_completed_downtime_aggregate(1, START, END)),
                         {"eligible_records": 1, "valid_values": 0, "valid_sum": None})

    def test_no_intervention_differs_from_missing_values(self):
        for name in ("get_completed_cost_aggregate", "get_completed_downtime_aggregate"):
            with self.subTest(name=name):
                self.assertEqual(dict(getattr(self.repo, name)(1, START, END)),
                                 {"eligible_records": 0, "valid_values": 0, "valid_sum": None})
        self.maintenance()
        for name in ("get_completed_cost_aggregate", "get_completed_downtime_aggregate"):
            with self.subTest(name=name):
                self.assertEqual(dict(getattr(self.repo, name)(1, START, END)),
                                 {"eligible_records": 1, "valid_values": 0, "valid_sum": None})

    def test_measurements_do_not_multiply_maintenance_aggregates(self):
        for sensor_id in (1, 1, 1, 2, 2):
            self.measurement(sensor_id=sensor_id)
        for value in (30, 0, None):
            self.maintenance(downtime_minutes=value, cost=value)
        self.maintenance(completed_at=END, cost=999, downtime_minutes=999)
        self.maintenance(equipment_id=4, cost=999, downtime_minutes=999)
        self.assertEqual(self.repo.count_measurements(1, START, END), 5)
        self.assertEqual(self.counts(self.repo.get_completed_maintenance_type_counts(1, START, END)),
                         {"preventive": 3})
        for method in (self.repo.get_completed_cost_aggregate, self.repo.get_completed_downtime_aggregate):
            self.assertEqual(dict(method(1, START, END)),
                             {"eligible_records": 3, "valid_values": 2, "valid_sum": 30})

    def test_daily_query_compiles_with_utc_and_scope(self):
        db = Mock()
        db.execute.return_value.mappings.return_value.all.return_value = []
        DashboardRepository(db).get_daily_measurement_counts(1, START, END, 2, 3)
        statement = db.execute.call_args.args[0]
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        self.assertIn("CAST(timezone(", sql)
        self.assertIn("AS DATE)", sql)
        self.assertIn("GROUP BY", sql)
        self.assertIn("measurements.timestamp >=", sql)
        self.assertIn("measurements.timestamp < ", sql)
        self.assertIn("UTC", compiled.params.values())
        self.assertEqual(compiled.params["company_id_1"], 1)
        self.assertEqual(compiled.params["id_1"], 2)
        self.assertEqual(compiled.params["id_2"], 3)

    def test_postgresql_daily_buckets_ignore_session_timezone(self):
        if self.engine.dialect.name != "postgresql":
            self.skipTest("Requires DASHBOARD_TEST_DATABASE_URL (PostgreSQL)")
        self.db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
        self.measurement(timestamp=START)
        self.measurement(timestamp=START+timedelta(days=2))
        self.measurement(timestamp=END)
        self.measurement(sensor_id=5)
        rows = self.repo.get_daily_measurement_counts(1, START, END)
        self.assertEqual([(r["date"], r["count"]) for r in rows],
                         [(START.date(), 1), ((START+timedelta(days=2)).date(), 1)])
        # Also exercise the complete SQL -> service -> schema path on native
        # PostgreSQL timestamps, without emulating timezone behavior in SQLite.
        with patch("app.services.dashboard_service.datetime", FixedDatetime):
            result = DashboardService(self.db).get_dashboard(1, START, END)
        self.assertEqual([day.count for day in result.measurements.daily_volume], [1, 0, 1])
        self.assertEqual(result.measurements.last_measurements[0].age_seconds, 86400)
        self.assertEqual(result.assets.equipments, 3)
