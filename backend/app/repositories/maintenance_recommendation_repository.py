from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.maintenance_recommendation import (
    MaintenanceRecommendation,
)
from app.schemas.maintenance_recommendation import (
    MaintenanceRecommendationCreate,
)
from datetime import datetime

from sqlalchemy import func, select

class MaintenanceRecommendationRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def create(
        self,
        data: MaintenanceRecommendationCreate,
    ) -> MaintenanceRecommendation:

        recommendation = MaintenanceRecommendation(
            equipment_id=data.equipment_id,
            priority=data.priority,
            recommendation_type=data.recommendation_type,
            title=data.title,
            reason=data.reason,
            recommended_action=data.recommended_action,
            signals=data.signals.model_dump(),
            generated_at=data.generated_at,
        )

        self.db.add(
            recommendation
        )
        self.db.commit()
        self.db.refresh(
            recommendation
        )

        return recommendation

    def get_by_id(
        self,
        recommendation_id: int,
    ) -> MaintenanceRecommendation | None:

        stmt = select(
            MaintenanceRecommendation
        ).where(
            MaintenanceRecommendation.id
            == recommendation_id
        )

        return self.db.scalar(
            stmt
        )

    def get_latest_by_equipment(
        self,
        equipment_id: int,
    ) -> MaintenanceRecommendation | None:

        stmt = (
            select(
                MaintenanceRecommendation
            )
            .where(
                MaintenanceRecommendation.equipment_id
                == equipment_id
            )
            .order_by(
                MaintenanceRecommendation.generated_at.desc(),
                MaintenanceRecommendation.id.desc(),
            )
            .limit(1)
        )

        return self.db.scalar(
            stmt
        )
        
    def list_by_equipment(
        self,
        *,
        equipment_id: int,
        priority: str | None = None,
        recommendation_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[MaintenanceRecommendation], int]:

        filters = [
            MaintenanceRecommendation.equipment_id == equipment_id
        ]

        if priority is not None:
            filters.append(
                MaintenanceRecommendation.priority == priority
            )

        if recommendation_type is not None:
            filters.append(
                MaintenanceRecommendation.recommendation_type
                == recommendation_type
            )

        if start_time is not None:
            filters.append(
                MaintenanceRecommendation.generated_at >= start_time
            )

        if end_time is not None:
            filters.append(
                MaintenanceRecommendation.generated_at <= end_time
            )

        count_stmt = (
            select(
                func.count(MaintenanceRecommendation.id)
            )
            .where(*filters)
        )

        total = self.db.scalar(
            count_stmt
        ) or 0

        stmt = (
            select(
                MaintenanceRecommendation
            )
            .where(*filters)
            .order_by(
                MaintenanceRecommendation.generated_at.desc(),
                MaintenanceRecommendation.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        items = list(
            self.db.scalars(stmt).all()
        )

        return items, total