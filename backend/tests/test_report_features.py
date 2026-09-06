"""§9 weekly report idempotency, §10 recipient audit, §11 retry/resend,
§13 historical reports include inactive members."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.member import MemberRole
from app.models.progress import ProgressStatus
from app.models.report import Report
from app.services.report_service import generate_semester_report_for_tenant, generate_weekly_report_for_tenant
from tests.conftest import make_challenge, make_member, make_platform, make_progress, make_semester


# --- §9 weekly report idempotency --------------------------------------

def test_generate_weekly_report_twice_does_not_duplicate(db, tenant):
    make_semester(db, tenant)
    r1 = generate_weekly_report_for_tenant(db, tenant)
    r2 = generate_weekly_report_for_tenant(db, tenant)
    assert r1.id == r2.id
    count = db.query(Report).filter(Report.tenant_id == tenant.id, Report.type == "weekly").count()
    assert count == 1


def test_generate_weekly_report_after_sent_does_not_overwrite(db, tenant):
    make_semester(db, tenant)
    report = generate_weekly_report_for_tenant(db, tenant)
    report.status = "sent"
    report.content = "ORIGINAL SENT CONTENT"
    db.commit()

    again = generate_weekly_report_for_tenant(db, tenant)
    assert again.id == report.id
    assert again.content == "ORIGINAL SENT CONTENT"


def test_db_level_uniqueness_backs_up_the_app_check(db, tenant):
    """Even a raw insert bypassing the service function can't create a
    second report for the same (tenant, semester, type, period)."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    semester = make_semester(db, tenant)
    report = generate_weekly_report_for_tenant(db, tenant)
    dup = Report(
        tenant_id=tenant.id,
        semester_id=semester.id,
        type="weekly",
        period_start=report.period_start,
        period_end=report.period_end,
        status="draft",
        content="dup",
    )
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --- §10/§11 recipient tracking + retry/resend --------------------------

def test_approve_report_records_recipient_and_success_attempt(leader_client, db, tenant):
    make_semester(db, tenant)
    report = generate_weekly_report_for_tenant(db, tenant)

    with patch("app.api.v1.reports.send_email") as mock_send:
        resp = leader_client.post(f"/api/v1/reports/{report.id}/approve", json={"to_address": "prof@example.com"})
    assert resp.status_code == 200
    assert resp.json()["recipient_email"] == "prof@example.com"

    attempts = leader_client.get(f"/api/v1/reports/{report.id}/send-attempts").json()
    assert len(attempts) == 1
    assert attempts[0]["kind"] == "initial"
    assert attempts[0]["status"] == "success"


def test_failed_send_is_recorded_and_report_stays_draft_for_retry(leader_client, db, tenant):
    from app.services.email_service import EmailSendError

    make_semester(db, tenant)
    report = generate_weekly_report_for_tenant(db, tenant)

    with patch("app.api.v1.reports.send_email", side_effect=EmailSendError("smtp down")):
        resp = leader_client.post(f"/api/v1/reports/{report.id}/approve", json={"to_address": "prof@example.com"})
    assert resp.status_code == 502

    attempts = leader_client.get(f"/api/v1/reports/{report.id}/send-attempts").json()
    assert attempts[0]["status"] == "failed"
    assert attempts[0]["kind"] == "initial"

    # Report is still draft — retry via the SAME approve endpoint.
    with patch("app.api.v1.reports.send_email") as mock_send:
        retry = leader_client.post(f"/api/v1/reports/{report.id}/approve", json={"to_address": "prof@example.com"})
    assert retry.status_code == 200
    attempts_after = leader_client.get(f"/api/v1/reports/{report.id}/send-attempts").json()
    kinds = {a["kind"] for a in attempts_after}
    assert "retry" in kinds


def test_resend_requires_explicit_confirmation(leader_client, db, tenant):
    make_semester(db, tenant)
    report = generate_weekly_report_for_tenant(db, tenant)
    with patch("app.api.v1.reports.send_email"):
        leader_client.post(f"/api/v1/reports/{report.id}/approve", json={"to_address": "prof@example.com"})

    unconfirmed = leader_client.post(
        f"/api/v1/reports/{report.id}/resend", json={"to_address": "prof2@example.com", "confirm": False}
    )
    assert unconfirmed.status_code == 400

    with patch("app.api.v1.reports.send_email"):
        confirmed = leader_client.post(
            f"/api/v1/reports/{report.id}/resend", json={"to_address": "prof2@example.com", "confirm": True}
        )
    assert confirmed.status_code == 200
    assert confirmed.json()["recipient_email"] == "prof2@example.com"
    # Original send metadata untouched by a resend.
    assert confirmed.json()["status"] == "sent"


def test_cannot_resend_a_draft_report(leader_client, db, tenant):
    make_semester(db, tenant)
    report = generate_weekly_report_for_tenant(db, tenant)
    resp = leader_client.post(
        f"/api/v1/reports/{report.id}/resend", json={"to_address": "x@example.com", "confirm": True}
    )
    assert resp.status_code == 400


def test_cannot_approve_already_sent_report(leader_client, db, tenant):
    make_semester(db, tenant)
    report = generate_weekly_report_for_tenant(db, tenant)
    with patch("app.api.v1.reports.send_email"):
        leader_client.post(f"/api/v1/reports/{report.id}/approve", json={"to_address": "prof@example.com"})
    again = leader_client.post(f"/api/v1/reports/{report.id}/approve", json={"to_address": "prof@example.com"})
    assert again.status_code == 400


# --- §13 historical reports include inactive members --------------------

def test_semester_report_includes_member_deactivated_after_participating(db, tenant):
    platform = make_platform(db, tenant)
    semester = make_semester(
        db, tenant, start_date=(datetime.now(timezone.utc) - timedelta(days=60)).date(),
        end_date=(datetime.now(timezone.utc) - timedelta(days=1)).date(),
    )
    departed = make_member(
        db, tenant, email="departed@example.com", full_name="Departed Member",
        joined_at=datetime.now(timezone.utc) - timedelta(days=90),
    )
    challenge = make_challenge(
        db, tenant, semester, platform, deadline_at=datetime.now(timezone.utc) - timedelta(days=30)
    )
    make_progress(db, departed, challenge, status=ProgressStatus.DONE)

    # Simulate them leaving the Lab AFTER the semester, before the report
    # is generated — the exact bug §13 describes.
    departed.active = False
    db.commit()

    report = generate_semester_report_for_tenant(db, tenant, semester)
    member_names = {m["member_name"] for m in report.data["members"]}
    assert "Departed Member" in member_names


def test_semester_report_excludes_member_who_joined_after_it_ended(db, tenant):
    platform = make_platform(db, tenant)
    semester = make_semester(
        db, tenant, start_date=(datetime.now(timezone.utc) - timedelta(days=60)).date(),
        end_date=(datetime.now(timezone.utc) - timedelta(days=30)).date(),
    )
    make_challenge(db, tenant, semester, platform, deadline_at=datetime.now(timezone.utc) - timedelta(days=45))
    # joined_at defaults to now() server-side — well after this semester ended.
    late_joiner = make_member(db, tenant, email="late@example.com", full_name="Late Joiner")

    report = generate_semester_report_for_tenant(db, tenant, semester)
    member_names = {m["member_name"] for m in report.data["members"]}
    assert "Late Joiner" not in member_names
