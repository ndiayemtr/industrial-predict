from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SiteBase(BaseModel):
    name: str
    code: str
    description: str | None = None


class SiteCreate(SiteBase):
    company_id: int


class SiteUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    company_id: int | None = None


class SiteRead(SiteBase):
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)