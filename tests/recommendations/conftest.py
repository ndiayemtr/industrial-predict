from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest

# Initialize the existing safe test configuration before application imports.
from dashboard.support import DatabaseCase
from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.maintenance_recommendation_repository import MaintenanceRecommendationRepository
from app.repositories.prediction_repository import PredictionRepository
from app.services.recommendation_service import RecommendationService
from recommendations.support import seed_history


@pytest.fixture
def db():
    case = DatabaseCase(methodName="runTest")
    try:
        case.setUp()
        yield case.db
    finally:
        case.doCleanups()


@pytest.fixture
def repository(db):
    return MaintenanceRecommendationRepository(db)


@pytest.fixture
def history(repository):
    return seed_history(repository)


@pytest.fixture
def recommendation_service():
    service = RecommendationService(None)
    service.equipment_repository = create_autospec(EquipmentRepository, instance=True)
    service.equipment_repository.get_by_id.return_value = SimpleNamespace(id=42)
    service.prediction_repository = create_autospec(PredictionRepository, instance=True)
    service.prediction_repository.get_latest_by_equipment_and_type.return_value = None
    service.maintenance_recommendation_repository = create_autospec(
        MaintenanceRecommendationRepository, instance=True)
    return service
