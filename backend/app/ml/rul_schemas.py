from dataclasses import dataclass


@dataclass(frozen=True)
class RULPredictionResult:
    rul_hours: float
    rul_level: str