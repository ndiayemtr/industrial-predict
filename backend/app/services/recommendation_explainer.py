from app.schemas.recommendation import (
    RecommendationPriority,
    RecommendationSignals,
    RecommendationType,
)


class RecommendationExplainer:

    def explain(
        self,
        *,
        priority: RecommendationPriority,
        recommendation_type: RecommendationType,
        signals: RecommendationSignals,
    ) -> tuple[str, str, str]:

        if priority == "critical":
            reasons = []

            if (
                signals.rul_hours is not None
                and signals.rul_hours <= 24
            ):
                reasons.append(
                    "remaining useful life is 24 hours or less"
                )

            if (
                signals.failure_probability is not None
                and signals.failure_probability >= 0.75
            ):
                reasons.append(
                    "failure probability is 75% or higher"
                )

            if (
                signals.health_score is not None
                and signals.health_score < 30
            ):
                reasons.append(
                    "equipment health score is below 30"
                )

            return (
                "Urgent maintenance required",
                "Critical maintenance condition detected because "
                + ", ".join(reasons)
                + ".",
                (
                    "Inspect the equipment immediately and prepare "
                    "an urgent maintenance intervention."
                ),
            )

        if priority == "high":
            if recommendation_type == "planned_maintenance":
                return (
                    "Maintenance should be planned soon",
                    "Remaining useful life indicates that maintenance "
                    "should be scheduled soon.",
                    "Plan maintenance within the next operating cycles.",
                )

            return (
                "Technical inspection recommended",
                "Equipment health indicates significant degradation.",
                (
                    "Inspect the equipment and identify the main "
                    "sources of degradation."
                ),
            )

        if priority == "medium":
            if recommendation_type == "planned_maintenance":
                return (
                    "Maintenance planning recommended",
                    "Remaining useful life indicates upcoming maintenance.",
                    (
                        "Include the equipment in the upcoming "
                        "maintenance plan."
                    ),
                )

            return (
                "Enhanced monitoring recommended",
                "An anomaly signal requires closer monitoring.",
                (
                    "Increase monitoring frequency and review "
                    "the latest sensor measurements."
                ),
            )

        return (
            "No immediate maintenance action required",
            "No significant maintenance risk was detected.",
            "Continue normal equipment monitoring.",
        )