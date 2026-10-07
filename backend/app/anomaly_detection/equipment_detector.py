import pandas as pd


class EquipmentAnomalyDetector:

    def summarize(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return pd.DataFrame(
                columns=[
                    "equipment_id",
                    "sensor_count",
                    "measurement_count",
                    "anomaly_count",
                    "anomaly_ratio",
                    "max_anomaly_score",
                    "mean_anomaly_score",
                    "equipment_anomaly",
                ]
            )

        required_columns = {
            "equipment_id",
            "sensor_id",
            "anomaly_score",
            "is_anomaly",
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

        result = (
            dataframe
            .groupby("equipment_id")
            .agg(
                sensor_count=(
                    "sensor_id",
                    "nunique",
                ),
                measurement_count=(
                    "is_anomaly",
                    "count",
                ),
                anomaly_count=(
                    "is_anomaly",
                    "sum",
                ),
                anomaly_ratio=(
                    "is_anomaly",
                    "mean",
                ),
                max_anomaly_score=(
                    "anomaly_score",
                    "max",
                ),
                mean_anomaly_score=(
                    "anomaly_score",
                    "mean",
                ),
            )
            .reset_index()
        )

        result["equipment_anomaly"] = (
            result["anomaly_count"] > 0
        )

        return result