import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.templates import render_template
from app.models.challenge import Challenge
from app.models.member import Member
from app.models.progress import Progress, ProgressStatus
from app.models.reminder_log import ReminderLog
from app.models.tenant import Tenant
from app.services.email_service import EmailConfigError, EmailSendError, get_smtp_config, send_email

# (days_before_deadline, milestone_label) — separate reminder_log entries
# per milestone so T-3 and T-1 are independently deduplicated.
MILESTONES = [(3, "T-3"), (1, "T-1")]


def send_reminders_for_tenant(db: Session, tenant: Tenant) -> dict:
    """PRD §6.7: T-3/T-1 reminders straight to Members who haven't
    completed a Challenge, no draft/approve gate (that gate is for
    communication leaving the Lab, not internal member reminders).

    "not_started or late" (as specified) maps onto our status enum as:
    no Progress row at all, or status in (missing, late) — there is no
    literal not_started value, flagged in the Phase 4 plan."""
    sent: list[dict] = []
    errors: list[str] = []

    try:
        # Resolve once per tenant rather than once per recipient — if SMTP
        # isn't configured at all, every send would fail identically.
        get_smtp_config(tenant)
    except EmailConfigError as exc:
        return {"sent": [], "errors": [str(exc)]}

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

                already_sent = (
                    db.query(ReminderLog)
                    .filter(
                        ReminderLog.member_id == member.id,
                        ReminderLog.challenge_id == challenge.id,
                        ReminderLog.milestone == milestone,
                    )
                    .first()
                )
                if already_sent:
                    continue

                try:
                    body = render_template(
                        "reminder_email.txt.j2",
                        member_name=member.full_name,
                        challenge_title=challenge.title,
                        deadline=challenge.deadline_at.strftime("%Y-%m-%d %H:%M UTC"),
                        days_left=days_before,
                        milestone=milestone,
                    )
                    send_email(
                        tenant,
                        member.email,
                        subject=f"Reminder: \"{challenge.title}\" due in {days_before} day(s)",
                        body=body,
                    )
                    db.add(
                        ReminderLog(
                            member_id=member.id, challenge_id=challenge.id, milestone=milestone, channel="email"
                        )
                    )
                    db.commit()
                    sent.append(
                        {"member_id": str(member.id), "challenge_id": str(challenge.id), "milestone": milestone}
                    )
                except EmailSendError as exc:
                    db.rollback()
                    errors.append(f"member {member.id} challenge {challenge.id} {milestone}: {exc}")

    return {"sent": sent, "errors": errors}
