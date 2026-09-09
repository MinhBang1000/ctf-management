"""GET/PATCH/POST/DELETE /api/v1/reminders — pending-reminders review
queue API. Email is mocked, never a real send."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.conftest import (
    login_as,
    make_challenge,
    make_member,
    make_platform,
    make_semester,
    set_tenant_context,
)


def _student_reminder(client):
    """send_reminders_for_tenant reminds every active Member who hasn't
    completed the challenge, including the Lab Leader themselves (no
    role filter — matches the original PRD §6.7 behavior) — leader_client's
    own lab_leader fixture is one of those, so tests pick out the
    "student" member's row specifically rather than assuming there's
    only one pending reminder."""
    body = client.get("/api/v1/reminders/pending").json()
    matches = [r for r in body if r["member_email"] == "student@example.com"]
    assert len(matches) == 1
    return matches[0]


def _queue_one(db, tenant, leader_client):
    set_tenant_context(db, tenant.id)
    tenant.smtp_config = {"host": "smtp.test.invalid"}
    db.commit()
    leader_client.patch(
        "/api/v1/settings/automation",
        json={
            "reminder": {"enabled": True, "repeat": "daily", "time_of_day": "06:00:00"},
            "weekly_report": {"enabled": True, "repeat": "weekly", "time_of_day": "00:00:00", "day_of_week": 0},
            "weekly_report_auto_send": False,
            "reminder_auto_send": False,
        },
    )
    semester = make_semester(db, tenant)
    platform = make_platform(db, tenant)
    member = make_member(db, tenant, email="student@example.com")
    challenge = make_challenge(
        db, tenant, semester, platform, title="CSRF",
        deadline_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    from app.services.automation_settings_service import get_or_create_automation_settings
    from app.services.reminder_service import send_reminders_for_tenant

    settings = get_or_create_automation_settings(db, tenant.id)
    send_reminders_for_tenant(db, tenant, settings)
    return member, challenge


def test_list_pending_reminders(leader_client, db, tenant):
    _queue_one(db, tenant, leader_client)
    row = _student_reminder(leader_client)
    assert row["status"] == "pending"
    assert row["milestone"] == "T-3"
    assert row["challenge_title"] == "CSRF"


def test_edit_pending_reminder(leader_client, db, tenant):
    _queue_one(db, tenant, leader_client)
    reminder_id = _student_reminder(leader_client)["id"]
    resp = leader_client.patch(
        f"/api/v1/reminders/{reminder_id}", json={"subject": "Custom subject", "body": "Custom body text"}
    )
    assert resp.status_code == 200
    assert resp.json()["subject"] == "Custom subject"
    assert resp.json()["body"] == "Custom body text"


def test_send_pending_reminder(leader_client, db, tenant):
    _queue_one(db, tenant, leader_client)
    reminder_id = _student_reminder(leader_client)["id"]
    with patch("app.services.reminder_service.send_email") as mock_send:
        resp = leader_client.post(f"/api/v1/reminders/{reminder_id}/send")
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"
    mock_send.assert_called_once()
    remaining = [r for r in leader_client.get("/api/v1/reminders/pending").json() if r["id"] == reminder_id]
    assert remaining == []


def test_send_failure_keeps_it_in_pending_list_as_failed(leader_client, db, tenant):
    from app.services.email_service import EmailSendError

    _queue_one(db, tenant, leader_client)
    reminder_id = _student_reminder(leader_client)["id"]
    with patch("app.services.reminder_service.send_email", side_effect=EmailSendError("smtp down")):
        resp = leader_client.post(f"/api/v1/reminders/{reminder_id}/send")
    assert resp.status_code == 502
    row = _student_reminder(leader_client)
    assert row["id"] == reminder_id
    assert row["status"] == "failed"
    assert row["error_detail"] == "smtp down"


def test_discard_pending_reminder(leader_client, db, tenant):
    _queue_one(db, tenant, leader_client)
    reminder_id = _student_reminder(leader_client)["id"]
    resp = leader_client.delete(f"/api/v1/reminders/{reminder_id}")
    assert resp.status_code == 204
    remaining = [r for r in leader_client.get("/api/v1/reminders/pending").json() if r["id"] == reminder_id]
    assert remaining == []


def test_cannot_edit_or_send_or_discard_after_sent(leader_client, db, tenant):
    _queue_one(db, tenant, leader_client)
    reminder_id = _student_reminder(leader_client)["id"]
    with patch("app.services.reminder_service.send_email"):
        leader_client.post(f"/api/v1/reminders/{reminder_id}/send")

    assert leader_client.patch(f"/api/v1/reminders/{reminder_id}", json={"subject": "x", "body": "y"}).status_code == 400
    assert leader_client.post(f"/api/v1/reminders/{reminder_id}/send").status_code == 400
    assert leader_client.delete(f"/api/v1/reminders/{reminder_id}").status_code == 400


def test_non_leader_forbidden(client, tenant, presenter):
    login_as(client, presenter.email, "presenterpass123")
    assert client.get("/api/v1/reminders/pending").status_code == 403


def test_cross_tenant_reminder_not_found(leader_client, db, tenant, other_tenant):
    _queue_one(db, tenant, leader_client)
    reminder_id = _student_reminder(leader_client)["id"]

    from app.models.member import MemberRole
    from tests.conftest import make_member as _mk

    other_leader = _mk(db, other_tenant, email="other-leader@example.com", role=MemberRole.LAB_LEADER, password="otherpass123")
    login_as(leader_client, other_leader.email, "otherpass123")
    resp = leader_client.get(f"/api/v1/reminders/pending")
    assert resp.json() == []
    assert leader_client.patch(f"/api/v1/reminders/{reminder_id}", json={"subject": "x", "body": "y"}).status_code == 404
