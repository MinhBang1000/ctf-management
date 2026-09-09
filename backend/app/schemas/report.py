import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr


class ReportOut(BaseModel):
    id: uuid.UUID
    type: str
    period_start: date
    period_end: date
    status: str
    content: str | None
    generated_at: datetime | None
    sent_at: datetime | None
    approved_by: str | None
    # §10 — the recipient the most recent successful send actually used.
    recipient_email: str | None

    model_config = {"from_attributes": True}


class ReportUpdate(BaseModel):
    content: str


class ApproveReportRequest(BaseModel):
    to_address: EmailStr


class ResendReportRequest(BaseModel):
    to_address: EmailStr
    # §11 — "Require explicit confirmation before resending a
    # successfully sent report" as a real field, not just a frontend
    # confirm() dialog, so the API itself refuses an accidental resend.
    confirm: bool = False


class ReportSendAttemptOut(BaseModel):
    id: uuid.UUID
    attempted_at: datetime
    recipient_email: str
    kind: str
    status: str
    error_detail: str | None
    attempted_by_email: str

    model_config = {"from_attributes": True}
