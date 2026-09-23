from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.measurement import Measurement


class MeasurementRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_paginated(
        self,
        *,
        offset: int,
        limit: int,
    ) -> list[Measurement]:
        statement = (
            select(Measurement)
            .order_by(Measurement.timestamp.desc(), Measurement.id.desc())
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def count_all(self) -> int:
        statement = select(func.count(Measurement.id))
        return self.db.execute(statement).scalar_one()

    def get_all(self) -> list[Measurement]:
        statement = (
            select(Measurement)
            .order_by(Measurement.timestamp.desc())
        )

        return list(self.db.scalars(statement).all())

    def get_by_id(
        self,
        measurement_id: int,
    ) -> Measurement | None:
        statement = select(Measurement).where(
            Measurement.id == measurement_id
        )

        return self.db.scalar(statement)

    def get_by_sensor_id(
        self,
        sensor_id: int,
    ) -> list[Measurement]:
        statement = (
            select(Measurement)
            .where(Measurement.sensor_id == sensor_id)
            .order_by(Measurement.timestamp.desc())
        )

        return list(self.db.scalars(statement).all())

    def get_by_sensor_and_period(
        self,
        sensor_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[Measurement]:
        statement = (
            select(Measurement)
            .where(
                Measurement.sensor_id == sensor_id,
                Measurement.timestamp >= start_time,
                Measurement.timestamp <= end_time,
            )
            .order_by(Measurement.timestamp)
        )

        return list(self.db.scalars(statement).all())

    def create(
        self,
        measurement: Measurement,
    ) -> Measurement:
        self.db.add(measurement)
        self.db.flush()
        self.db.refresh(measurement)

        return measurement

    def update(
        self,
        measurement: Measurement,
    ) -> Measurement:
        self.db.flush()
        self.db.refresh(measurement)

        return measurement

    def delete(
        self,
        measurement: Measurement,
    ) -> None:
        self.db.delete(measurement)
        self.db.flush()
