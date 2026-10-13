from typing import Literal

from pydantic import BaseModel, Field


RecommendationPriority = Literal[
    "critical",
    "high",
    "medium",
    "low",
]

RecommendationType = Literal[
    "urgent_maintenance",
    "inspection",
    "planned_maintenance",
    "monitoring",
    "no_action",
]


class RecommendationSignals(BaseModel):
    anomaly_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    failure_probability: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    health_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    rul_hours: float | None = Field(
        default=None,
        ge=0,
    )


class RecommendationRead(BaseModel):
    equipment_id: int = Field(ge=1)
    priority: RecommendationPriority
    recommendation_type: RecommendationType
    title: str
    reason: str
    recommended_action: str
    signals: RecommendationSignals