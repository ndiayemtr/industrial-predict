import pandas as pd


class FailureRiskScorer:

    def build(
        self,
        probabilities: pd.Series,
    ) -> pd.DataFrame:

        if probabilities.empty:
            return pd.DataFrame(
                columns=[
                    "failure_probability",
                    "risk_score",
                    "risk_level",
                ]
            )

        if (
            (probabilities < 0).any()
            or (probabilities > 1).any()
        ):
            raise ValueError(
                "probabilities must be between 0 and 1"
            )

        result = pd.DataFrame(
            {
                "failure_probability": probabilities.astype(float)
            }
        )

        result["risk_score"] = (
            result["failure_probability"]
            * 100
        )

        def classify(probability: float) -> str:
            if probability < 0.25:
                return "low"

            if probability < 0.50:
                return "medium"

            if probability < 0.75:
                return "high"

            return "critical"

        result["risk_level"] = (
            result["failure_probability"]
            .apply(classify)
        )

        return result