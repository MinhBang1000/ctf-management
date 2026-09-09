import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class FeedbackOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    member_email: str
    member_role: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
