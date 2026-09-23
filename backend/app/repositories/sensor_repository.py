from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.sensor import Sensor


class SensorRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[Sensor]:
        statement = select(Sensor).order_by(Sensor.id.asc())

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def get_by_id(self, sensor_id: int) -> Sensor | None:
        statement = select(Sensor).where(
            Sensor.id == sensor_id
        )

        return self.db.execute(
            statement
        ).scalar_one_or_none()

    def get_by_equipment_id(
        self,
        equipment_id: int,
    ) -> list[Sensor]:
        statement = (
            select(Sensor)
            .where(
                Sensor.equipment_id == equipment_id
            )
            .order_by(Sensor.id.asc())
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def get_paginated(
        self,
        *,
        offset: int,
        limit: int,
        equipment_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> list[Sensor]:
        statement = select(Sensor)

        if equipment_id is not None:
            statement = statement.where(
                Sensor.equipment_id == equipment_id
            )

        if status is not None:
            statement = statement.where(
                Sensor.status == status
            )

        if search:
            pattern = f"%{search.strip()}%"

            statement = statement.where(
                or_(
                    Sensor.name.ilike(pattern),
                    Sensor.code.ilike(pattern),
                    Sensor.sensor_type.ilike(pattern),
                    Sensor.unit.ilike(pattern),
                )
            )

        statement = (
            statement
            .order_by(Sensor.id.asc())
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
        equipment_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> int:
        statement = select(
            func.count(Sensor.id)
        )

        if equipment_id is not None:
            statement = statement.where(
                Sensor.equipment_id == equipment_id
            )

        if status is not None:
            statement = statement.where(
                Sensor.status == status
            )

        if search:
            pattern = f"%{search.strip()}%"

            statement = statement.where(
                or_(
                    Sensor.name.ilike(pattern),
                    Sensor.code.ilike(pattern),
                    Sensor.sensor_type.ilike(pattern),
                    Sensor.unit.ilike(pattern),
                )
            )

        return self.db.execute(
            statement
        ).scalar_one()

    def create(self, sensor: Sensor) -> Sensor:
        self.db.add(sensor)
        self.db.commit()
        self.db.refresh(sensor)

        return sensor

    def update(self, sensor: Sensor) -> Sensor:
        self.db.commit()
        self.db.refresh(sensor)

        return sensor

    def delete(self, sensor: Sensor) -> None:
        self.db.delete(sensor)
        self.db.commit()