from app.schemas.recommendation import RecommendationSignals


class RecommendationPriorityResolver:

    CRITICAL_RUL_HOURS = 24
    HIGH_RUL_HOURS = 72
    MEDIUM_RUL_HOURS = 168

    CRITICAL_FAILURE_PROBABILITY = 0.75

    CRITICAL_HEALTH_SCORE = 30
    HIGH_HEALTH_SCORE = 50

    MODERATE_ANOMALY_SCORE = 0.50

    def resolve(
        self,
        signals: RecommendationSignals,
    ) -> str:

        if (
            signals.rul_hours is not None
            and signals.rul_hours <= self.CRITICAL_RUL_HOURS
        ):
            return "critical"

        if (
            signals.failure_probability is not None
            and signals.failure_probability
            >= self.CRITICAL_FAILURE_PROBABILITY
        ):
            return "critical"

        if (
            signals.health_score is not None
            and signals.health_score < self.CRITICAL_HEALTH_SCORE
        ):
            return "critical"

        if (
            signals.rul_hours is not None
            and signals.rul_hours <= self.HIGH_RUL_HOURS
        ):
            return "high"

        if (
            signals.health_score is not None
            and self.CRITICAL_HEALTH_SCORE
            <= signals.health_score
            < self.HIGH_HEALTH_SCORE
        ):
            return "high"

        if (
            signals.rul_hours is not None
            and signals.rul_hours <= self.MEDIUM_RUL_HOURS
        ):
            return "medium"

        if (
            signals.anomaly_score is not None
            and signals.anomaly_score >= self.MODERATE_ANOMALY_SCORE
        ):
            return "medium"

        return "low"