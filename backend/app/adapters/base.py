from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class AdapterError(Exception):
    """Any failure talking to a platform's API (auth, not found, network,
    exhausted retries, unrecognized response shape)."""


class AdapterAuthError(AdapterError):
    """The configured credentials were rejected (e.g. bad api_key)."""


class AdapterNotFoundError(AdapterError):
    """The requested user/challenge doesn't exist on the platform."""


@dataclass
class ValidationEntry:
    """One challenge a user has solved, per the platform's own record of
    when it happened. For Root Me this comes from validations[], keyed by
    id_challenge, with a real completion timestamp — see PRD §4.2."""

    id_challenge: str
    title: str | None
    category_id: str | None
    completed_at: datetime | None


@dataclass
class ChallengeDetail:
    title: str | None
    category: str | None
    score: int | None


class PlatformAdapter(ABC):
    """PRD §3.2 — the abstraction every CTF platform integration implements.
    RootMeAdapter is the first implementation; nothing here is Root Me-specific."""

    @abstractmethod
    def resolve_user(self, username: str) -> str | None:
        """Look up a platform user's stable external_user_id from their
        (mutable) username. Returns None if no exact match is found —
        callers must never silently guess."""

    @abstractmethod
    def get_user_completed_challenges(self, external_user_id: str) -> list[ValidationEntry]:
        """All challenges this user has validated, with real completion
        timestamps where the platform provides them."""

    @abstractmethod
    def get_challenge_detail(self, external_challenge_id: str) -> ChallengeDetail:
        """Metadata for one challenge, used to prefill Challenge forms."""
