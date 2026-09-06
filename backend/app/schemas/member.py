import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.member import MemberRole


class PlatformAccountIn(BaseModel):
    platform_id: uuid.UUID
    external_username: str = Field(min_length=1, max_length=255)
    # Root Me id_auteur. Required, NOT auto-derived from the username —
    # PRD §6.3 / ERD note in §5: must be typed/confirmed by the Admin.
    external_user_id: str = Field(min_length=1, max_length=64)


class PlatformAccountOut(PlatformAccountIn):
    id: uuid.UUID

    model_config = {"from_attributes": True}


class MemberCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)
    role: MemberRole = MemberRole.MEMBER
    platform_accounts: list[PlatformAccountIn] = []


class MemberUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role: MemberRole | None = None
    active: bool | None = None


class MemberResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class TransferOwnershipRequest(BaseModel):
    # §15 — explicit confirmation as a real field (not just a frontend
    # confirm() dialog), same pattern as ResendReportRequest.confirm.
    confirm: bool = False
    # None = stay a co-Lab-Leader alongside the newly-promoted one;
    # otherwise the initiator steps down to this role once the promotion
    # has happened (always safe by then — see assert_not_last_lab_leader).
    demote_self_to: MemberRole | None = None




class MemberOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: MemberRole
    active: bool
    joined_at: datetime
    platform_accounts: list[PlatformAccountOut] = []

    model_config = {"from_attributes": True}
