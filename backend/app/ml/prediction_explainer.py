import pandas as pd


class FailureRiskPredictionExplainer:

    def explain_global(
        self,
        feature_importances: pd.DataFrame,
        *,
        top_n: int = 5,
    ) -> pd.DataFrame:

        if top_n < 1:
            raise ValueError(
                "top_n must be greater than or equal to 1"
            )

        if feature_importances.empty:
            return feature_importances.copy()

        required_columns = {
            "feature",
            "importance",
        }

        missing_columns = (
            required_columns
            - set(feature_importances.columns)
        )

        if missing_columns:
            raise ValueError(
                "Missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        result = (
            feature_importances
            .sort_values(
                by="importance",
                ascending=False,
            )
            .head(top_n)
            .reset_index(drop=True)
        )

        result["importance_percent"] = (
            result["importance"]
            * 100
        )

        return result

    def build_summary(
        self,
        feature_importances: pd.DataFrame,
        *,
        top_n: int = 3,
    ) -> str:

        top_features = self.explain_global(
            feature_importances,
            top_n=top_n,
        )

        if top_features.empty:
            return "No feature importance available."

        parts = []

        for _, row in top_features.iterrows():
            parts.append(
                f"{row['feature']} "
                f"({row['importance_percent']:.1f}%)"
            )

        return (
            "Most influential features: "
            + ", ".join(parts)
        )