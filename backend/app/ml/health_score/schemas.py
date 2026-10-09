from dataclasses import dataclass


@dataclass(frozen=True)
class HealthScoreComponents:
    failure_health: float
    anomaly_health: float
    data_quality_health: float
    maintenance_health: float


@dataclass(frozen=True)
class HealthScoreWeights:
    failure_risk: float = 0.40
    anomaly: float = 0.30
    data_quality: float = 0.15
    maintenance: float = 0.15


@dataclass(frozen=True)
class HealthScoreResult:
    health_score: float
    health_level: str
    components: HealthScoreComponents