import pandas as pd

from app.data_pipeline.cleaner import MeasurementDataCleaner
from app.data_pipeline.duplicate_detector import DuplicateMeasurementDetector
from app.data_pipeline.outlier_detector import MeasurementOutlierDetector
from app.data_pipeline.quality_filter import MeasurementQualityFilter


class MeasurementCleaningReport:

    def __init__(self):
        self.cleaner = MeasurementDataCleaner()
        self.quality_filter = MeasurementQualityFilter()
        self.duplicate_detector = DuplicateMeasurementDetector()
        self.outlier_detector = MeasurementOutlierDetector()

    def build(
        self,
        dataframe: pd.DataFrame,
        *,
        include_warnings: bool = True,
        remove_duplicate_measurement_ids: bool = True,
        remove_duplicate_sensor_timestamps: bool = True,
        remove_outliers: bool = False,
        iqr_multiplier: float = 1.5,
    ) -> dict:

        initial_count = len(dataframe)

        classified = self.quality_filter.classify(
            dataframe
        )

        invalid_quality_count = int(
            (
                classified["data_quality_status"]
                == "invalid"
            ).sum()
        ) if not classified.empty else 0

        duplicate_summary = (
            self.duplicate_detector.summarize(
                dataframe
            )
        )

        outlier_summary = (
            self.outlier_detector.summarize(
                dataframe,
                iqr_multiplier=iqr_multiplier,
            )
        )

        cleaned = self.cleaner.clean(
            dataframe,
            include_warnings=include_warnings,
            remove_duplicate_measurement_ids=remove_duplicate_measurement_ids,
            remove_duplicate_sensor_timestamps=remove_duplicate_sensor_timestamps,
            remove_outliers=remove_outliers,
            iqr_multiplier=iqr_multiplier,
        )

        final_count = len(cleaned)

        return {
            "initial_row_count": initial_count,
            "final_row_count": final_count,
            "removed_row_count": initial_count - final_count,
            "invalid_quality_count": invalid_quality_count,
            "duplicate_measurement_id_count": duplicate_summary[
                "duplicate_measurement_id_count"
            ],
            "duplicate_sensor_timestamp_count": duplicate_summary[
                "duplicate_sensor_timestamp_count"
            ],
            "outlier_count": outlier_summary[
                "outlier_count"
            ],
        }