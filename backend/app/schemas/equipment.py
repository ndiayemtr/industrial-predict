from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EquipmentBase(BaseModel):
    name: str
    code: str
    equipment_type: str
    description: str | None = None
    status: str = "operational"
    criticality: str = "medium"


class EquipmentCreate(EquipmentBase):
    site_id: int


class EquipmentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    equipment_type: str | None = None
    description: str | None = None
    status: str | None = None
    criticality: str | None = None
    site_id: int | None = None


class EquipmentRead(EquipmentBase):
    id: int
    site_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)