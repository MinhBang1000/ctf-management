import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    # First Lab Leader account, created together with the Lab (PRD §6.1).
    lab_leader_full_name: str = Field(min_length=1, max_length=255)
    lab_leader_email: EmailStr
    lab_leader_password: str = Field(min_length=8)


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantUpdate(BaseModel):
    is_active: bool
