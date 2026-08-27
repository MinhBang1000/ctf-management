import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from app.adapters.base import (
    AdapterAuthError,
    AdapterError,
    AdapterNotFoundError,
    ChallengeDetail,
    PlatformAdapter,
    ValidationEntry,
)
from app.core.config import settings
from app.core.rate_limiter import RateLimitTimeoutError, RedisTokenBucket, get_rootme_rate_limiter

DEFAULT_BASE_URL = "https://api.www.root-me.org"

# CONFIRMED (2026-08-25, live API, not a guess): Root Me returns
# "YYYY-MM-DD HH:MM:SS" with no timezone marker, and it is Europe/Paris
# LOCAL time (CET/CEST), not UTC. Proof: fetched GET /challenges/5 at
# server time 09:42:23 UTC (per the HTTP response's own Date header) and
# its validations[] list included entries timestamped up to 10:53:56 —
# i.e. dated ~71 minutes AFTER the request, which is only possible if the
# displayed timestamp already carries a positive UTC offset (a solve
# cannot be recorded in the future). Multiple entries showed the same
# pattern, and the offset is bounded consistent with CEST (UTC+2, in
# effect for France in August). Using zoneinfo (not a fixed +2h) so this
# converts correctly year-round across the CET/CEST DST boundary.
ROOTME_TZ = ZoneInfo("Europe/Paris")


def _parse_rootme_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    # Convert on ingest, not at comparison time — every ValidationEntry
    # leaving this adapter is already UTC-aware, so nothing downstream
    # (classify_status, reminder scheduling) needs to know Root Me's
    # timezone quirk exists at all.
    return naive.replace(tzinfo=ROOTME_TZ).astimezone(timezone.utc)


class RootMeAdapter(PlatformAdapter):
    """PRD §4.2 — confirmed via real API testing (2026-08-24):
    - Auth is a cookie named "api_key", not a query param or header.
    - One api_key can fetch ANY user's public data (verified against
      /auteurs/1) — no per-member key storage needed.
    - GET /auteurs/{id_auteur} returns validations[] with real
      "date": "YYYY-MM-DD HH:MM:SS" per solved challenge — this is what
      get_user_completed_challenges reads, NOT the dateless challenges[].

    /auteurs?nom= (search) and /challenges/{id} (detail) were NOT covered
    by that real testing — parsed defensively here against the documented
    API shape and worth a live smoke-test once a real api_key is in use.

    Root Me rate-limits by IP, not by api_key (PRD §4.2), and this server
    can run many tenants' syncs concurrently — every request acquires a
    slot from the shared Redis-backed token bucket (app/core/rate_limiter)
    BEFORE hitting the network, whether this call came from the manual
    /sync-now endpoint or a scheduled Celery task (Phase 3). A 429 that
    still gets through despite that is handled with local backoff/retry
    on top, as a second line of defense.
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        rate_limiter: RedisTokenBucket | None = None,
    ):
        if not api_key:
            raise AdapterAuthError("Root Me platform has no api_key configured")
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._rate_limiter = rate_limiter or get_rootme_rate_limiter()

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                self._rate_limiter.acquire(timeout=settings.RATE_LIMIT_ACQUIRE_TIMEOUT_SECONDS)
            except RateLimitTimeoutError as exc:
                raise AdapterError(f"Root Me rate limiter: {exc}") from exc

            try:
                resp = httpx.get(
                    url,
                    params=params,
                    cookies={"api_key": self.api_key},
                    timeout=10,
                )
            except httpx.RequestError as exc:
                last_error = exc
                time.sleep(self._backoff_seconds(attempt))
                continue

            if resp.status_code == 429:
                time.sleep(self._retry_after_seconds(resp) or self._backoff_seconds(attempt))
                continue
            if resp.status_code == 401:
                raise AdapterAuthError("Root Me rejected the configured api_key")
            if resp.status_code == 404:
                raise AdapterNotFoundError(f"Root Me: {path} not found")
            if resp.status_code >= 400:
                raise AdapterError(f"Root Me API error {resp.status_code} on {path}: {resp.text[:200]}")

            try:
                return resp.json()
            except ValueError as exc:
                raise AdapterError(f"Root Me API returned non-JSON response for {path}") from exc

        raise AdapterError(f"Root Me API unreachable after {self.MAX_RETRIES} attempts on {path}: {last_error}")

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        return min(2**attempt, 8)

    @staticmethod
    def _retry_after_seconds(resp: httpx.Response) -> float | None:
        value = resp.headers.get("Retry-After")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def resolve_user(self, username: str) -> str | None:
        # CONFIRMED (Phase 6 smoke test, real key): /auteurs?nom= responds
        # [{"0": {"id_auteur":..., "nom":...}, "1": {...}, ...}] — a list
        # wrapping ONE object whose keys are numeric-string indices, not a
        # flat list of author objects. This is inconsistent with
        # /auteurs/{id}'s validations[] (a genuine array) — Root Me's API
        # shapes don't generalize across endpoints, each needs its own
        # verification rather than assuming a shared convention.
        #
        # ALSO CONFIRMED: a search with zero matches returns HTTP 404, not
        # an empty list/200 — that's a normal "no such username" outcome
        # for this lookup helper, not an adapter/system error, so it's
        # translated to None rather than propagating as AdapterNotFoundError.
        try:
            data = self._get("/auteurs", params={"nom": username})
        except AdapterNotFoundError:
            return None
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            return None
        for entry in data.values():
            if isinstance(entry, dict) and str(entry.get("nom", "")).lower() == username.lower():
                id_auteur = entry.get("id_auteur")
                if id_auteur is not None:
                    return str(id_auteur)
        return None

    def get_user_completed_challenges(self, external_user_id: str) -> list[ValidationEntry]:
        data = self._get(f"/auteurs/{external_user_id}")
        if isinstance(data, list):
            data = data[0] if data else {}
        validations = data.get("validations") or []

        result = []
        for v in validations:
            if not isinstance(v, dict) or v.get("id_challenge") is None:
                continue
            result.append(
                ValidationEntry(
                    id_challenge=str(v["id_challenge"]),
                    title=v.get("titre"),
                    category_id=v.get("id_rubrique"),
                    completed_at=_parse_rootme_datetime(v.get("date")),
                )
            )
        return result

    def get_challenge_detail(self, external_challenge_id: str) -> ChallengeDetail:
        data = self._get(f"/challenges/{external_challenge_id}")
        if isinstance(data, list):
            data = data[0] if data else {}
        score = data.get("score")
        try:
            score = int(score) if score is not None else None
        except (TypeError, ValueError):
            score = None
        return ChallengeDetail(
            title=data.get("titre"),
            category=data.get("rubrique"),
            score=score,
        )
