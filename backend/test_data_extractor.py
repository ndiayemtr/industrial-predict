from app.core.database import SessionLocal
from app.data_pipeline.pipeline import MeasurementDataPipeline


db = SessionLocal()

try:
    pipeline = MeasurementDataPipeline(db)

    dataframe = pipeline.build(
        window_size=3,
    )

    print("\nDataset final :")
    print(dataframe)

    print("\nShape :")
    print(dataframe.shape)

    print("\nColonnes :")
    print(dataframe.columns.tolist())

    print("\nRapport qualité :")
    print(
        pipeline.analyze_quality(
            dataframe
        )
    )

    print("\nProfil temporel :")
    print(
        pipeline.profile_time_series(
            dataframe
        )
    )

finally:
    db.close()