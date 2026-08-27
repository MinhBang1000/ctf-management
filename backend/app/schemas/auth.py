import uuid

from pydantic import BaseModel, EmailStr

from app.models.member import MemberRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MemberMe(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    full_name: str
    email: EmailStr
    role: MemberRole

    model_config = {"from_attributes": True}


class SuperAdminMe(BaseModel):
    id: uuid.UUID
    email: EmailStr

    model_config = {"from_attributes": True}
