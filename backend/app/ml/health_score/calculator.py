from app.ml.health_score.aggregator import HealthScoreAggregator
from app.ml.health_score.anomaly_health import AnomalyHealthCalculator
from app.ml.health_score.classifier import HealthLevelClassifier
from app.ml.health_score.data_quality_health import (
    DataQualityHealthCalculator,
)
from app.ml.health_score.failure_health import FailureHealthCalculator
from app.ml.health_score.maintenance_health import (
    MaintenanceHealthCalculator,
)
from app.ml.health_score.schemas import (
    HealthScoreComponents,
    HealthScoreResult,
    HealthScoreWeights,
)


class HealthScoreCalculator:

    def __init__(self):
        self.failure_health_calculator = FailureHealthCalculator()
        self.anomaly_health_calculator = AnomalyHealthCalculator()
        self.data_quality_health_calculator = (
            DataQualityHealthCalculator()
        )
        self.maintenance_health_calculator = (
            MaintenanceHealthCalculator()
        )
        self.aggregator = HealthScoreAggregator()
        self.classifier = HealthLevelClassifier()

    def calculate(
        self,
        *,
        failure_probability: float,
        anomaly_score: float,
        valid_count: int,
        warning_count: int,
        invalid_count: int,
        corrective_in_progress: bool = False,
        overdue_maintenance: bool = False,
        planned_soon: bool = False,
        weights: HealthScoreWeights | None = None,
    ) -> HealthScoreResult:

        failure_health = (
            self.failure_health_calculator.calculate(
                failure_probability
            )
        )

        anomaly_health = (
            self.anomaly_health_calculator.calculate(
                anomaly_score
            )
        )

        data_quality_health = (
            self.data_quality_health_calculator.calculate(
                valid_count=valid_count,
                warning_count=warning_count,
                invalid_count=invalid_count,
            )
        )

        maintenance_health = (
            self.maintenance_health_calculator.calculate(
                corrective_in_progress=corrective_in_progress,
                overdue_maintenance=overdue_maintenance,
                planned_soon=planned_soon,
            )
        )

        components = HealthScoreComponents(
            failure_health=failure_health,
            anomaly_health=anomaly_health,
            data_quality_health=data_quality_health,
            maintenance_health=maintenance_health,
        )

        health_score = self.aggregator.calculate(
            components,
            weights,
        )

        health_level = self.classifier.classify(
            health_score
        )

        return HealthScoreResult(
            health_score=health_score,
            health_level=health_level,
            components=components,
        )