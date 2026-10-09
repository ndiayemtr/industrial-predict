from pydantic import BaseModel, Field, model_validator


class HealthScoreRequest(BaseModel):
    failure_probability: float = Field(
        ge=0.0,
        le=1.0,
    )
    anomaly_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    valid_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)

    corrective_in_progress: bool = False
    overdue_maintenance: bool = False
    planned_soon: bool = False

    @model_validator(mode="after")
    def validate_quality_observations(self):
        total = (
            self.valid_count
            + self.warning_count
            + self.invalid_count
        )

        if total == 0:
            raise ValueError(
                "At least one quality observation is required"
            )

        return self


class HealthScoreComponentsRead(BaseModel):
    failure_health: float
    anomaly_health: float
    data_quality_health: float
    maintenance_health: float


class HealthScoreRead(BaseModel):
    equipment_id: int
    health_score: float
    health_level: str
    components: HealthScoreComponentsRead