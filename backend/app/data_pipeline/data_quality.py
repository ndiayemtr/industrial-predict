import pandas as pd


class DataQualityReport:

    def analyze(
        self,
        dataframe: pd.DataFrame,
    ) -> dict:

        if dataframe.empty:
            return {
                "row_count": 0,
                "missing_values": {},
                "duplicate_measurements": 0,
                "invalid_values": 0,
                "invalid_timestamps": 0,
                "quality_distribution": {},
            }

        missing_values = (
            dataframe
            .isna()
            .sum()
            .to_dict()
        )

        duplicate_measurements = int(
            dataframe.duplicated(
                subset=["measurement_id"]
            ).sum()
        )

        invalid_values = int(
            (
                dataframe["value"].isna()
                |
                ~pd.to_numeric(
                    dataframe["value"],
                    errors="coerce",
                ).notna()
            ).sum()
        )

        invalid_timestamps = int(
            dataframe["timestamp"]
            .isna()
            .sum()
        )

        quality_distribution = (
            dataframe["quality"]
            .value_counts(dropna=False)
            .to_dict()
        )

        return {
            "row_count": len(dataframe),
            "missing_values": missing_values,
            "duplicate_measurements": duplicate_measurements,
            "invalid_values": invalid_values,
            "invalid_timestamps": invalid_timestamps,
            "quality_distribution": quality_distribution,
        }