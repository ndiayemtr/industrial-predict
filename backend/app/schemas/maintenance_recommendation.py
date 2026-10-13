from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.recommendation import (
    RecommendationPriority,
    RecommendationSignals,
    RecommendationType,
)


class MaintenanceRecommendationCreate(BaseModel):
    equipment_id: int
    priority: RecommendationPriority
    recommendation_type: RecommendationType
    title: str
    reason: str
    recommended_action: str
    signals: RecommendationSignals
    generated_at: datetime


class MaintenanceRecommendationRead(
    MaintenanceRecommendationCreate
):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    created_at: datetime