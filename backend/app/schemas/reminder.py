import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PendingReminderOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    member_name: str
    member_email: str
    challenge_id: uuid.UUID
    challenge_title: str
    milestone: str
    status: str
    subject: str | None
    body: str | None
    error_detail: str | None
    created_at: datetime
    sent_at: datetime | None


class ReminderUpdate(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
