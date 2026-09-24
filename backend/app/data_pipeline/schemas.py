from datetime import datetime

from pydantic import BaseModel


class MeasurementDataRow(BaseModel):
    measurement_id: int
    timestamp: datetime
    value: float
    quality: str

    sensor_id: int
    sensor_code: str
    sensor_type: str
    sensor_unit: str
    sensor_status: str

    equipment_id: int
    equipment_code: str
    equipment_type: str
    equipment_status: str
    equipment_criticality: str

    site_id: int
    site_code: str

    company_id: int
    company_code: str