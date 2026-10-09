from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.prediction_record import PredictionRecord


class PredictionRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        prediction: PredictionRecord,
    ) -> PredictionRecord:

        self.db.add(prediction)
        self.db.flush()
        self.db.refresh(prediction)

        return prediction

    def get_by_id(
        self,
        prediction_id: int,
    ) -> PredictionRecord | None:

        statement = select(
            PredictionRecord
        ).where(
            PredictionRecord.id == prediction_id
        )

        return self.db.scalar(statement)

    def get_by_equipment_id(
        self,
        equipment_id: int,
    ) -> list[PredictionRecord]:

        statement = (
            select(PredictionRecord)
            .where(
                PredictionRecord.equipment_id == equipment_id
            )
            .order_by(
                PredictionRecord.predicted_at.desc(),
                PredictionRecord.id.desc(),
            )
        )

        return list(
            self.db.scalars(statement).all()
        )

    def get_by_equipment_and_type(
        self,
        equipment_id: int,
        prediction_type: str,
    ) -> list[PredictionRecord]:

        statement = (
            select(PredictionRecord)
            .where(
                PredictionRecord.equipment_id == equipment_id,
                PredictionRecord.prediction_type == prediction_type,
            )
            .order_by(
                PredictionRecord.predicted_at.desc(),
                PredictionRecord.id.desc(),
            )
        )

        return list(
            self.db.scalars(statement).all()
        )

    def get_latest_by_equipment_and_type(
        self,
        equipment_id: int,
        prediction_type: str,
    ) -> PredictionRecord | None:

        statement = (
            select(PredictionRecord)
            .where(
                PredictionRecord.equipment_id == equipment_id,
                PredictionRecord.prediction_type == prediction_type,
            )
            .order_by(
                PredictionRecord.predicted_at.desc(),
                PredictionRecord.id.desc(),
            )
            .limit(1)
        )

        return self.db.scalar(statement)

    def get_paginated(
        self,
        *,
        equipment_id: int,
        offset: int,
        limit: int,
        prediction_type: str | None = None,
        level: str | None = None,
        is_alert: bool | None = None,
        start_time=None,
        end_time=None,
    ) -> list[PredictionRecord]:

        statement = select(PredictionRecord).where(
            PredictionRecord.equipment_id == equipment_id
        )

        if prediction_type is not None:
            statement = statement.where(
                PredictionRecord.prediction_type == prediction_type
            )

        if level is not None:
            statement = statement.where(
                PredictionRecord.level == level
            )

        if is_alert is not None:
            statement = statement.where(
                PredictionRecord.is_alert == is_alert
            )

        if start_time is not None:
            statement = statement.where(
                PredictionRecord.predicted_at >= start_time
            )

        if end_time is not None:
            statement = statement.where(
                PredictionRecord.predicted_at <= end_time
            )

        statement = (
            statement
            .order_by(
                PredictionRecord.predicted_at.desc(),
                PredictionRecord.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def count_all(
        self,
        *,
        equipment_id: int,
        prediction_type: str | None = None,
        level: str | None = None,
        is_alert: bool | None = None,
        start_time=None,
        end_time=None,
    ) -> int:

        statement = select(
            func.count(PredictionRecord.id)
        ).where(
            PredictionRecord.equipment_id == equipment_id
        )

        if prediction_type is not None:
            statement = statement.where(
                PredictionRecord.prediction_type == prediction_type
            )

        if level is not None:
            statement = statement.where(
                PredictionRecord.level == level
            )

        if is_alert is not None:
            statement = statement.where(
                PredictionRecord.is_alert == is_alert
            )

        if start_time is not None:
            statement = statement.where(
                PredictionRecord.predicted_at >= start_time
            )

        if end_time is not None:
            statement = statement.where(
                PredictionRecord.predicted_at <= end_time
            )

        return self.db.execute(
            statement
        ).scalar_one()