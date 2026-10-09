class HealthLevelClassifier:

    def classify(
        self,
        health_score: float,
    ) -> str:

        if not 0.0 <= health_score <= 100.0:
            raise ValueError(
                "health_score must be between 0 and 100"
            )

        if health_score >= 85.0:
            return "healthy"

        if health_score >= 70.0:
            return "good"

        if health_score >= 50.0:
            return "degraded"

        if health_score >= 30.0:
            return "poor"

        return "critical"