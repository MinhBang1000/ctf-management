import uuid
from datetime import datetime, timedelta, timezone

from jinja2 import Template
from sqlalchemy.orm import Session

from app.core.templates import TEMPLATES_DIR, render_template
from app.models.automation_settings import TenantAutomationSettings
from app.models.challenge import Challenge
from app.models.member import Member
from app.models.progress import Progress, ProgressStatus
from app.models.reminder_log import ReminderLog
from app.models.tenant import Tenant
from app.services.email_service import EmailConfigError, EmailSendError, get_smtp_config, send_email

# (days_before_deadline, milestone_label) — separate reminder_log entries
# per milestone so T-3 and T-1 are independently deduplicated.
MILESTONES = [(3, "T-3"), (1, "T-1")]

DEFAULT_REMINDER_SUBJECT_TEMPLATE = 'Reminder: "{{ challenge_title }}" due in {{ days_left }} day(s)'

# System auto-send actor label, shared with the dispatcher's report
# auto-send path (app.tasks.automation_dispatcher.SYSTEM_AUTO_SEND_LABEL)
# — kept as a separate constant here to avoid a service->task import.
SYSTEM_AUTO_SEND_LABEL = "system:auto-send"


def default_reminder_body_template() -> str:
    """Raw (unrendered) text of the built-in template — shown to the Lab
    Leader as a starting point/placeholder when customizing, and used as
    the actual render source when no custom template is configured."""
    return (TEMPLATES_DIR / "reminder_email.txt.j2").read_text()


def render_reminder_content(settings: TenantAutomationSettings | None, **context) -> tuple[str, str]:
    """Renders (subject, body) using the Tenant's custom template if set,
    else the built-in default — same Jinja context either way, so
    customizing never changes what data is available, only the wording."""
    subject_src = (settings.reminder_subject_template if settings else None) or DEFAULT_REMINDER_SUBJECT_TEMPLATE
    subject = Template(subject_src).render(**context)

    if settings and settings.reminder_body_template:
        body = Template(settings.reminder_body_template).render(**context)
    else:
        body = render_template("reminder_email.txt.j2", **context)
    return subject, body


def _reminder_context(member: Member, challenge: Challenge, days_before: int, milestone: str) -> dict:
    return {
        "member_name": member.full_name,
        "challenge_title": challenge.title,
        "deadline": challenge.deadline_at.strftime("%Y-%m-%d %H:%M UTC"),
        "days_left": days_before,
        "milestone": milestone,
    }


def send_reminders_for_tenant(db: Session, tenant: Tenant, settings: TenantAutomationSettings | None = None) -> dict:
    """PRD §6.7: T-3/T-1 reminders to Members who haven't completed a
    Challenge. Originally "no draft/approve gate" — now an explicit
    per-Lab opt-in (settings.reminder_auto_send, default True preserves
    that original behavior): when False, this generates ReminderLog rows
    with status="pending" instead of sending, for review at
    GET /api/v1/reminders/pending.

    "not_started or late" (as specified) maps onto our status enum as:
    no Progress row at all, or status in (missing, late) — there is no
    literal not_started value, flagged in the Phase 4 plan."""
    sent: list[dict] = []
    queued: list[dict] = []
    errors: list[str] = []
    auto_send = settings.reminder_auto_send if settings else True

    if auto_send:
        try:
            # Resolve once per tenant rather than once per recipient — if
            # SMTP isn't configured at all, every send would fail identically.
            get_smtp_config(tenant)
        except EmailConfigError as exc:
            return {"sent": [], "queued": [], "errors": [str(exc)]}

    now = datetime.now(timezone.utc)
    challenges = db.query(Challenge).filter(Challenge.tenant_id == tenant.id).all()
    members = db.query(Member).filter(Member.tenant_id == tenant.id, Member.active.is_(True)).all()

    for challenge in challenges:
        for days_before, milestone in MILESTONES:
            milestone_time = challenge.deadline_at - timedelta(days=days_before)
            if now < milestone_time:
                continue  # milestone not reached yet

            for member in members:
                progress = (
                    db.query(Progress)
                    .filter(Progress.member_id == member.id, Progress.challenge_id == challenge.id)
                    .first()
                )
                if progress and progress.status in (ProgressStatus.DONE, ProgressStatus.EARLY):
                    continue  # already completed, no reminder needed

                already_exists = (
                    db.query(ReminderLog)
                    .filter(
                        ReminderLog.member_id == member.id,
                        ReminderLog.challenge_id == challenge.id,
                        ReminderLog.milestone == milestone,
                    )
                    .first()
                )
                if already_exists:
                    continue  # already sent, pending, or failed (retry is a separate explicit action)

                context = _reminder_context(member, challenge, days_before, milestone)
                subject, body = render_reminder_content(settings, **context)

                if not auto_send:
                    db.add(ReminderLog(
                        member_id=member.id, challenge_id=challenge.id, milestone=milestone,
                        status="pending", subject=subject, body=body,
                    ))
                    db.commit()
                    queued.append(
                        {"member_id": str(member.id), "challenge_id": str(challenge.id), "milestone": milestone}
                    )
                    continue

                try:
                    send_email(tenant, member.email, subject=subject, body=body)
                    db.add(ReminderLog(
                        member_id=member.id, challenge_id=challenge.id, milestone=milestone,
                        status="sent", subject=subject, body=body,
                        sent_at=now, attempted_by=SYSTEM_AUTO_SEND_LABEL,
                    ))
                    db.commit()
                    sent.append(
                        {"member_id": str(member.id), "challenge_id": str(challenge.id), "milestone": milestone}
                    )
                except EmailSendError as exc:
                    db.rollback()
                    errors.append(f"member {member.id} challenge {challenge.id} {milestone}: {exc}")

    return {"sent": sent, "queued": queued, "errors": errors}


def send_one_pending_reminder(db: Session, reminder: ReminderLog, tenant: Tenant, attempted_by: str) -> None:
    """Sends (or retries) a single pending/failed reminder now — used by
    both the manual "Send" button and a retry after a prior failure.
    Raises EmailSendError/EmailConfigError on failure, after recording it
    (mirrors reports.py's _send_and_record shape)."""
    member = db.get(Member, reminder.member_id)
    try:
        send_email(tenant, member.email, subject=reminder.subject or "", body=reminder.body or "")
    except (EmailConfigError, EmailSendError) as exc:
        reminder.status = "failed"
        reminder.error_detail = str(exc)
        reminder.attempted_by = attempted_by
        db.commit()
        raise
    reminder.status = "sent"
    reminder.sent_at = datetime.now(timezone.utc)
    reminder.error_detail = None
    reminder.attempted_by = attempted_by
    db.commit()
