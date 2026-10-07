import pandas as pd

from app.data_pipeline.failure_labeler import FailureLabeler


class FailureRiskDatasetBuilder:

    def __init__(self):
        self.failure_labeler = FailureLabeler()

    def build(
        self,
        feature_dataframe: pd.DataFrame,
        maintenance_records: pd.DataFrame,
        *,
        horizon_hours: float = 24.0,
    ) -> pd.DataFrame:

        if feature_dataframe.empty:
            return feature_dataframe.copy()

        required_columns = {
            "equipment_id",
            "timestamp",
        }

        missing_columns = (
            required_columns
            - set(feature_dataframe.columns)
        )

        if missing_columns:
            raise ValueError(
                "Missing feature columns: "
                + ", ".join(
                    sorted(missing_columns)
                )
            )

        result = self.failure_labeler.build(
            feature_dataframe,
            maintenance_records,
            horizon_hours=horizon_hours,
        )

        result["failure_within_horizon"] = (
            result["failure_within_horizon"]
            .astype("int8")
        )

        return result

    def summarize(
        self,
        dataframe: pd.DataFrame,
    ) -> dict:

        if dataframe.empty:
            return {
                "row_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "positive_ratio": 0.0,
            }

        if "failure_within_horizon" not in dataframe.columns:
            raise ValueError(
                "Missing required column: "
                "failure_within_horizon"
            )

        positive_count = int(
            dataframe["failure_within_horizon"].sum()
        )

        row_count = len(dataframe)

        negative_count = (
            row_count - positive_count
        )

        return {
            "row_count": row_count,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "positive_ratio": (
                positive_count / row_count
            ),
        }