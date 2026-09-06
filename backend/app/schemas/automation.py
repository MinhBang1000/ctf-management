import uuid
from datetime import datetime

from pydantic import BaseModel


class SyncRunOut(BaseModel):
    id: uuid.UUID
    platform_id: uuid.UUID
    platform_name: str
    run_at: datetime
    status: str
    members_checked: int
    updated_count: int
    conflicts_count: int
    errors: str | None


class JobRunOut(BaseModel):
    id: uuid.UUID
    job_type: str
    run_at: datetime
    status: str
    detail: str | None

    model_config = {"from_attributes": True}


class RetryJobRequest(BaseModel):
    job_type: str  # "sync" | "reminder" | "weekly_report"


class SystemJobRunOut(BaseModel):
    id: uuid.UUID
    job_type: str
    run_at: datetime
    status: str
    detail: str | None

    model_config = {"from_attributes": True}
