from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sensor import Sensor


class SensorRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_paginated(
        self,
        *,
        offset: int,
        limit: int,
    ) -> list[Sensor]:
        statement = (
            select(Sensor)
            .order_by(Sensor.id.asc())
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def count_all(self) -> int:
        statement = select(func.count(Sensor.id))
        return self.db.execute(statement).scalar_one()

    def get_all(self) -> list[Sensor]:
        statement = select(Sensor).order_by(Sensor.id)
        return list(self.db.scalars(statement).all())

    def get_by_id(self, sensor_id: int) -> Sensor | None:
        statement = select(Sensor).where(
            Sensor.id == sensor_id
        )
        return self.db.scalar(statement)

    def get_by_code(self, code: str) -> Sensor | None:
        statement = select(Sensor).where(
            Sensor.code == code
        )
        return self.db.scalar(statement)

    def get_by_equipment_id(self, equipment_id: int) -> list[Sensor]:
        statement = (
            select(Sensor)
            .where(Sensor.equipment_id == equipment_id)
            .order_by(Sensor.id)
        )
        return list(self.db.scalars(statement).all())

    def create(self, sensor: Sensor) -> Sensor:
        self.db.add(sensor)
        self.db.flush()
        self.db.refresh(sensor)
        return sensor

    def update(self, sensor: Sensor) -> Sensor:
        self.db.flush()
        self.db.refresh(sensor)
        return sensor

    def delete(self, sensor: Sensor) -> None:
        self.db.delete(sensor)
        self.db.flush()
