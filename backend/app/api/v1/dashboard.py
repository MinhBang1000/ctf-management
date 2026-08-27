from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_member, get_db
from app.models.challenge import Challenge
from app.models.member import Member
from app.models.platform import Platform
from app.models.progress import Progress, ProgressStatus
from app.models.reminder_log import ReminderLog
from app.models.report import Report
from app.models.semester import Semester
from app.models.sync_log import SyncLog
from app.schemas.dashboard import LabDashboardOut, PendingReport, SemesterReportNudge, StatusCounts

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=LabDashboardOut)
def get_dashboard(db: Session = Depends(get_db), current: Member = Depends(get_current_member)):
    tenant_id = current.tenant_id

    member_count = db.query(Member).filter(Member.tenant_id == tenant_id).count()
    active_member_count = (
        db.query(Member).filter(Member.tenant_id == tenant_id, Member.active.is_(True)).count()
    )
    semester_count = db.query(Semester).filter(Semester.tenant_id == tenant_id).count()
    current_semester = (
        db.query(Semester).filter(Semester.tenant_id == tenant_id, Semester.is_current.is_(True)).first()
    )
    challenge_count = db.query(Challenge).filter(Challenge.tenant_id == tenant_id).count()

    counts = StatusCounts()
    rows = (
        db.query(Progress.status, Progress.id)
        .join(Challenge, Progress.challenge_id == Challenge.id)
        .filter(Challenge.tenant_id == tenant_id)
        .all()
    )
    for status_value, _ in rows:
        status_str = status_value.value if isinstance(status_value, ProgressStatus) else status_value
        if hasattr(counts, status_str):
            setattr(counts, status_str, getattr(counts, status_str) + 1)

    focus_platform = (
        db.query(Platform)
        .filter(Platform.tenant_id == tenant_id, Platform.is_focus.is_(True), Platform.is_active.is_(True))
        .first()
    )
    last_sync = None
    if focus_platform:
        last_sync = (
            db.query(SyncLog)
            .filter(SyncLog.tenant_id == tenant_id, SyncLog.platform_id == focus_platform.id)
            .order_by(SyncLog.run_at.desc())
            .first()
        )

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    reminders_sent_this_week = (
        db.query(ReminderLog)
        .join(Challenge, ReminderLog.challenge_id == Challenge.id)
        .filter(Challenge.tenant_id == tenant_id, ReminderLog.sent_at >= week_ago)
        .count()
    )

    pending_report_row = (
        db.query(Report)
        .filter(Report.tenant_id == tenant_id, Report.status == "draft")
        .order_by(Report.generated_at.desc())
        .first()
    )
    pending_report = (
        PendingReport(
            id=pending_report_row.id,
            period_start=pending_report_row.period_start,
            period_end=pending_report_row.period_end,
        )
        if pending_report_row
        else None
    )

    # Low-priority nudge (Phase 5, not a hard PRD requirement): a Semester
    # that's ended with no semester Report yet. Deliberately plain/less
    # prominent than pending_report's banner — this is a suggestion, not
    # an action already queued up for approval.
    reported_semester_ids = {
        r.semester_id for r in db.query(Report.semester_id).filter(Report.tenant_id == tenant_id, Report.type == "semester")
    }
    ended_semester = (
        db.query(Semester)
        .filter(Semester.tenant_id == tenant_id, Semester.end_date < datetime.now(timezone.utc).date())
        .order_by(Semester.end_date.desc())
        .first()
    )
    semester_report_nudge = (
        SemesterReportNudge(semester_id=ended_semester.id, semester_name=ended_semester.name, end_date=ended_semester.end_date)
        if ended_semester and ended_semester.id not in reported_semester_ids
        else None
    )

    return LabDashboardOut(
        member_count=member_count,
        active_member_count=active_member_count,
        semester_count=semester_count,
        challenge_count=challenge_count,
        current_semester_name=current_semester.name if current_semester else None,
        status_counts=counts,
        focus_platform_name=focus_platform.name if focus_platform else None,
        focus_platform_configured=bool(focus_platform and focus_platform.has_credentials),
        last_sync_run_at=last_sync.run_at if last_sync else None,
        last_sync_status=last_sync.status if last_sync else None,
        reminders_sent_this_week=reminders_sent_this_week,
        pending_report=pending_report,
        semester_report_nudge=semester_report_nudge,
    )
