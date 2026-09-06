import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str | None
    target_type: str | None
    target_id: uuid.UUID | None
    read_at: datetime | None
    dismissed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
