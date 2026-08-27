import uuid

from pydantic import BaseModel, Field


class PlatformCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    adapter_type: str = "rootme"
    base_url: str | None = None
    # e.g. {"api_key": "..."} for the Root Me adapter. Encrypted at rest,
    # never echoed back by any endpoint.
    auth_config: dict | None = None


class PlatformUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    auth_config: dict | None = None
    is_active: bool | None = None


class PlatformOut(BaseModel):
    id: uuid.UUID
    name: str
    adapter_type: str
    base_url: str | None
    is_focus: bool
    is_active: bool
    has_credentials: bool

    model_config = {"from_attributes": True}


class TestConnectionResult(BaseModel):
    ok: bool
    detail: str


class ResolveUserResult(BaseModel):
    external_user_id: str | None
    matched: bool


class ChallengeLookupResult(BaseModel):
    title: str | None
    category: str | None
    score: int | None


class SyncNowResult(BaseModel):
    members_checked: int
    updated: list[dict]
    conflicts: list[dict]
    errors: list[str]
