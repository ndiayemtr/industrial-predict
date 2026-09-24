import pandas as pd

from app.data_pipeline.quality_rules import (
    DataQualityStatus,
    MeasurementQualityPolicy,
)


class MeasurementQualityFilter:

    def classify(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            result = dataframe.copy()
            result["data_quality_status"] = pd.Series(dtype="str")
            return result

        result = dataframe.copy()

        result["data_quality_status"] = (
            result["quality"]
            .apply(
                MeasurementQualityPolicy.classify_quality
            )
            .astype(str)
        )

        return result

    def filter_usable(
        self,
        dataframe: pd.DataFrame,
        *,
        include_warnings: bool = True,
    ) -> pd.DataFrame:

        classified = self.classify(dataframe)

        if classified.empty:
            return classified

        accepted_statuses = {
            DataQualityStatus.VALID.value,
        }

        if include_warnings:
            accepted_statuses.add(
                DataQualityStatus.WARNING.value
            )

        return (
            classified[
                classified["data_quality_status"].isin(
                    accepted_statuses
                )
            ]
            .reset_index(drop=True)
        )