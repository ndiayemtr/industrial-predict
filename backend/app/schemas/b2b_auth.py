"""Minimal Angular-compatible profile; no tokens or external identity claims."""
from pydantic import BaseModel, ConfigDict, Field
from app.core.authorization import Permission


class AuthorizedCompany(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    companyId: int = Field(gt=0)
    displayName: str | None
    permissions: list[Permission]


class AuthenticatedProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    userId: int = Field(gt=0)
    displayName: str | None
    companies: list[AuthorizedCompany] = Field(min_length=1)
