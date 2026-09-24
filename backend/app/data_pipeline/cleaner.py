import pandas as pd

from app.data_pipeline.duplicate_detector import DuplicateMeasurementDetector
from app.data_pipeline.outlier_detector import MeasurementOutlierDetector
from app.data_pipeline.quality_filter import MeasurementQualityFilter


class MeasurementDataCleaner:

    def __init__(self):
        self.quality_filter = MeasurementQualityFilter()
        self.duplicate_detector = DuplicateMeasurementDetector()
        self.outlier_detector = MeasurementOutlierDetector()

    def clean(
        self,
        dataframe: pd.DataFrame,
        *,
        include_warnings: bool = True,
        remove_duplicate_measurement_ids: bool = True,
        remove_duplicate_sensor_timestamps: bool = True,
        remove_outliers: bool = False,
        iqr_multiplier: float = 1.5,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return dataframe.copy()

        result = self.quality_filter.filter_usable(
            dataframe,
            include_warnings=include_warnings,
        )

        if remove_duplicate_measurement_ids:
            result = self.duplicate_detector.detect(result)

            result = result[
                ~result["duplicate_measurement_id"]
            ].copy()

            result = result.drop(
                columns=[
                    "duplicate_measurement_id",
                    "duplicate_sensor_timestamp",
                ],
                errors="ignore",
            )

        if remove_duplicate_sensor_timestamps:
            result = self.duplicate_detector.detect(result)

            result = result[
                ~result["duplicate_sensor_timestamp"]
            ].copy()

        if remove_outliers:
            result = self.outlier_detector.detect(
                result,
                iqr_multiplier=iqr_multiplier,
            )

            result = result[
                ~result["outlier_detected"]
            ].copy()

        return result.reset_index(drop=True)