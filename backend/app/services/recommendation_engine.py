from app.schemas.recommendation import (
    RecommendationRead,
    RecommendationSignals,
)
from app.services.recommendation_explainer import (
    RecommendationExplainer,
)
from app.services.recommendation_priority import (
    RecommendationPriorityResolver,
)


class RecommendationEngine:

    def __init__(self):
        self.priority_resolver = RecommendationPriorityResolver()
        self.explainer = RecommendationExplainer()

    def recommend(
        self,
        *,
        equipment_id: int,
        signals: RecommendationSignals,
    ) -> RecommendationRead:

        if all(
            value is None
            for value in (
                signals.anomaly_score,
                signals.failure_probability,
                signals.health_score,
                signals.rul_hours,
            )
        ):
            raise ValueError(
                "At least one recommendation signal is required"
            )

        priority = self.priority_resolver.resolve(
            signals
        )

        recommendation_type = self._resolve_recommendation_type(
            priority=priority,
            signals=signals,
        )

        title, reason, recommended_action = self.explainer.explain(
            priority=priority,
            recommendation_type=recommendation_type,
            signals=signals,
        )

        return RecommendationRead(
            equipment_id=equipment_id,
            priority=priority,
            recommendation_type=recommendation_type,
            title=title,
            reason=reason,
            recommended_action=recommended_action,
            signals=signals,
        )

    def _resolve_recommendation_type(
        self,
        *,
        priority: str,
        signals: RecommendationSignals,
    ) -> str:

        if priority == "critical":
            return "urgent_maintenance"

        if priority == "high":
            if (
                signals.rul_hours is not None
                and signals.rul_hours <= 72
            ):
                return "planned_maintenance"

            return "inspection"

        if priority == "medium":
            if (
                signals.rul_hours is not None
                and signals.rul_hours <= 168
            ):
                return "planned_maintenance"

            return "monitoring"

        return "no_action"