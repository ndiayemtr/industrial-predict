import pandas as pd


class AnomalyExplainer:

    def explain(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            result = dataframe.copy()
            result["anomaly_reason"] = pd.Series(dtype="str")
            return result

        result = dataframe.copy()

        def build_reason(row) -> str | None:
            reasons = []

            if bool(
                row.get(
                    "statistical_anomaly",
                    False,
                )
            ):
                reasons.append(
                    "statistical deviation"
                )

            if bool(
                row.get(
                    "robust_zscore_anomaly",
                    False,
                )
            ):
                reasons.append(
                    "robust z-score anomaly"
                )

            if bool(
                row.get(
                    "isolation_forest_anomaly",
                    False,
                )
            ):
                reasons.append(
                    "isolation forest anomaly"
                )

            if bool(
                row.get(
                    "is_gap",
                    False,
                )
            ):
                reasons.append(
                    "measurement gap"
                )

            if bool(
                row.get(
                    "is_outlier",
                    False,
                )
            ):
                reasons.append(
                    "statistical outlier"
                )

            if not reasons:
                return None

            return ", ".join(reasons)

        result["anomaly_reason"] = result.apply(
            build_reason,
            axis=1,
        )

        return result