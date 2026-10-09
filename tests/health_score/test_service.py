import unittest
from types import SimpleNamespace
from unittest.mock import create_autospec

# Initialize the existing safe test DB configuration before app service imports.
from dashboard.support import DatabaseCase
from app.ml.health_score.calculator import HealthScoreCalculator
from app.ml.health_score.schemas import HealthScoreComponents, HealthScoreResult
from app.repositories.equipment_repository import EquipmentRepository
from app.schemas.health_score import HealthScoreRead, HealthScoreRequest
from app.services.health_score_service import HealthScoreService
from health_score.support import expected_response, payload


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = HealthScoreService(None)
        self.repository = create_autospec(EquipmentRepository, instance=True)
        self.calculator = create_autospec(HealthScoreCalculator, instance=True)
        self.service.equipment_repository = self.repository
        self.service.calculator = self.calculator

    def test_existing_equipment_delegation_and_exact_mapping(self):
        self.repository.get_by_id.return_value = SimpleNamespace(id=42)
        # Distinct values ensure mapping cannot swap any component.
        self.calculator.calculate.return_value = HealthScoreResult(
            43.21, "poor", HealthScoreComponents(11, 22, 33, 44))
        request = HealthScoreRequest(**payload(overdue_maintenance=True, planned_soon=True))
        result = self.service.calculate_for_equipment(42, request)
        self.repository.get_by_id.assert_called_once_with(42)
        self.calculator.calculate.assert_called_once_with(**request.model_dump())
        self.assertIsInstance(result, HealthScoreRead)
        self.assertEqual(result.model_dump(), dict(equipment_id=42, health_score=43.21, health_level="poor",
            components=dict(failure_health=11, anomaly_health=22, data_quality_health=33, maintenance_health=44)))

    def test_missing_equipment_raises_lookup_error_without_calculation(self):
        self.repository.get_by_id.return_value = None
        with self.assertRaisesRegex(LookupError, "Equipment not found"):
            self.service.calculate_for_equipment(999, HealthScoreRequest(**payload()))
        self.repository.get_by_id.assert_called_once_with(999)
        self.calculator.calculate.assert_not_called()


class ServiceIntegrationTests(DatabaseCase):
    def test_real_repository_and_calculator(self):
        result = HealthScoreService(self.db).calculate_for_equipment(1, HealthScoreRequest(**payload()))
        self.assertEqual(result.model_dump(), expected_response())

    def test_missing_equipment_with_real_repository(self):
        with self.assertRaisesRegex(LookupError, "Equipment not found"):
            HealthScoreService(self.db).calculate_for_equipment(999, HealthScoreRequest(**payload()))
