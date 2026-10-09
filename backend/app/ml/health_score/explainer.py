from app.ml.health_score.schemas import HealthScoreComponents


class HealthScoreExplainer:

    def explain(
        self,
        components: HealthScoreComponents,
        *,
        top_n: int = 2,
    ) -> list[str]:

        if top_n < 1:
            raise ValueError(
                "top_n must be greater than or equal to 1"
            )

        component_scores = {
            "failure_health": components.failure_health,
            "anomaly_health": components.anomaly_health,
            "data_quality_health": components.data_quality_health,
            "maintenance_health": components.maintenance_health,
        }

        for name, value in component_scores.items():
            if not 0.0 <= value <= 100.0:
                raise ValueError(
                    f"{name} must be between 0 and 100"
                )

        ordered = sorted(
            component_scores.items(),
            key=lambda item: item[1],
        )

        explanations = []

        for name, score in ordered[:top_n]:
            explanations.append(
                f"{name} is one of the weakest components "
                f"with a score of {score:.2f}"
            )

        return explanations