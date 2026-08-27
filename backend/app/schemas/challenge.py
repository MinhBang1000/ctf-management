import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChallengeCreate(BaseModel):
    semester_id: uuid.UUID
    platform_id: uuid.UUID
    week_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    category: str | None = None
    difficulty: str | None = None
    external_challenge_id: str | None = None
    presenter_id: uuid.UUID | None = None
    deadline_at: datetime
    points: int | None = None


class ChallengeUpdate(BaseModel):
    semester_id: uuid.UUID | None = None
    platform_id: uuid.UUID | None = None
    week_number: int | None = Field(default=None, ge=1)
    title: str | None = None
    category: str | None = None
    difficulty: str | None = None
    external_challenge_id: str | None = None
    presenter_id: uuid.UUID | None = None
    deadline_at: datetime | None = None
    points: int | None = None


class ChallengeOut(BaseModel):
    id: uuid.UUID
    semester_id: uuid.UUID
    platform_id: uuid.UUID
    week_number: int
    title: str
    category: str | None
    difficulty: str | None
    external_challenge_id: str | None
    presenter_id: uuid.UUID | None
    deadline_at: datetime
    points: int | None

    model_config = {"from_attributes": True}
