"""RootMeAdapter's own JSON-parsing logic, against real response shapes
captured from the live API (2026-09-07, real api_key) — nothing here was
covered before: every other test mocks get_adapter() itself, never
exercising RootMeAdapter._get's parsing at all.

This is regression coverage for two real bugs found live: search_challenges
was reading "rubrique"/"langue" (wrong keys — the search endpoint has
neither; the real keys are "id_rubrique"/"lang") and always silently
returned category=None, language=None, and get_challenge_detail wasn't
extracting the detail endpoint's real "url_challenge" path at all.
"""
from unittest.mock import patch

from app.adapters.rootme import RootMeAdapter


class _NoOpRateLimiter:
    def acquire(self, timeout):
        pass


def _adapter():
    return RootMeAdapter(api_key="test-key", rate_limiter=_NoOpRateLimiter())


class _FakeResponse:
    def __init__(self, status_code, json_body):
        self.status_code = status_code
        self._json_body = json_body
        self.headers = {}
        self.text = ""

    def json(self):
        return self._json_body


# Real response for GET /challenges?titre=CSRF, captured live.
SEARCH_RESPONSE = [
    {
        "0": {
            "id_challenge": "1019",
            "id_rubrique": "16",
            "titre": "CSRF - 0 protection",
            "lang": "fr",
            "date_publication": "2016-02-16 19:40:20",
            "maj": "2024-06-26 10:50:07",
        },
        "1": {
            "id_challenge": "1021",
            "id_rubrique": "16",
            "titre": "CSRF - contournement de jeton",
            "lang": "fr",
            "date_publication": "2016-02-18 19:42:51",
            "maj": "2024-06-26 10:49:48",
        },
    }
]

# Real response for GET /challenges/1019, captured live (trimmed).
DETAIL_RESPONSE = [
    {
        "titre": "CSRF - 0 protection",
        "rubrique": "Web - Client",
        "score": "35",
        "id_rubrique": "16",
        "url_challenge": "fr/Challenges/Web-Client/CSRF-0-protection",
        "difficulte": "Moyen",
    }
]


def test_search_challenges_parses_real_response_shape():
    with patch("httpx.get", return_value=_FakeResponse(200, SEARCH_RESPONSE)):
        results = _adapter().search_challenges("CSRF")

    assert len(results) == 2
    first = results[0]
    assert first.external_challenge_id == "1019"
    assert first.title == "CSRF - 0 protection"
    assert first.language == "fr"  # was None before the fix (wrong key "langue")
    assert first.category == "16"  # the id_rubrique, not a name — this endpoint has no name field
    assert first.url is None  # this endpoint has no URL field at all


def test_get_challenge_detail_parses_real_response_and_builds_url():
    with patch("httpx.get", return_value=_FakeResponse(200, DETAIL_RESPONSE)):
        detail = _adapter().get_challenge_detail("1019")

    assert detail.title == "CSRF - 0 protection"
    assert detail.category == "Web - Client"
    assert detail.score == 35
    assert detail.url == "https://www.root-me.org/fr/Challenges/Web-Client/CSRF-0-protection"


def test_get_challenge_detail_url_none_when_api_omits_it():
    with patch("httpx.get", return_value=_FakeResponse(200, [{"titre": "X", "rubrique": "Y", "score": "1"}])):
        detail = _adapter().get_challenge_detail("999")

    assert detail.url is None
