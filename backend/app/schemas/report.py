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

    model_config = {"from_attributes": True}


class ReportUpdate(BaseModel):
    content: str


class ApproveReportRequest(BaseModel):
    to_address: EmailStr
