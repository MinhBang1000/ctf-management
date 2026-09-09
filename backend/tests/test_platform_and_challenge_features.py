"""§1 Root Me challenge search + URL field, §4 challenge editing,
§7 persisted platform connection verification."""
from unittest.mock import patch

from app.adapters.base import ChallengeSearchResult
from tests.conftest import make_platform, make_semester


def _challenge_payload(semester, platform, **overrides):
    payload = {
        "semester_id": str(semester.id),
        "platform_id": str(platform.id),
        "week_number": 1,
        "title": "Buffer Overflow 101",
        "deadline_at": "2026-12-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


# --- §7 persisted platform connection verification ----------------------

def test_focus_requires_verified_credentials_not_just_nonempty(leader_client, db, tenant):
    platform = make_platform(db, tenant, auth_config={"api_key": "whatever"})
    resp = leader_client.post(f"/api/v1/platforms/{platform.id}/focus")
    assert resp.status_code == 400
    assert "Test Connection" in resp.json()["detail"]


def test_successful_test_connection_persists_verification_and_enables_focus(leader_client, db, tenant):
    platform = make_platform(db, tenant, auth_config={"api_key": "whatever"})
    with patch("app.api.v1.platforms.get_adapter") as mock_get_adapter:
        mock_get_adapter.return_value.get_user_completed_challenges.return_value = []
        resp = leader_client.post(f"/api/v1/platforms/{platform.id}/test-connection")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    focus_resp = leader_client.post(f"/api/v1/platforms/{platform.id}/focus")
    assert focus_resp.status_code == 200
    assert focus_resp.json()["credentials_verified_at"] is not None


def test_editing_credentials_invalidates_verification(leader_client, db, tenant):
    platform = make_platform(db, tenant, auth_config={"api_key": "whatever"})
    with patch("app.api.v1.platforms.get_adapter") as mock_get_adapter:
        mock_get_adapter.return_value.get_user_completed_challenges.return_value = []
        leader_client.post(f"/api/v1/platforms/{platform.id}/test-connection")

    resp = leader_client.patch(f"/api/v1/platforms/{platform.id}", json={"auth_config": {"api_key": "a-new-key"}})
    assert resp.status_code == 200
    assert resp.json()["credentials_verified_at"] is None

    focus_resp = leader_client.post(f"/api/v1/platforms/{platform.id}/focus")
    assert focus_resp.status_code == 400


def test_inactive_platform_cannot_become_focus(leader_client, db, tenant):
    platform = make_platform(db, tenant, auth_config={"api_key": "whatever"}, is_active=False)
    with patch("app.api.v1.platforms.get_adapter") as mock_get_adapter:
        mock_get_adapter.return_value.get_user_completed_challenges.return_value = []
        leader_client.post(f"/api/v1/platforms/{platform.id}/test-connection")
    resp = leader_client.post(f"/api/v1/platforms/{platform.id}/focus")
    assert resp.status_code == 400


# --- §1 Root Me challenge search + URL field -----------------------------

def test_challenge_search_endpoint_returns_adapter_results(leader_client, db, tenant):
    platform = make_platform(db, tenant, auth_config={"api_key": "whatever"})
    fake_results = [
        ChallengeSearchResult(external_challenge_id="42", title="Buffer Overflow 101", category="App-Script", language="en", url="https://www.root-me.org/en/Challenges/App-Script/Buffer-Overflow-101")
    ]
    with patch("app.api.v1.platforms.get_adapter") as mock_get_adapter:
        mock_get_adapter.return_value.search_challenges.return_value = fake_results
        resp = leader_client.get(f"/api/v1/platforms/{platform.id}/challenge-search", params={"title": "buffer"})
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["external_challenge_id"] == "42"
    assert body[0]["url"].startswith("https://www.root-me.org/")


def test_challenge_url_must_be_https(leader_client, db, tenant):
    semester = make_semester(db, tenant)
    platform = make_platform(db, tenant)
    resp = leader_client.post(
        "/api/v1/challenges",
        json=_challenge_payload(semester, platform, external_url="http://insecure.example.com/x"),
    )
    assert resp.status_code == 422


def test_challenge_create_and_edit_with_url(leader_client, db, tenant):
    semester = make_semester(db, tenant)
    platform = make_platform(db, tenant)
    create_resp = leader_client.post(
        "/api/v1/challenges",
        json=_challenge_payload(
            semester, platform, external_url="https://www.root-me.org/en/Challenges/App-Script/Buffer-Overflow-101"
        ),
    )
    assert create_resp.status_code == 201, create_resp.text
    challenge_id = create_resp.json()["id"]

    # §4 — full edit, not just create/delete.
    edit_resp = leader_client.patch(
        f"/api/v1/challenges/{challenge_id}",
        json={"title": "Buffer Overflow 102", "points": 150, "week_number": 2},
    )
    assert edit_resp.status_code == 200
    body = edit_resp.json()
    assert body["title"] == "Buffer Overflow 102"
    assert body["points"] == 150
    assert body["week_number"] == 2
    # Untouched fields preserved.
    assert body["external_url"].startswith("https://www.root-me.org/")


def test_challenge_edit_rejects_presenter_from_another_tenant(leader_client, db, tenant, other_tenant):
    from tests.conftest import make_member

    semester = make_semester(db, tenant)
    platform = make_platform(db, tenant)
    create_resp = leader_client.post("/api/v1/challenges", json=_challenge_payload(semester, platform))
    challenge_id = create_resp.json()["id"]

    foreign_presenter = make_member(db, other_tenant, email="foreign-presenter@example.com")
    resp = leader_client.patch(f"/api/v1/challenges/{challenge_id}", json={"presenter_id": str(foreign_presenter.id)})
    assert resp.status_code == 400
