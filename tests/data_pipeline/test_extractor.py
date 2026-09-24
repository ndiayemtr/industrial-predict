from datetime import timedelta, timezone

from sqlalchemy.exc import OperationalError

from dashboard.support import DatabaseCase
from data_pipeline.support import START
from app.data_pipeline.extractor import MeasurementDataExtractor


END = START+timedelta(seconds=30)


class ExtractorTests(DatabaseCase):
    def setUp(self):
        try:
            super().setUp()
        except OperationalError:
            # Connection unavailability is a skip, not a disguised SQL test failure.
            if getattr(self, "engine", None) is not None and self.engine.dialect.name == "postgresql":
                self.skipTest("PostgreSQL test connection unavailable")
            raise
        self.extractor = MeasurementDataExtractor(self.db)
        for ident, sensor, seconds in ((8, 1, 20), (3, 1, 0), (4, 2, 10),
                                       (5, 4, 10), (6, 5, 30), (7, 1, 30)):
            self.measurement(id=ident, sensor_id=sensor, timestamp=START+timedelta(seconds=seconds))

    def ids(self, **filters):
        return [item.measurement_id for item in self.extractor.extract(**filters)]

    def test_chronological_order_then_id_with_ties(self):
        self.assertEqual(self.ids(), [3, 4, 5, 8, 6, 7])

    def test_company_filter(self):
        self.assertEqual(self.ids(company_id=1), [3, 4, 5, 8, 7])
        self.assertEqual(self.ids(company_id=2), [6])

    def test_site_filter(self):
        self.assertEqual(self.ids(site_id=1), [3, 4, 8, 7])
        self.assertEqual(self.ids(site_id=2), [5])

    def test_equipment_filter(self):
        self.assertEqual(self.ids(equipment_id=1), [3, 4, 8, 7])
        self.assertEqual(self.ids(equipment_id=3), [5])
        self.assertEqual(self.ids(equipment_id=2), [])

    def test_sensor_filter(self):
        self.assertEqual(self.ids(sensor_id=1), [3, 8, 7])
        self.assertEqual(self.ids(sensor_id=2), [4])

    def test_start_time_inclusive(self):
        self.assertEqual(self.ids(start_time=START+timedelta(seconds=10)), [4, 5, 8, 6, 7])

    def test_end_time_exclusive(self):
        self.assertEqual(self.ids(end_time=END), [3, 4, 5, 8])

    def test_half_open_period(self):
        self.assertEqual(self.ids(start_time=START, end_time=END), [3, 4, 5, 8])
        self.assertEqual(self.ids(start_time=END, end_time=END+timedelta(seconds=1)), [6, 7])

    def test_all_filters_combined(self):
        self.assertEqual(self.ids(company_id=1, site_id=1, equipment_id=1, sensor_id=1,
                                  start_time=START+timedelta(seconds=1), end_time=END), [8])

    def test_inconsistent_scope_does_not_leak_data(self):
        for filters in (dict(company_id=2, sensor_id=1), dict(site_id=2, equipment_id=1),
                        dict(equipment_id=3, sensor_id=2)):
            with self.subTest(filters=filters):
                self.assertEqual(self.ids(**filters), [])

    def test_no_matches(self):
        self.assertEqual(self.ids(company_id=999), [])
        self.assertEqual(self.ids(start_time=END+timedelta(days=1)), [])

    def test_joined_metadata_is_from_correct_ancestors(self):
        value = self.extractor.extract(sensor_id=5)[0]
        self.assertEqual((value.company_id, value.site_id, value.equipment_id, value.sensor_id), (2, 3, 4, 5))
        self.assertEqual((value.company_code, value.site_code, value.equipment_code, value.sensor_code),
                         ("2", "3", "4", "5"))
        self.assertEqual((value.sensor_type, value.sensor_unit, value.sensor_status),
                         ("temperature", "C", "active"))
        self.assertEqual((value.equipment_type, value.equipment_status, value.equipment_criticality),
                         ("pump", "out_of_service", "high"))

    def test_postgresql_offset_bounds_and_native_timestamps(self):
        if self.engine.dialect.name != "postgresql":
            self.skipTest("Requires DASHBOARD_TEST_DATABASE_URL (PostgreSQL)")
        self.db.expunge_all()
        offset = timezone(timedelta(hours=5, minutes=30))
        rows = self.extractor.extract(start_time=START.astimezone(offset), end_time=END.astimezone(offset))
        self.assertEqual([item.measurement_id for item in rows], [3, 4, 5, 8])
        self.assertEqual(rows[0].timestamp, START)
        self.assertIsNotNone(rows[0].timestamp.utcoffset())
