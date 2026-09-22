from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import (
    EquipmentCriticality,
    EquipmentStatus,
)


class EquipmentBase(BaseModel):
    name: str
    code: str
    equipment_type: str
    description: str | None = None
    status: EquipmentStatus = EquipmentStatus.OPERATIONAL
    criticality: EquipmentCriticality = EquipmentCriticality.MEDIUM


class EquipmentCreate(EquipmentBase):
    site_id: int


class EquipmentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    equipment_type: str | None = None
    description: str | None = None
    status: EquipmentStatus | None = None
    criticality: EquipmentCriticality | None = None
    site_id: int | None = None


class EquipmentRead(EquipmentBase):
    id: int
    site_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)