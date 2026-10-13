from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest

from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.maintenance_recommendation_repository import MaintenanceRecommendationRepository
from app.schemas.maintenance_recommendation import MaintenanceRecommendationRead
from app.services.maintenance_recommendation_service import MaintenanceRecommendationService
from recommendations.support import START, create_data


@pytest.fixture
def service():
    result = MaintenanceRecommendationService(None)
    result.equipment_repository = create_autospec(EquipmentRepository, instance=True)
    result.equipment_repository.get_by_id.return_value = SimpleNamespace(id=1)
    result.repository = create_autospec(MaintenanceRecommendationRepository, instance=True)
    result.repository.list_by_equipment.return_value = ([], 0)
    return result


def row():
    return SimpleNamespace(id=7, created_at=START, **create_data().model_dump())


@pytest.mark.parametrize("method,kwargs", [("list_for_equipment", {}),
                                           ("get_paginated", {"page": 1, "page_size": 20})])
def test_missing_equipment_stops_repository(service, method, kwargs):
    service.equipment_repository.get_by_id.return_value = None
    with pytest.raises(LookupError, match="Equipment not found"):
        getattr(service, method)(equipment_id=999, **kwargs)
    service.equipment_repository.get_by_id.assert_called_once_with(999)
    service.repository.list_by_equipment.assert_not_called()


def test_list_maps_orm_items_and_passes_all_filters(service):
    service.repository.list_by_equipment.return_value = ([row()], 11)
    arguments = dict(equipment_id=1, priority="critical", recommendation_type="urgent_maintenance",
                     start_time=START, end_time=START + timedelta(hours=1), offset=3, limit=5)
    items, total = service.list_for_equipment(**arguments)
    assert total == 11
    assert len(items) == 1
    assert isinstance(items[0], MaintenanceRecommendationRead)
    assert items[0].id == 7
    assert items[0].signals.rul_hours == 18.
    service.equipment_repository.get_by_id.assert_called_once_with(1)
    service.repository.list_by_equipment.assert_called_once_with(**arguments)


def test_list_defaults_and_empty_result(service):
    assert service.list_for_equipment(equipment_id=1) == ([], 0)
    service.repository.list_by_equipment.assert_called_once_with(equipment_id=1,
        priority=None, recommendation_type=None, start_time=None, end_time=None, offset=0, limit=20)


@pytest.mark.parametrize("kwargs,message", [({"offset": -1}, "offset"),
                                          ({"limit": 0}, "limit"), ({"limit": -1}, "limit")])
def test_list_rejects_invalid_offset_and_limit(service, kwargs, message):
    with pytest.raises(ValueError, match=message):
        service.list_for_equipment(equipment_id=1, **kwargs)
    service.repository.list_by_equipment.assert_not_called()


@pytest.mark.parametrize("page,page_size,total,pages,offset", [
    (1, 20, 0, 0, 0), (1, 20, 20, 1, 0), (2, 20, 21, 2, 20),
    (3, 5, 11, 3, 10), (10, 5, 11, 3, 45),
])
def test_pagination_offset_and_metadata(service, page, page_size, total, pages, offset):
    service.repository.list_by_equipment.return_value = ([], total)
    result = service.get_paginated(equipment_id=1, page=page, page_size=page_size,
        priority="critical", recommendation_type="urgent_maintenance", start_time=START, end_time=START)
    assert result.model_dump() == dict(items=[], total=total, page=page, page_size=page_size, pages=pages)
    service.equipment_repository.get_by_id.assert_called_once_with(1)
    service.repository.list_by_equipment.assert_called_once_with(equipment_id=1,
        priority="critical", recommendation_type="urgent_maintenance", start_time=START,
        end_time=START, offset=offset, limit=page_size)


def test_paginated_items_pass_through(service):
    record = row()
    service.repository.list_by_equipment.return_value = ([record], 1)
    result = service.get_paginated(equipment_id=1, page=1, page_size=20)
    assert result.items == [record]
    assert result.total == result.pages == 1


def test_service_with_real_repository(db, history):
    service = MaintenanceRecommendationService(db)
    items, total = service.list_for_equipment(equipment_id=1, priority="high")
    assert [item.id for item in items] == [history["tie_first"].id]
    assert total == 1
    result = service.get_paginated(equipment_id=1, page=2, page_size=2)
    assert [item.id for item in result.items] == [history["tie_first"].id, history["early"].id]
    assert (result.total, result.pages) == (4, 2)
