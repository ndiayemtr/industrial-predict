import pandas as pd


class QualityFeatureBuilder:

    def build(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return dataframe.copy()

        result = dataframe.copy()

        result["is_gap"] = (
            result["gap_detected"]
            if "gap_detected" in result.columns
            else False
        )

        result["is_quality_warning"] = (
            result["data_quality_status"]
            .eq("warning")
            if "data_quality_status" in result.columns
            else False
        )

        result["is_quality_invalid"] = (
            result["data_quality_status"]
            .eq("invalid")
            if "data_quality_status" in result.columns
            else False
        )

        duplicate_measurement = (
            result["duplicate_measurement_id"]
            if "duplicate_measurement_id" in result.columns
            else False
        )

        duplicate_timestamp = (
            result["duplicate_sensor_timestamp"]
            if "duplicate_sensor_timestamp" in result.columns
            else False
        )

        result["is_duplicate"] = (
            duplicate_measurement
            | duplicate_timestamp
        )

        result["is_outlier"] = (
            result["outlier_detected"]
            if "outlier_detected" in result.columns
            else False
        )

        return result