import pandas as pd


class MeasurementOutlierDetector:

    def detect(
        self,
        dataframe: pd.DataFrame,
        *,
        iqr_multiplier: float = 1.5,
    ) -> pd.DataFrame:

        if iqr_multiplier <= 0:
            raise ValueError(
                "iqr_multiplier must be greater than 0"
            )

        result = dataframe.copy()

        if result.empty:
            result["outlier_lower_bound"] = pd.Series(
                dtype="float64"
            )
            result["outlier_upper_bound"] = pd.Series(
                dtype="float64"
            )
            result["outlier_detected"] = pd.Series(
                dtype="bool"
            )
            return result

        result["outlier_lower_bound"] = pd.NA
        result["outlier_upper_bound"] = pd.NA
        result["outlier_detected"] = False

        for sensor_id, group in result.groupby("sensor_id"):

            values = pd.to_numeric(
                group["value"],
                errors="coerce",
            )

            valid_values = values.dropna()

            if valid_values.empty:
                continue

            q1 = valid_values.quantile(0.25)
            q3 = valid_values.quantile(0.75)

            iqr = q3 - q1

            lower_bound = q1 - iqr_multiplier * iqr
            upper_bound = q3 + iqr_multiplier * iqr

            indexes = group.index

            result.loc[
                indexes,
                "outlier_lower_bound",
            ] = lower_bound

            result.loc[
                indexes,
                "outlier_upper_bound",
            ] = upper_bound

            result.loc[
                indexes,
                "outlier_detected",
            ] = (
                (values < lower_bound)
                | (values > upper_bound)
            )

        result["outlier_lower_bound"] = pd.to_numeric(
            result["outlier_lower_bound"],
            errors="coerce",
        )

        result["outlier_upper_bound"] = pd.to_numeric(
            result["outlier_upper_bound"],
            errors="coerce",
        )

        return result

    def summarize(
        self,
        dataframe: pd.DataFrame,
        *,
        iqr_multiplier: float = 1.5,
    ) -> dict:

        detected = self.detect(
            dataframe,
            iqr_multiplier=iqr_multiplier,
        )

        if detected.empty:
            return {
                "outlier_count": 0,
                "sensors_with_outliers": 0,
            }

        outliers = detected[
            detected["outlier_detected"]
        ]

        return {
            "outlier_count": int(
                outliers.shape[0]
            ),
            "sensors_with_outliers": int(
                outliers["sensor_id"].nunique()
            ),
        }