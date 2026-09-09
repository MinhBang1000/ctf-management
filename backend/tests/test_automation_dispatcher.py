"""The dispatcher's own decision logic (fire vs skip, auto-send vs
notify, once-per-Semester), tested by calling its internal functions
directly with the test's own `db` session — dispatch_automation() itself
opens a brand-new SessionLocal() (same shape as every other per-tenant
Celery task in this codebase, e.g. sync_tasks/backup_tasks), which can't
see this test's uncommitted transaction, so the real unit under test is
these functions, not that thin per-tenant-loop shell.

Email is mocked everywhere here — never a real send (see
app.tasks.automation_dispatcher.send_email import site being the patch
target, exactly like the existing reports.py tests patch
app.api.v1.reports.send_email).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.job_run_log import JobRunLog
from app.models.notification import Notification
from app.models.report import Report
from app.models.report_send_attempt import ReportSendAttempt
from app.services.automation_settings_service import get_or_create_automation_settings
from app.services.email_service import EmailSendError
from app.tasks.automation_dispatcher import (
    SYSTEM_AUTO_SEND_LABEL,
    _dispatch_reminders,
    _dispatch_semester_reports,
    _dispatch_weekly_report,
)
from tests.conftest import make_semester, set_tenant_context


def _far_past():
    return datetime(2020, 1, 1, tzinfo=timezone.utc)


# --- reminders -----------------------------------------------------------

def test_dispatch_reminders_fires_when_due_and_stamps_anchor(db, tenant, lab_leader):
    settings = get_or_create_automation_settings(db, tenant.id)
    settings.reminder_last_fired_at = _far_past()
    db.commit()
    now = datetime.now(timezone.utc)

    _dispatch_reminders(db, tenant, tenant.id, settings, now)

    set_tenant_context(db, tenant.id)
    assert abs((settings.reminder_last_fired_at - now).total_seconds()) < 5
    runs = db.query(JobRunLog).filter(JobRunLog.tenant_id == tenant.id, JobRunLog.job_type == "reminder").all()
    assert len(runs) == 1


def test_dispatch_reminders_skips_when_not_due(db, tenant):
    set_tenant_context(db, tenant.id)
    settings = get_or_create_automation_settings(db, tenant.id)
    now = datetime.now(timezone.utc)
    settings.reminder_last_fired_at = now  # just fired
    db.commit()

    with patch("app.tasks.automation_dispatcher.send_reminders_for_tenant") as mock_send:
        _dispatch_reminders(db, tenant, tenant.id, settings, now + timedelta(minutes=1))
    mock_send.assert_not_called()


# --- weekly report ---------------------------------------------------------

def test_dispatch_weekly_report_notifies_without_auto_send(db, tenant, lab_leader):
    make_semester(db, tenant)
    settings = get_or_create_automation_settings(db, tenant.id)
    settings.weekly_report_last_fired_at = _far_past()
    settings.weekly_report_auto_send = False
    db.commit()

    _dispatch_weekly_report(db, tenant, tenant.id, settings, datetime.now(timezone.utc))

    set_tenant_context(db, tenant.id)
    report = db.query(Report).filter(Report.tenant_id == tenant.id, Report.type == "weekly").first()
    assert report is not None
    assert report.status == "draft"
    notifications = db.query(Notification).filter(Notification.tenant_id == tenant.id, Notification.type == "report_ready").all()
    assert len(notifications) >= 1


def test_dispatch_weekly_report_auto_sends_when_enabled(db, tenant, lab_leader):
    make_semester(db, tenant)
    set_tenant_context(db, tenant.id)
    tenant.professor_email = "prof@example.com"
    db.commit()
    settings = get_or_create_automation_settings(db, tenant.id)
    settings.weekly_report_last_fired_at = _far_past()
    settings.weekly_report_auto_send = True
    db.commit()

    with patch("app.tasks.automation_dispatcher.send_email") as mock_send:
        _dispatch_weekly_report(db, tenant, tenant.id, settings, datetime.now(timezone.utc))
    mock_send.assert_called_once()

    set_tenant_context(db, tenant.id)
    report = db.query(Report).filter(Report.tenant_id == tenant.id, Report.type == "weekly").first()
    assert report.status == "sent"
    assert report.approved_by == SYSTEM_AUTO_SEND_LABEL
    attempt = db.query(ReportSendAttempt).filter(ReportSendAttempt.report_id == report.id).first()
    assert attempt.status == "success"
    assert attempt.attempted_by_email == SYSTEM_AUTO_SEND_LABEL


def test_auto_send_skipped_without_professor_email(db, tenant, lab_leader):
    make_semester(db, tenant)
    settings = get_or_create_automation_settings(db, tenant.id)
    settings.weekly_report_last_fired_at = _far_past()
    settings.weekly_report_auto_send = True
    db.commit()
    assert tenant.professor_email is None

    with patch("app.tasks.automation_dispatcher.send_email") as mock_send:
        _dispatch_weekly_report(db, tenant, tenant.id, settings, datetime.now(timezone.utc))
    mock_send.assert_not_called()

    set_tenant_context(db, tenant.id)
    report = db.query(Report).filter(Report.tenant_id == tenant.id, Report.type == "weekly").first()
    assert report.status == "draft"  # never sent, but not a crash either


def test_auto_send_failure_recorded_as_failed_attempt(db, tenant, lab_leader):
    make_semester(db, tenant)
    set_tenant_context(db, tenant.id)
    tenant.professor_email = "prof@example.com"
    db.commit()
    settings = get_or_create_automation_settings(db, tenant.id)
    settings.weekly_report_last_fired_at = _far_past()
    settings.weekly_report_auto_send = True
    db.commit()

    with patch("app.tasks.automation_dispatcher.send_email", side_effect=EmailSendError("smtp down")):
        _dispatch_weekly_report(db, tenant, tenant.id, settings, datetime.now(timezone.utc))

    set_tenant_context(db, tenant.id)
    report = db.query(Report).filter(Report.tenant_id == tenant.id, Report.type == "weekly").first()
    assert report.status == "draft"  # a failed auto-send never flips status to sent
    attempt = db.query(ReportSendAttempt).filter(ReportSendAttempt.report_id == report.id).first()
    assert attempt.status == "failed"


# --- semester report -------------------------------------------------------

def test_dispatch_semester_report_fires_once_and_never_again(db, tenant, lab_leader):
    semester = make_semester(db, tenant, end_date=datetime.now(timezone.utc).date() - timedelta(days=1))
    now = datetime.now(timezone.utc)

    _dispatch_semester_reports(db, tenant, tenant.id, now)
    set_tenant_context(db, tenant.id)
    reports = db.query(Report).filter(Report.tenant_id == tenant.id, Report.type == "semester").all()
    assert len(reports) == 1
    assert semester.report_last_fired_at is not None

    # Second tick: must NOT generate a second report or re-notify.
    with patch("app.tasks.automation_dispatcher.generate_semester_report_for_tenant") as mock_gen:
        _dispatch_semester_reports(db, tenant, tenant.id, now + timedelta(days=1))
    mock_gen.assert_not_called()


def test_dispatch_semester_report_respects_disabled_flag(db, tenant, lab_leader):
    semester = make_semester(db, tenant, end_date=datetime.now(timezone.utc).date() - timedelta(days=1))
    set_tenant_context(db, tenant.id)
    semester.report_automation_enabled = False
    db.commit()

    with patch("app.tasks.automation_dispatcher.generate_semester_report_for_tenant") as mock_gen:
        _dispatch_semester_reports(db, tenant, tenant.id, datetime.now(timezone.utc))
    mock_gen.assert_not_called()


def test_dispatch_semester_report_not_yet_due(db, tenant, lab_leader):
    make_semester(db, tenant, end_date=datetime.now(timezone.utc).date() + timedelta(days=30))

    with patch("app.tasks.automation_dispatcher.generate_semester_report_for_tenant") as mock_gen:
        _dispatch_semester_reports(db, tenant, tenant.id, datetime.now(timezone.utc))
    mock_gen.assert_not_called()


def test_dispatch_semester_report_auto_sends(db, tenant, lab_leader):
    semester = make_semester(db, tenant, end_date=datetime.now(timezone.utc).date() - timedelta(days=1))
    set_tenant_context(db, tenant.id)
    semester.report_auto_send = True
    tenant.professor_email = "prof@example.com"
    db.commit()

    with patch("app.tasks.automation_dispatcher.send_email") as mock_send:
        _dispatch_semester_reports(db, tenant, tenant.id, datetime.now(timezone.utc))
    mock_send.assert_called_once()

    set_tenant_context(db, tenant.id)
    report = db.query(Report).filter(Report.tenant_id == tenant.id, Report.type == "semester").first()
    assert report.status == "sent"
