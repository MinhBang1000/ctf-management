import uuid
from datetime import date

from pydantic import BaseModel, Field


class SemesterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    is_current: bool = False


class SemesterUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None


class SemesterOut(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    is_current: bool

    model_config = {"from_attributes": True}
