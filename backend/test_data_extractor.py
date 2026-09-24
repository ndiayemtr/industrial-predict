from app.core.database import SessionLocal
from app.data_pipeline.dataset_builder import MeasurementDatasetBuilder
from app.data_pipeline.extractor import MeasurementDataExtractor
from app.data_pipeline.data_quality import DataQualityReport
from app.data_pipeline.time_series import TimeSeriesPreparer
from app.data_pipeline.window_features import WindowFeatureBuilder


db = SessionLocal()

try:
    extractor = MeasurementDataExtractor(db)
    builder = MeasurementDatasetBuilder()

    rows = extractor.extract()

    dataframe = builder.build(rows)
    
    quality_report = DataQualityReport()

    report = quality_report.analyze(dataframe)
    
    time_series_preparer = TimeSeriesPreparer()

    prepared_dataframe = time_series_preparer.prepare(
        dataframe
    )

    time_series_profile = time_series_preparer.profile(
        prepared_dataframe
    )
    
    window_builder = WindowFeatureBuilder()

    featured_dataframe = window_builder.build(
        prepared_dataframe,
        window_size=3,
    )

    print("\nFeatures temporelles :")
    print(
        featured_dataframe[
            [
                "measurement_id",
                "sensor_id",
                "timestamp",
                "value",
                "rolling_mean",
                "rolling_min",
                "rolling_max",
                "rolling_std",
                "rolling_count",
                "value_delta",
            ]
        ]
    )

    print("\nDataset temporel :")
    print(
        prepared_dataframe[
            [
                "measurement_id",
                "sensor_id",
                "timestamp",
                "value",
                "time_delta_seconds",
            ]
        ]
    )

    print("\nProfil temporel :")
    print(time_series_profile)

    print("\nRapport qualité :")
    print(report)

    print("\nDataset :")
    print(dataframe)

    print("\nShape :")
    print(dataframe.shape)

    print("\nColonnes :")
    print(dataframe.columns.tolist())

    print("\nTypes :")
    print(dataframe.dtypes)

finally:
    db.close()