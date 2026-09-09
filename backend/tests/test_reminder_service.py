"""send_reminders_for_tenant's actual dedup/rendering/auto-send-vs-queue
logic — previously had zero direct test coverage (only ever exercised
through a fully-mocked call in test_automation_dispatcher.py). Email is
mocked everywhere here, never a real send.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.progress import ProgressStatus
from app.models.reminder_log import ReminderLog
from app.services.automation_settings_service import get_or_create_automation_settings
from app.services.email_service import EmailSendError
from app.services.reminder_service import (
    DEFAULT_REMINDER_SUBJECT_TEMPLATE,
    render_reminder_content,
    send_one_pending_reminder,
    send_reminders_for_tenant,
)
from tests.conftest import (
    make_challenge,
    make_member,
    make_platform,
    make_progress,
    make_semester,
    set_tenant_context,
)


def _setup(db, tenant, deadline_in_days=2, active=True):
    # send_reminders_for_tenant pre-checks SMTP config before iterating —
    # give the tenant its own so this doesn't depend on whatever (if
    # anything) DEFAULT_SMTP_HOST happens to be in this environment's .env.
    set_tenant_context(db, tenant.id)
    tenant.smtp_config = {"host": "smtp.test.invalid", "username": "x", "password": "y"}
    db.commit()
    semester = make_semester(db, tenant)
    platform = make_platform(db, tenant)
    member = make_member(db, tenant, email="student@example.com", active=active)
    challenge = make_challenge(
        db, tenant, semester, platform, title="Buffer Overflow",
        deadline_at=datetime.now(timezone.utc) + timedelta(days=deadline_in_days),
    )
    return member, challenge


# --- auto-send (default, legacy behavior) ---------------------------------

def test_auto_send_sends_email_and_logs_sent(db, tenant):
    member, challenge = _setup(db, tenant)  # T-3 reached, T-1 not yet
    with patch("app.services.reminder_service.send_email") as mock_send:
        result = send_reminders_for_tenant(db, tenant)
    mock_send.assert_called_once()
    assert len(result["sent"]) == 1
    assert result["queued"] == []

    set_tenant_context(db, tenant.id)
    row = db.query(ReminderLog).filter(ReminderLog.member_id == member.id, ReminderLog.challenge_id == challenge.id).first()
    assert row.status == "sent"
    assert row.milestone == "T-3"
    assert row.sent_at is not None
    assert row.subject and row.body


def test_no_reminder_for_completed_member(db, tenant):
    member, challenge = _setup(db, tenant)
    make_progress(db, member, challenge, status=ProgressStatus.DONE)
    with patch("app.services.reminder_service.send_email") as mock_send:
        result = send_reminders_for_tenant(db, tenant)
    mock_send.assert_not_called()
    assert result["sent"] == []


def test_no_reminder_for_inactive_member(db, tenant):
    _setup(db, tenant, active=False)
    with patch("app.services.reminder_service.send_email") as mock_send:
        send_reminders_for_tenant(db, tenant)
    mock_send.assert_not_called()


def test_dedup_prevents_second_send_same_milestone(db, tenant):
    _setup(db, tenant)
    with patch("app.services.reminder_service.send_email"):
        send_reminders_for_tenant(db, tenant)
    with patch("app.services.reminder_service.send_email") as mock_send_again:
        result = send_reminders_for_tenant(db, tenant)
    mock_send_again.assert_not_called()
    assert result["sent"] == []


def test_send_failure_recorded_and_not_deduped_from_retry(db, tenant):
    _setup(db, tenant)
    with patch("app.services.reminder_service.send_email", side_effect=EmailSendError("smtp down")):
        result = send_reminders_for_tenant(db, tenant)
    assert result["errors"]
    set_tenant_context(db, tenant.id)
    # A failed send is rolled back entirely (no ReminderLog row at all —
    # matches the original pre-existing behavior), so it's eligible again
    # on the very next run, not stuck requiring a separate "retry" action.
    assert db.query(ReminderLog).count() == 0


# --- manual review queue (reminder_auto_send=False) ------------------------

def test_manual_mode_queues_instead_of_sending(db, tenant):
    member, challenge = _setup(db, tenant)
    settings = get_or_create_automation_settings(db, tenant.id)
    settings.reminder_auto_send = False
    db.commit()

    with patch("app.services.reminder_service.send_email") as mock_send:
        result = send_reminders_for_tenant(db, tenant, settings)
    mock_send.assert_not_called()
    assert len(result["queued"]) == 1
    assert result["sent"] == []

    set_tenant_context(db, tenant.id)
    row = db.query(ReminderLog).filter(ReminderLog.member_id == member.id, ReminderLog.challenge_id == challenge.id).first()
    assert row.status == "pending"
    assert row.sent_at is None
    assert "Buffer Overflow" in row.body


def test_manual_mode_also_dedups(db, tenant):
    _setup(db, tenant)
    settings = get_or_create_automation_settings(db, tenant.id)
    settings.reminder_auto_send = False
    db.commit()

    send_reminders_for_tenant(db, tenant, settings)
    result = send_reminders_for_tenant(db, tenant, settings)
    assert result["queued"] == []


# --- custom templates -------------------------------------------------------

def test_custom_template_overrides_default_rendering():
    settings = type("S", (), {
        "reminder_subject_template": "Hey {{ member_name }}, {{ challenge_title }} is due soon",
        "reminder_body_template": "Custom body for {{ member_name }} — {{ days_left }} days left.",
    })()
    subject, body = render_reminder_content(
        settings, member_name="Alice", challenge_title="CSRF", deadline="2026-01-01 00:00 UTC",
        days_left=3, milestone="T-3",
    )
    assert subject == "Hey Alice, CSRF is due soon"
    assert body == "Custom body for Alice — 3 days left."


def test_default_template_used_when_none_set():
    subject, body = render_reminder_content(
        None, member_name="Alice", challenge_title="CSRF", deadline="2026-01-01 00:00 UTC",
        days_left=3, milestone="T-3",
    )
    assert subject == 'Reminder: "CSRF" due in 3 day(s)'
    assert "Alice" in body
    assert "CSRF" in body


def test_default_subject_template_matches_original_f_string_format():
    # Locks the exact wording so switching to a Jinja-rendered default
    # never silently changes what every existing Lab has been receiving.
    assert DEFAULT_REMINDER_SUBJECT_TEMPLATE == 'Reminder: "{{ challenge_title }}" due in {{ days_left }} day(s)'


# --- send_one_pending_reminder (manual send / retry) ------------------------

def test_send_one_pending_reminder_success(db, tenant, lab_leader):
    member, challenge = _setup(db, tenant)
    settings = get_or_create_automation_settings(db, tenant.id)
    settings.reminder_auto_send = False
    db.commit()
    send_reminders_for_tenant(db, tenant, settings)

    set_tenant_context(db, tenant.id)
    row = db.query(ReminderLog).filter(ReminderLog.member_id == member.id, ReminderLog.challenge_id == challenge.id).first()

    with patch("app.services.reminder_service.send_email") as mock_send:
        send_one_pending_reminder(db, row, tenant, attempted_by=lab_leader.email)
    mock_send.assert_called_once()

    set_tenant_context(db, tenant.id)
    row = db.query(ReminderLog).filter(ReminderLog.id == row.id).first()
    assert row.status == "sent"
    assert row.attempted_by == lab_leader.email
    assert row.sent_at is not None


def test_send_one_pending_reminder_failure_is_retryable(db, tenant, lab_leader):
    member, challenge = _setup(db, tenant)
    settings = get_or_create_automation_settings(db, tenant.id)
    settings.reminder_auto_send = False
    db.commit()
    send_reminders_for_tenant(db, tenant, settings)

    set_tenant_context(db, tenant.id)
    row = db.query(ReminderLog).filter(ReminderLog.member_id == member.id, ReminderLog.challenge_id == challenge.id).first()

    with patch("app.services.reminder_service.send_email", side_effect=EmailSendError("smtp down")):
        try:
            send_one_pending_reminder(db, row, tenant, attempted_by=lab_leader.email)
        except EmailSendError:
            pass

    set_tenant_context(db, tenant.id)
    row = db.query(ReminderLog).filter(ReminderLog.id == row.id).first()
    assert row.status == "failed"
    assert row.error_detail == "smtp down"

    with patch("app.services.reminder_service.send_email") as mock_send:
        send_one_pending_reminder(db, row, tenant, attempted_by=lab_leader.email)
    mock_send.assert_called_once()
    set_tenant_context(db, tenant.id)
    row = db.query(ReminderLog).filter(ReminderLog.id == row.id).first()
    assert row.status == "sent"
