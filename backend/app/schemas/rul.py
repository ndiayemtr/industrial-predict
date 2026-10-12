from pydantic import BaseModel, Field


class RULPredictionRequest(BaseModel):
    features: dict[str, float]


class RULPredictionRead(BaseModel):
    equipment_id: int = Field(ge=1)
    rul_hours: float = Field(ge=0)
    rul_level: str