import pandas as pd

from app.data_pipeline.rul_labeler import RULLabeler


class RULDatasetBuilder:

    def __init__(self):
        self.rul_labeler = RULLabeler()

    def build(
        self,
        feature_dataframe: pd.DataFrame,
        maintenance_records: pd.DataFrame,
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

        result = self.rul_labeler.build(
            feature_dataframe,
            maintenance_records,
        )

        return result

    def summarize(
        self,
        dataframe: pd.DataFrame,
    ) -> dict:

        if dataframe.empty:
            return {
                "row_count": 0,
                "labeled_count": 0,
                "unlabeled_count": 0,
                "labeled_ratio": 0.0,
            }

        if "rul_hours" not in dataframe.columns:
            raise ValueError(
                "Missing required column: rul_hours"
            )

        labeled_count = int(
            dataframe["rul_hours"]
            .notna()
            .sum()
        )

        row_count = len(dataframe)

        unlabeled_count = (
            row_count - labeled_count
        )

        return {
            "row_count": row_count,
            "labeled_count": labeled_count,
            "unlabeled_count": unlabeled_count,
            "labeled_ratio": (
                labeled_count / row_count
            ),
        }