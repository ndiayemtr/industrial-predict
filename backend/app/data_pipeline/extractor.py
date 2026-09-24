from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data_pipeline.schemas import MeasurementDataRow
from app.models.company import Company
from app.models.equipment import Equipment
from app.models.measurement import Measurement
from app.models.sensor import Sensor
from app.models.site import Site


class MeasurementDataExtractor:

    def __init__(self, db: Session):
        self.db = db

    def extract(
        self,
        *,
        company_id: int | None = None,
        site_id: int | None = None,
        equipment_id: int | None = None,
        sensor_id: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[MeasurementDataRow]:

        statement = (
            select(
                Measurement,
                Sensor,
                Equipment,
                Site,
                Company,
            )
            .join(
                Sensor,
                Measurement.sensor_id == Sensor.id,
            )
            .join(
                Equipment,
                Sensor.equipment_id == Equipment.id,
            )
            .join(
                Site,
                Equipment.site_id == Site.id,
            )
            .join(
                Company,
                Site.company_id == Company.id,
            )
        )

        if company_id is not None:
            statement = statement.where(
                Company.id == company_id
            )

        if site_id is not None:
            statement = statement.where(
                Site.id == site_id
            )

        if equipment_id is not None:
            statement = statement.where(
                Equipment.id == equipment_id
            )

        if sensor_id is not None:
            statement = statement.where(
                Sensor.id == sensor_id
            )

        if start_time is not None:
            statement = statement.where(
                Measurement.timestamp >= start_time
            )

        if end_time is not None:
            statement = statement.where(
                Measurement.timestamp < end_time
            )

        statement = statement.order_by(
            Measurement.timestamp.asc(),
            Measurement.id.asc(),
        )

        rows = self.db.execute(statement).all()

        return [
            MeasurementDataRow(
                measurement_id=measurement.id,
                timestamp=measurement.timestamp,
                value=measurement.value,
                quality=measurement.quality,

                sensor_id=sensor.id,
                sensor_code=sensor.code,
                sensor_type=sensor.sensor_type,
                sensor_unit=sensor.unit,
                sensor_status=sensor.status,

                equipment_id=equipment.id,
                equipment_code=equipment.code,
                equipment_type=equipment.equipment_type,
                equipment_status=equipment.status,
                equipment_criticality=equipment.criticality,

                site_id=site.id,
                site_code=site.code,

                company_id=company.id,
                company_code=company.code,
            )
            for (
                measurement,
                sensor,
                equipment,
                site,
                company,
            ) in rows
        ]