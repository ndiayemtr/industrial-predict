from datetime import datetime

from sqlalchemy.orm import Session

from app.core.pagination import build_page

from app.models.measurement import Measurement
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.sensor_repository import SensorRepository
from app.schemas.measurement import MeasurementCreate, MeasurementUpdate


class MeasurementService:

    def __init__(self, db: Session):
        self.repository = MeasurementRepository(db)
        self.sensor_repository = SensorRepository(db)
        self.db = db

    def get_paginated(
        self,
        *,
        page: int,
        page_size: int,
    ):
        offset = (page - 1) * page_size

        items = self.repository.get_paginated(
            offset=offset,
            limit=page_size,
        )

        total = self.repository.count_all()

        return build_page(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_all(self) -> list[Measurement]:
        return self.repository.get_all()

    def get_by_id(self, measurement_id: int) -> Measurement | None:
        return self.repository.get_by_id(measurement_id)

    def get_by_sensor_id(self, sensor_id: int) -> list[Measurement]:
        sensor = self.sensor_repository.get_by_id(sensor_id)

        if not sensor:
            raise ValueError("Sensor not found")

        return self.repository.get_by_sensor_id(sensor_id)

    def get_by_sensor_and_period(
        self,
        sensor_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[Measurement]:

        sensor = self.sensor_repository.get_by_id(sensor_id)

        if not sensor:
            raise ValueError("Sensor not found")

        if start_time > end_time:
            raise ValueError(
                "start_time must be before or equal to end_time"
            )

        return self.repository.get_by_sensor_and_period(
            sensor_id,
            start_time,
            end_time,
        )

    def create(
        self,
        data: MeasurementCreate,
    ) -> Measurement:

        sensor = self.sensor_repository.get_by_id(data.sensor_id)

        if not sensor:
            raise ValueError("Sensor not found")

        measurement = Measurement(
            sensor_id=data.sensor_id,
            timestamp=data.timestamp,
            value=data.value,
            quality=data.quality,
        )

        measurement = self.repository.create(measurement)

        self.db.commit()
        self.db.refresh(measurement)

        return measurement

    def update(
        self,
        measurement: Measurement,
        data: MeasurementUpdate,
    ) -> Measurement:

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(measurement, field, value)

        measurement = self.repository.update(measurement)

        self.db.commit()
        self.db.refresh(measurement)

        return measurement

    def delete(
        self,
        measurement: Measurement,
    ) -> None:

        self.repository.delete(measurement)

        self.db.commit()
