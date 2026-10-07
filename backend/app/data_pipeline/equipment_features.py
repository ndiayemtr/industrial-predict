import pandas as pd


class EquipmentFeatureBuilder:

    def build(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return pd.DataFrame(
                columns=[
                    "equipment_id",
                    "sensor_count",
                    "measurement_count",
                    "value_mean",
                    "value_std",
                    "outlier_ratio",
                    "gap_ratio",
                    "invalid_quality_ratio",
                ]
            )

        required_columns = {
            "equipment_id",
            "sensor_id",
            "value",
        }

        missing_columns = (
            required_columns
            - set(dataframe.columns)
        )

        if missing_columns:
            raise ValueError(
                "Missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        result = dataframe.copy()

        if "is_outlier" not in result.columns:
            result["is_outlier"] = False

        if "is_gap" not in result.columns:
            result["is_gap"] = False

        if "is_quality_invalid" not in result.columns:
            result["is_quality_invalid"] = False

        grouped = result.groupby(
            "equipment_id"
        )

        features = grouped.agg(
            sensor_count=(
                "sensor_id",
                "nunique",
            ),
            measurement_count=(
                "value",
                "count",
            ),
            value_mean=(
                "value",
                "mean",
            ),
            value_std=(
                "value",
                "std",
            ),
            outlier_ratio=(
                "is_outlier",
                "mean",
            ),
            gap_ratio=(
                "is_gap",
                "mean",
            ),
            invalid_quality_ratio=(
                "is_quality_invalid",
                "mean",
            ),
        ).reset_index()

        return features