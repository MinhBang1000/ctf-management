import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# §1 — "Validate that the value is a valid https URL before saving it."
# Not required to be root-me.org (the Lab Leader can enter/correct a URL
# manually when the API doesn't provide one) — the "prefer official
# root-me.org, warn before accepting an external domain" half of the
# rule is a frontend confirmation-prompt concern (IS_OFFICIAL_ROOTME_HOST
# below lets the frontend/tests share the exact same check), not a hard
# backend rejection of non-root-me.org URLs.
OFFICIAL_ROOTME_HOST = "www.root-me.org"


def is_official_rootme_url(url: str) -> bool:
    return url.startswith(f"https://{OFFICIAL_ROOTME_HOST}/")


def _validate_https_url(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not value.startswith("https://"):
        raise ValueError("Challenge URL must start with https://")
    return value


class ChallengeCreate(BaseModel):
    semester_id: uuid.UUID
    platform_id: uuid.UUID
    week_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    category: str | None = None
    difficulty: str | None = None
    external_challenge_id: str | None = None
    external_url: str | None = Field(default=None, max_length=500)
    presenter_id: uuid.UUID | None = None
    deadline_at: datetime
    points: int | None = None

    _validate_external_url = field_validator("external_url")(_validate_https_url)


class ChallengeUpdate(BaseModel):
    semester_id: uuid.UUID | None = None
    platform_id: uuid.UUID | None = None
    week_number: int | None = Field(default=None, ge=1)
    title: str | None = None
    category: str | None = None
    difficulty: str | None = None
    external_challenge_id: str | None = None
    external_url: str | None = Field(default=None, max_length=500)
    presenter_id: uuid.UUID | None = None
    deadline_at: datetime | None = None
    points: int | None = None

    _validate_external_url = field_validator("external_url")(_validate_https_url)


class ChallengeOut(BaseModel):
    id: uuid.UUID
    semester_id: uuid.UUID
    platform_id: uuid.UUID
    week_number: int
    title: str
    category: str | None
    difficulty: str | None
    external_challenge_id: str | None
    external_url: str | None
    presenter_id: uuid.UUID | None
    deadline_at: datetime
    points: int | None

    model_config = {"from_attributes": True}
