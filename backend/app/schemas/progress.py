import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.progress import DetectedBy, ProgressStatus


class ProgressUpsert(BaseModel):
    member_id: uuid.UUID
    challenge_id: uuid.UUID
    status: ProgressStatus
    completed_at: datetime | None = None
    note: str | None = None


class ProgressOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    challenge_id: uuid.UUID
    status: ProgressStatus
    completed_at: datetime | None
    detected_by: DetectedBy
    note: str | None

    model_config = {"from_attributes": True}
