from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.maintenance_recommendation import (
    MaintenanceRecommendation,
)
from app.schemas.maintenance_recommendation import (
    MaintenanceRecommendationCreate,
)


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