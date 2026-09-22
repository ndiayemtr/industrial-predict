from datetime import timedelta, timezone

from dashboard.support import END, NOW, START, ServiceCase


class DashboardServiceTests(ServiceCase):
    def assert_rejected(self, message, **kwargs):
        with self.assertRaisesRegex(ValueError, message):
            self.dashboard(**kwargs)
        self.assertEqual(self.aggregates.mock_calls, [])

    def test_site_from_other_company_is_rejected(self):
        self.assert_rejected("Site does not belong to company", site_id=3)

    def test_equipment_from_other_site_is_rejected(self):
        self.assert_rejected("Equipment does not belong to site", site_id=1, equipment_id=3)

    def test_equipment_from_other_company_without_site_is_rejected(self):
        self.assert_rejected("Equipment does not belong to company", equipment_id=4)

    def test_unknown_scope_is_rejected(self):
        for field, message in (("company_id", "Company not found"),
                               ("site_id", "Site not found"),
                               ("equipment_id", "Equipment not found")):
            with self.subTest(field=field):
                self.assert_rejected(message, **{field: 999})

    def test_reversed_period_is_rejected(self):
        self.assert_rejected("start_time must be before end_time", start_time=END, end_time=START)

    def test_empty_period_is_rejected(self):
        self.assert_rejected("start_time must be before end_time", end_time=START)

    def test_future_period_is_rejected(self):
        self.assert_rejected("end_time cannot be in the future", end_time=NOW+timedelta(seconds=1))

    def test_start_without_timezone_is_rejected(self):
        self.assert_rejected("start_time must include timezone", start_time=START.replace(tzinfo=None))

    def test_end_without_timezone_is_rejected(self):
        self.assert_rejected("end_time must include timezone", end_time=END.replace(tzinfo=None))

    def test_timezone_normalized_and_cutoff_shared(self):
        offset = timezone(timedelta(hours=5, minutes=30))
        result = self.dashboard(start_time=START.astimezone(offset),
                                end_time=END.astimezone(offset), site_id=1, equipment_id=1)
        self.assertEqual(result.period.start_time, START)
        self.assertEqual(result.period.start_time.utcoffset(), timedelta(0))
        self.assertEqual(result.period.calculated_at, NOW)
        self.aggregates.count_measurements.assert_called_once_with(1, START, END, 1, 1)
        self.aggregates.get_last_measurements.assert_called_once_with(1, NOW, 1, 1)
        self.aggregates.count_overdue_maintenance.assert_called_once_with(1, NOW, 1, 1)
        self.aggregates.count_sites.assert_called_once_with(1, 1, 1)

    def test_end_equal_to_calculated_at_is_allowed(self):
        self.assertEqual(self.dashboard(end_time=NOW).period.end_time, NOW)

    def test_sensor_coverage_uses_all_equipment(self):
        self.aggregates.count_equipments.return_value = 2
        self.aggregates.count_equipments_with_active_sensor.return_value = 1
        result = self.dashboard().sensor_coverage
        self.assertEqual(result.equipments_total, 2)
        self.assertEqual(result.coverage.model_dump(),
                         {"numerator": 1, "denominator": 2, "percentage": 50.0})

    def test_quality_includes_unknown_categories_in_denominator(self):
        self.aggregates.count_measurements.return_value = 4
        self.aggregates.get_measurement_quality_counts.return_value = [
            {"value": "good", "count": 2}, {"value": "bad", "count": 1},
            {"value": "custom", "count": 1},
        ]
        result = self.dashboard().measurements.quality
        self.assertEqual((result.total, result.good, result.bad, result.other), (4, 2, 1, 1))
        self.assertEqual(result.good_ratio.percentage, 50)
        self.assertIn("custom", [item.value for item in result.distribution])

    def test_unknown_equipment_and_sensor_categories_are_other(self):
        self.aggregates.get_equipment_status_counts.return_value = [{"value": "custom", "count": 2}]
        self.aggregates.get_equipment_criticality_counts.return_value = [{"value": "custom", "count": 2}]
        self.aggregates.get_sensor_status_counts.return_value = [{"value": "custom", "count": 3}]
        result = self.dashboard()
        self.assertEqual((result.equipment_status.other, result.equipment_criticality.other,
                          result.sensor_status.other), (2, 2, 3))
        self.assertEqual(result.equipment_status.operational, 0)
        self.assertEqual(result.equipment_criticality.high_or_critical, 0)

    def test_days_without_measurement_are_zero_and_end_day_excluded(self):
        self.aggregates.get_daily_measurement_counts.return_value = [
            {"date": START.date(), "count": 2},
            {"date": (START+timedelta(days=2)).date(), "count": 1},
        ]
        rows = self.dashboard().measurements.daily_volume
        self.assertEqual([(row.date, row.count) for row in rows],
                         [("2026-01-01", 2), ("2026-01-02", 0), ("2026-01-03", 1)])

    def test_partial_last_day_is_included(self):
        rows = self.dashboard(end_time=END+timedelta(hours=1)).measurements.daily_volume
        self.assertEqual([(row.date, row.count) for row in rows],
                         [("2026-01-01", 0), ("2026-01-02", 0),
                          ("2026-01-03", 0), ("2026-01-04", 0)])

    def test_last_measurement_age_and_sensor_without_reading(self):
        base = dict(sensor_name="temperature", sensor_code="t", equipment_id=1, unit="C")
        self.aggregates.get_last_measurements.return_value = [
            dict(base, sensor_id=1, timestamp=NOW-timedelta(seconds=60), value=7, quality="bad"),
            dict(base, sensor_id=2, timestamp=None, value=None, quality=None),
        ]
        rows = self.dashboard().measurements.last_measurements
        self.assertEqual((rows[0].age_seconds, rows[0].value, rows[0].quality), (60, 7, "bad"))
        self.assertIsNone(rows[1].timestamp)
        self.assertIsNone(rows[1].value)
        self.assertIsNone(rows[1].age_seconds)

    def test_open_and_overdue_summaries(self):
        self.aggregates.get_open_maintenance_status_counts.return_value = [
            {"value": "planned", "count": 3}, {"value": "in_progress", "count": 1}]
        self.aggregates.get_open_maintenance_priority_counts.return_value = [
            {"value": "high", "count": 3}, {"value": "custom", "count": 1}]
        self.aggregates.count_overdue_maintenance.return_value = 2
        self.aggregates.count_planned_maintenance_without_planned_at.return_value = 1
        result = self.dashboard().maintenance
        self.assertEqual((result.open.total, result.open.planned, result.open.in_progress), (4, 3, 1))
        self.assertEqual((result.open.priorities.high, result.open.priorities.other), (3, 1))
        self.assertEqual((result.overdue.overdue, result.overdue.planned_without_planned_at), (2, 1))

    def test_corrective_share_includes_unknown_type_but_not_missing_date(self):
        self.aggregates.get_completed_maintenance_type_counts.return_value = [
            {"value": "corrective", "count": 1}, {"value": "preventive", "count": 1},
            {"value": "custom", "count": 1}]
        self.aggregates.count_completed_maintenance_without_completed_at.return_value = 2
        result = self.dashboard().maintenance
        self.assertEqual(result.completed.total, 3)
        self.assertEqual(result.completed.completed_without_completed_at, 2)
        self.assertEqual(result.completed.types.other, 1)
        self.assertEqual(result.corrective.ratio.model_dump(),
                         {"numerator": 1, "denominator": 3, "percentage": 33.33})

    def test_downtime_partial_coverage_and_hours(self):
        self.aggregates.get_completed_downtime_aggregate.return_value = {
            "eligible_records": 3, "valid_values": 2, "valid_sum": 30}
        result = self.dashboard().maintenance.downtime
        self.assertEqual((result.total_minutes, result.total_hours), (30, 0.5))
        self.assertEqual(result.coverage.ratio.model_dump(),
                         {"numerator": 2, "denominator": 3, "percentage": 66.67})

    def test_cost_partial_coverage_without_invented_currency(self):
        self.aggregates.get_completed_cost_aggregate.return_value = {
            "eligible_records": 3, "valid_values": 2, "valid_sum": 100.5}
        result = self.dashboard().maintenance.cost
        self.assertEqual(result.total_cost, 100.5)
        self.assertEqual(result.coverage.ratio.percentage, 66.67)
        self.assertIsNone(result.currency)

    def test_no_intervention_returns_zero_with_undefined_coverage(self):
        result = self.dashboard().maintenance
        self.assertEqual(result.downtime.total_minutes, 0)
        self.assertEqual(result.downtime.total_hours, 0)
        self.assertEqual(result.cost.total_cost, 0)
        self.assertIsNone(result.downtime.coverage.ratio.percentage)
        self.assertIsNone(result.cost.coverage.ratio.percentage)

    def test_interventions_with_missing_values_return_null(self):
        for name in ("get_completed_downtime_aggregate", "get_completed_cost_aggregate"):
            getattr(self.aggregates, name).return_value = {
                "eligible_records": 2, "valid_values": 0, "valid_sum": None}
        result = self.dashboard().maintenance
        self.assertIsNone(result.downtime.total_minutes)
        self.assertIsNone(result.downtime.total_hours)
        self.assertIsNone(result.cost.total_cost)
        self.assertEqual(result.cost.coverage.ratio.percentage, 0)
        self.assertEqual(result.downtime.coverage.ratio.percentage, 0)

    def test_empty_scope_ratios_are_null(self):
        result = self.dashboard(company_id=3)
        self.assertEqual(result.assets.model_dump(), {"sites": 0, "equipments": 0, "sensors": 0})
        for ratio in (result.equipment_status.operational_ratio, result.sensor_coverage.coverage,
                      result.sensor_status.active_ratio, result.measurements.quality.good_ratio,
                      result.measurements.activity.active_sensors_reporting_ratio,
                      result.maintenance.corrective.ratio):
            self.assertIsNone(ratio.percentage)
