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


@dataclass
class ChallengeSearchResult:
    """§1 — one match from searching a platform's challenges by name.
    `url` is the canonical webpage URL when the platform's API provides
    one — never constructed from the ID unless the platform documents
    that URL scheme (REQUIRED_FEATURES.md §1)."""

    external_challenge_id: str
    title: str | None
    category: str | None
    language: str | None
    url: str | None


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

    @abstractmethod
    def search_challenges(self, title: str) -> list[ChallengeSearchResult]:
        """§1 — every challenge whose title matches `title` (platform-
        defined match rules — exact, substring, or fuzzy), so the Lab
        Leader can pick the right one instead of needing its numeric ID
        up front. Returns an empty list for no matches, never raises for
        that case specifically."""
