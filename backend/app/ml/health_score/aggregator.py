from app.ml.health_score.schemas import (
    HealthScoreComponents,
    HealthScoreWeights,
)


class HealthScoreAggregator:

    def calculate(
        self,
        components: HealthScoreComponents,
        weights: HealthScoreWeights | None = None,
    ) -> float:

        if weights is None:
            weights = HealthScoreWeights()

        component_values = {
            "failure_health": components.failure_health,
            "anomaly_health": components.anomaly_health,
            "data_quality_health": components.data_quality_health,
            "maintenance_health": components.maintenance_health,
        }

        for name, value in component_values.items():
            if not 0.0 <= value <= 100.0:
                raise ValueError(
                    f"{name} must be between 0 and 100"
                )

        weight_values = {
            "failure_risk": weights.failure_risk,
            "anomaly": weights.anomaly,
            "data_quality": weights.data_quality,
            "maintenance": weights.maintenance,
        }

        for name, value in weight_values.items():
            if value < 0.0:
                raise ValueError(
                    f"{name} weight must be greater than or equal to 0"
                )

        total_weight = sum(weight_values.values())

        if abs(total_weight - 1.0) > 1e-9:
            raise ValueError(
                "Health Score weights must sum to 1.0"
            )

        score = (
            components.failure_health
            * weights.failure_risk
            + components.anomaly_health
            * weights.anomaly
            + components.data_quality_health
            * weights.data_quality
            + components.maintenance_health
            * weights.maintenance
        )

        return round(score, 2)