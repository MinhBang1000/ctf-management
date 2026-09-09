import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    actor_type: str
    actor_label: str
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    summary: str
    created_at: datetime

    model_config = {"from_attributes": True}
