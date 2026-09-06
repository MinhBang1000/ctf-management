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


class DeletionPreview(BaseModel):
    """§16 — "Show the affected data before deletion.\""""

    tenant_name: str
    member_count: int
    semester_count: int
    challenge_count: int
    progress_count: int
    report_count: int
    platform_count: int


class DeleteLabRequest(BaseModel):
    # §16 — "Require explicit confirmation using the Lab name" as a real
    # field the API itself checks, not just a frontend dialog.
    confirm_name: str


class AssignLeaderRequest(BaseModel):
    # §15 — "the Super Admin directly promotes/adds a new Lab Leader for
    # that Lab from the Console" when none is left. Creates a brand-new
    # account rather than promoting an existing Member: Members has no
    # general Super-Admin SELECT bypass (deliberate no-impersonation
    # design), so this stays a narrow INSERT-only action instead of
    # widening that boundary just to populate a "pick a member" dropdown.
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)


class RestoreBundleRequest(BaseModel):
    bundle: dict
    mode: str  # "new_lab" | "overwrite_existing"
    target_tenant_id: uuid.UUID | None = None


class RestoreResult(BaseModel):
    tenant_id: uuid.UUID
    warnings: list[str]


class TenantDataJobOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    job_type: str
    status: str
    format_version: str
    requested_by_email: str
    downloaded_at: datetime | None
    error_detail: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
