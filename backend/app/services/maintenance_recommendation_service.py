from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.maintenance_recommendation_repository import (
    MaintenanceRecommendationRepository,
)
from app.schemas.maintenance_recommendation import (
    MaintenanceRecommendationRead,
)
from app.core.pagination import build_page


class MaintenanceRecommendationService:

    def __init__(self, db: Session):
        self.equipment_repository = EquipmentRepository(db)
        self.repository = MaintenanceRecommendationRepository(db)

    def list_for_equipment(
        self,
        *,
        equipment_id: int,
        priority: str | None = None,
        recommendation_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[MaintenanceRecommendationRead], int]:

        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if equipment is None:
            raise LookupError(
                "Equipment not found"
            )

        if offset < 0:
            raise ValueError(
                "offset must be greater than or equal to 0"
            )

        if limit < 1:
            raise ValueError(
                "limit must be greater than or equal to 1"
            )

        items, total = self.repository.list_by_equipment(
            equipment_id=equipment_id,
            priority=priority,
            recommendation_type=recommendation_type,
            start_time=start_time,
            end_time=end_time,
            offset=offset,
            limit=limit,
        )

        return (
            [
                MaintenanceRecommendationRead.model_validate(item)
                for item in items
            ],
            total,
        )
        
    def get_paginated(
        self,
        *,
        equipment_id: int,
        page: int,
        page_size: int,
        priority: str | None = None,
        recommendation_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ):
        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if equipment is None:
            raise LookupError(
                "Equipment not found"
            )

        offset = (page - 1) * page_size

        items, total = self.repository.list_by_equipment(
            equipment_id=equipment_id,
            priority=priority,
            recommendation_type=recommendation_type,
            start_time=start_time,
            end_time=end_time,
            offset=offset,
            limit=page_size,
        )

        return build_page(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    
