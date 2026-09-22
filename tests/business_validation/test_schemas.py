import unittest
from datetime import datetime, timedelta, timezone, tzinfo

from pydantic import ValidationError

from app.core.enums import (
    EquipmentCriticality, EquipmentStatus, MaintenancePriority,
    MaintenanceStatus, MaintenanceType, MeasurementQuality, SensorStatus,
)
from app.schemas.equipment import EquipmentCreate, EquipmentUpdate
from app.schemas.maintenance import MaintenanceCreate, MaintenanceUpdate
from app.schemas.measurement import MeasurementCreate, MeasurementUpdate
from app.schemas.sensor import SensorCreate, SensorUpdate


AWARE = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
NAIVE = AWARE.replace(tzinfo=None)
EQUIPMENT = dict(name="Pump", code="P1", equipment_type="pump", site_id=1)
SENSOR = dict(name="Temperature", code="T1", sensor_type="temperature", unit="C", equipment_id=1)
MEASUREMENT = dict(sensor_id=1, timestamp=AWARE, value=12.5)
MAINTENANCE = dict(equipment_id=1, title="Inspection", maintenance_type="preventive")


class NoOffsetTimezone(tzinfo):
    def utcoffset(self, dt):
        return None


class ValidationAssertions(unittest.TestCase):
    def assert_field_rejected(self, schema, payload, field, error_type=None):
        with self.assertRaises(ValidationError) as caught:
            schema.model_validate(payload)
        errors = [error for error in caught.exception.errors() if error["loc"] == (field,)]
        self.assertTrue(errors, caught.exception.errors())
        if error_type:
            self.assertIn(error_type, [error["type"] for error in errors])


class EnumValidationTests(ValidationAssertions):
    def check_enum(self, create, update, payload, field, enum, expected_values):
        # Explicit business vocabulary: iterating the Enum alone would miss deletions.
        self.assertEqual({member.value for member in enum}, set(expected_values))
        for schema, base in ((create, payload), (update, {})):
            for value in expected_values:
                for supplied in (value, enum(value)):
                    with self.subTest(schema=schema.__name__, field=field, value=supplied):
                        result = schema.model_validate(base | {field: supplied})
                        self.assertIs(getattr(result, field), enum(value))
                        self.assertEqual(result.model_dump(mode="json")[field], value)
            for value in ("invalid", "", " " + expected_values[0], expected_values[0].upper(), 123):
                with self.subTest(schema=schema.__name__, field=field, invalid=value):
                    self.assert_field_rejected(schema, base | {field: value}, field, "enum")

    def test_equipment_status(self):
        self.check_enum(EquipmentCreate, EquipmentUpdate, EQUIPMENT, "status", EquipmentStatus,
                        ("operational", "maintenance", "out_of_service"))

    def test_equipment_criticality(self):
        self.check_enum(EquipmentCreate, EquipmentUpdate, EQUIPMENT, "criticality", EquipmentCriticality,
                        ("low", "medium", "high", "critical"))

    def test_sensor_status(self):
        self.check_enum(SensorCreate, SensorUpdate, SENSOR, "status", SensorStatus, ("active", "inactive"))

    def test_measurement_quality(self):
        self.check_enum(MeasurementCreate, MeasurementUpdate, MEASUREMENT, "quality", MeasurementQuality,
                        ("good", "suspect", "bad", "missing", "estimated"))

    def test_maintenance_type(self):
        self.check_enum(MaintenanceCreate, MaintenanceUpdate, MAINTENANCE, "maintenance_type", MaintenanceType,
                        ("preventive", "corrective", "predictive"))

    def test_maintenance_status(self):
        self.check_enum(MaintenanceCreate, MaintenanceUpdate, MAINTENANCE, "status", MaintenanceStatus,
                        ("planned", "in_progress", "completed", "cancelled"))

    def test_maintenance_priority(self):
        self.check_enum(MaintenanceCreate, MaintenanceUpdate, MAINTENANCE, "priority", MaintenancePriority,
                        ("low", "medium", "high", "critical"))

    def test_create_defaults(self):
        equipment = EquipmentCreate(**EQUIPMENT)
        self.assertEqual(equipment.status, EquipmentStatus.OPERATIONAL)
        self.assertEqual(equipment.criticality, EquipmentCriticality.MEDIUM)
        self.assertEqual(SensorCreate(**SENSOR).status, SensorStatus.ACTIVE)
        self.assertEqual(MeasurementCreate(**MEASUREMENT).quality, MeasurementQuality.GOOD)
        maintenance = MaintenanceCreate(**MAINTENANCE)
        self.assertEqual(maintenance.status, MaintenanceStatus.PLANNED)
        self.assertEqual(maintenance.priority, MaintenancePriority.MEDIUM)

    def test_empty_updates_do_not_supply_defaults(self):
        for schema in (EquipmentUpdate, SensorUpdate, MeasurementUpdate, MaintenanceUpdate):
            with self.subTest(schema=schema.__name__):
                self.assertEqual(schema().model_dump(exclude_unset=True), {})


class SensorUnitTests(ValidationAssertions):
    def test_create_requires_unit(self):
        self.assert_field_rejected(SensorCreate, {k: v for k, v in SENSOR.items() if k != "unit"},
                                   "unit", "missing")

    def test_create_rejects_empty_unit(self):
        self.assert_field_rejected(SensorCreate, SENSOR | {"unit": ""}, "unit", "string_too_short")

    def test_create_rejects_null_unit(self):
        self.assert_field_rejected(SensorCreate, SENSOR | {"unit": None}, "unit")

    def test_update_rejects_empty_unit(self):
        self.assert_field_rejected(SensorUpdate, {"unit": ""}, "unit", "string_too_short")

    def test_nonempty_unit_accepted_on_create_and_update(self):
        for schema, base in ((SensorCreate, SENSOR), (SensorUpdate, {})):
            for unit in ("C", "mm/s", "°C"):
                with self.subTest(schema=schema.__name__, unit=unit):
                    self.assertEqual(schema.model_validate(base | {"unit": unit}).unit, unit)

    def test_partial_update_can_omit_unit(self):
        self.assertEqual(SensorUpdate(status="active").model_dump(exclude_unset=True),
                         {"status": SensorStatus.ACTIVE})


class MeasurementTimestampTests(ValidationAssertions):
    def test_timezone_accepted_on_create_and_update(self):
        for schema, base in ((MeasurementCreate, MEASUREMENT), (MeasurementUpdate, {})):
            for value in (AWARE, AWARE.astimezone(timezone(timedelta(hours=5, minutes=30))),
                          "2026-01-01T12:00:00Z", "2026-01-01T17:30:00+05:30"):
                with self.subTest(schema=schema.__name__, value=value):
                    result = schema.model_validate(base | {"timestamp": value})
                    self.assertEqual(result.timestamp, AWARE)
                    self.assertIsNotNone(result.timestamp.utcoffset())

    def test_naive_timestamp_rejected_on_create_and_update(self):
        for schema, base in ((MeasurementCreate, MEASUREMENT), (MeasurementUpdate, {})):
            for value in (NAIVE, "2026-01-01T12:00:00", NAIVE.replace(tzinfo=NoOffsetTimezone())):
                with self.subTest(schema=schema.__name__, value=value):
                    self.assert_field_rejected(schema, base | {"timestamp": value}, "timestamp", "value_error")

    def test_update_null_does_not_raise_unhandled_attribute_error(self):
        # The annotated nullable field may be accepted or rejected by validation,
        # but must never leak AttributeError instead of a client validation error.
        try:
            result = MeasurementUpdate(timestamp=None)
        except ValidationError as error:
            self.assertIn(("timestamp",), [item["loc"] for item in error.errors()])
        else:
            self.assertIsNone(result.timestamp)


class MaintenanceValidationTests(ValidationAssertions):
    def test_timezone_dates_accepted_on_create_and_update(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            for field in ("planned_at", "started_at", "completed_at"):
                for value in (AWARE, "2026-01-01T17:30:00+05:30"):
                    with self.subTest(schema=schema.__name__, field=field, value=value):
                        self.assertEqual(getattr(schema.model_validate(base | {field: value}), field), AWARE)

    def test_naive_dates_rejected_on_create(self):
        for field in ("planned_at", "started_at", "completed_at"):
            for value in (NAIVE, "2026-01-01T12:00:00", NAIVE.replace(tzinfo=NoOffsetTimezone())):
                with self.subTest(field=field, value=value):
                    self.assert_field_rejected(MaintenanceCreate, MAINTENANCE | {field: value}, field, "value_error")

    def test_update_rejects_naive_planned_at(self):
        self.assert_field_rejected(MaintenanceUpdate, {"planned_at": NAIVE}, "planned_at", "value_error")

    def test_update_rejects_naive_started_at(self):
        self.assert_field_rejected(MaintenanceUpdate, {"started_at": NAIVE}, "started_at", "value_error")

    def test_update_rejects_naive_completed_at(self):
        self.assert_field_rejected(MaintenanceUpdate, {"completed_at": NAIVE}, "completed_at", "value_error")

    def test_optional_dates_can_be_null(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            with self.subTest(schema=schema.__name__):
                result = schema.model_validate(base | dict(planned_at=None, started_at=None, completed_at=None))
                self.assertIsNone(result.planned_at)
                self.assertIsNone(result.started_at)
                self.assertIsNone(result.completed_at)

    def test_started_before_or_equal_to_completed_is_accepted(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            for end in (AWARE, AWARE+timedelta(seconds=1), AWARE.astimezone(timezone(timedelta(hours=-4)))):
                with self.subTest(schema=schema.__name__, end=end):
                    result = schema.model_validate(base | dict(started_at=AWARE, completed_at=end))
                    self.assertLessEqual(result.started_at, result.completed_at)

    def test_started_after_completed_is_rejected(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            with self.subTest(schema=schema.__name__):
                with self.assertRaises(ValidationError) as caught:
                    schema.model_validate(base | dict(started_at=AWARE+timedelta(microseconds=1), completed_at=AWARE))
                self.assertTrue(any(error["type"] == "value_error" and error["loc"] == ()
                                    for error in caught.exception.errors()))

    def test_chronology_compares_instants_not_local_clock(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            with self.subTest(schema=schema.__name__):
                result = schema.model_validate(base | dict(
                    started_at="2026-01-01T13:00:00+02:00", completed_at="2026-01-01T12:00:00Z"))
                self.assertLess(result.started_at, result.completed_at)
                with self.assertRaises(ValidationError):
                    schema.model_validate(base | dict(
                        started_at="2026-01-01T10:00:00-03:00", completed_at="2026-01-01T12:00:00Z"))

    def test_partial_update_can_supply_only_one_date(self):
        for field in ("started_at", "completed_at"):
            with self.subTest(field=field):
                self.assertEqual(MaintenanceUpdate(**{field: AWARE}).model_dump(exclude_unset=True), {field: AWARE})

    def test_zero_downtime_is_accepted(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            with self.subTest(schema=schema.__name__):
                self.assertEqual(schema.model_validate(base | {"downtime_minutes": 0}).downtime_minutes, 0)

    def test_negative_downtime_is_rejected(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            with self.subTest(schema=schema.__name__):
                self.assert_field_rejected(schema, base | {"downtime_minutes": -1}, "downtime_minutes", "greater_than_equal")

    def test_zero_cost_is_accepted(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            with self.subTest(schema=schema.__name__):
                self.assertEqual(schema.model_validate(base | {"cost": 0}).cost, 0)

    def test_negative_cost_is_rejected(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            with self.subTest(schema=schema.__name__):
                self.assert_field_rejected(schema, base | {"cost": -0.01}, "cost", "greater_than_equal")

    def test_positive_and_missing_numeric_values_are_accepted(self):
        for schema, base in ((MaintenanceCreate, MAINTENANCE), (MaintenanceUpdate, {})):
            for values in (dict(downtime_minutes=30, cost=12.5), dict(downtime_minutes=None, cost=None)):
                with self.subTest(schema=schema.__name__, values=values):
                    result = schema.model_validate(base | values)
                    self.assertEqual(result.downtime_minutes, values["downtime_minutes"])
                    self.assertEqual(result.cost, values["cost"])
