from sqlalchemy.orm import Session

from app.repositories.equipment_repository import EquipmentRepository
from app.schemas.recommendation import (
    RecommendationRead,
    RecommendationSignals,
)
from app.services.recommendation_engine import RecommendationEngine
from app.repositories.prediction_repository import PredictionRepository
from datetime import datetime, timezone

from app.repositories.maintenance_recommendation_repository import (
    MaintenanceRecommendationRepository,
)
from app.schemas.maintenance_recommendation import (
    MaintenanceRecommendationCreate,
)


class RecommendationService:

    def __init__(self, db: Session):
        self.equipment_repository = EquipmentRepository(db)
        self.engine = RecommendationEngine()
        self.prediction_repository = PredictionRepository(db)
        self.maintenance_recommendation_repository = (
            MaintenanceRecommendationRepository(db)
        )

    def recommend_for_equipment(
        self,
        *,
        equipment_id: int,
        signals: RecommendationSignals,
    ) -> RecommendationRead:

        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if equipment is None:
            raise LookupError(
                "Equipment not found"
            )

        return self.engine.recommend(
            equipment_id=equipment.id,
            signals=signals,
        )
    def recommend_from_latest_predictions(
        self,
        *,
        equipment_id: int,
    ) -> RecommendationRead:

        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if equipment is None:
            raise LookupError(
                "Equipment not found"
            )

        anomaly = (
            self.prediction_repository
            .get_latest_by_equipment_and_type(
                equipment_id,
                "anomaly",
            )
        )

        failure_risk = (
            self.prediction_repository
            .get_latest_by_equipment_and_type(
                equipment_id,
                "failure_risk",
            )
        )

        health_score = (
            self.prediction_repository
            .get_latest_by_equipment_and_type(
                equipment_id,
                "health_score",
            )
        )

        rul = (
            self.prediction_repository
            .get_latest_by_equipment_and_type(
                equipment_id,
                "rul",
            )
        )

        failure_probability = None

        if failure_risk is not None:
            failure_probability = (
                failure_risk.details or {}
            ).get(
                "failure_probability"
            )

        signals = RecommendationSignals(
            anomaly_score=(
                anomaly.score
                if anomaly is not None
                else None
            ),
            failure_probability=failure_probability,
            health_score=(
                health_score.score
                if health_score is not None
                else None
            ),
            rul_hours=(
                rul.score
                if rul is not None
                else None
            ),
        )

        recommendation = self.engine.recommend(
            equipment_id=equipment.id,
            signals=signals,
        )

        self.maintenance_recommendation_repository.create(
            MaintenanceRecommendationCreate(
                equipment_id=recommendation.equipment_id,
                priority=recommendation.priority,
                recommendation_type=recommendation.recommendation_type,
                title=recommendation.title,
                reason=recommendation.reason,
                recommended_action=recommendation.recommended_action,
                signals=recommendation.signals,
                generated_at=datetime.now(timezone.utc),
            )
        )

        return recommendation