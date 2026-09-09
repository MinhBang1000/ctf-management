import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.member import MemberRole

# §2 "a consistent password-strength policy...applied to account creation,
# password changes, and password resets" — the only policy ever specified
# anywhere in this codebase (MemberCreate) is a minimum length, so that's
# what's kept consistent everywhere rather than inventing new complexity
# rules nothing else in the product enforces.
PASSWORD_MIN_LENGTH = 8


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH)


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
