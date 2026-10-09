from enum import Enum, StrEnum


class EquipmentStatus(StrEnum):
    OPERATIONAL = "operational"
    MAINTENANCE = "maintenance"
    OUT_OF_SERVICE = "out_of_service"


class EquipmentCriticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SensorStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MeasurementQuality(StrEnum):
    GOOD = "good"
    SUSPECT = "suspect"
    BAD = "bad"
    MISSING = "missing"
    ESTIMATED = "estimated"


class MaintenanceType(StrEnum):
    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    PREDICTIVE = "predictive"


class MaintenanceStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MaintenancePriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class PredictionType(str, Enum):
    ANOMALY = "anomaly"
    FAILURE_RISK = "failure_risk"
    HEALTH_SCORE = "health_score"