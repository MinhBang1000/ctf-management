from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.templates import render_template
from app.models.challenge import Challenge
from app.models.member import Member
from app.models.platform import Platform
from app.models.progress import Progress, ProgressStatus
from app.models.report import Report
from app.models.semester import Semester
from app.models.tenant import Tenant


def _participating_members(db: Session, tenant_id, as_of: datetime) -> list[Member]:
    """§13 — every Member who had joined the Lab by `as_of`, regardless of
    whether they're active *now*. Filtering by *current* `active` status
    (the old behavior) is exactly the bug §13 describes: a Member active
    all semester but deactivated afterward would vanish from a report
    generated later for that same semester.

    There's no stored history of exactly when each Member was active on
    any given past date, so `joined_at` is the closest available "was
    actually part of the Lab at the time" signal — it correctly excludes
    a genuinely new Member with zero relationship to a historical period
    (someone who joined well after a semester ended), which is the other
    half of what §13 requires ("Exclude Members who never participated").
    """
    return db.query(Member).filter(Member.tenant_id == tenant_id, Member.joined_at <= as_of).all()


def _week_bounds(reference: date, weeks_ago: int) -> tuple[date, date]:
    """Monday-Sunday calendar week containing `reference`, offset back by
    `weeks_ago` weeks. Deliberately calendar-based, not Challenge.week_number
    — that field is an admin-assigned label, not guaranteed calendar-aligned
    (flagged in the Phase 4 plan)."""
    monday = reference - timedelta(days=reference.weekday()) - timedelta(weeks=weeks_ago)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _day_bounds_utc(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, time.min, tzinfo=timezone.utc),
        datetime.combine(end, time.max, tzinfo=timezone.utc),
    )


def generate_weekly_report_for_tenant(db: Session, tenant: Tenant) -> Report | None:
    """PRD §6.8: aggregates last week's Done/Late/Missing + this week's
    Early list into a draft Report — sends nothing (approve flow does that).
    Returns None if the tenant has no Semester to attach the report to."""
    today = datetime.now(timezone.utc).date()
    prev_start, prev_end = _week_bounds(today, weeks_ago=1)
    curr_start, curr_end = _week_bounds(today, weeks_ago=0)
    prev_from, prev_to = _day_bounds_utc(prev_start, prev_end)
    curr_from, curr_to = _day_bounds_utc(curr_start, curr_end)

    semester = (
        db.query(Semester).filter(Semester.tenant_id == tenant.id, Semester.is_current.is_(True)).first()
        or db.query(Semester).filter(Semester.tenant_id == tenant.id).order_by(Semester.start_date.desc()).first()
    )
    if not semester:
        return None  # nothing to attach the report to yet

    # §9 — idempotency: never insert a second report for the same
    # (tenant, semester, type, period) — the DB-level unique constraint
    # backs this up, but checking here lets a repeated call *update* the
    # existing draft (still-current numbers) instead of erroring, and
    # lets an already-sent report come back untouched instead of being
    # silently overwritten.
    existing = (
        db.query(Report)
        .filter(
            Report.tenant_id == tenant.id,
            Report.semester_id == semester.id,
            Report.type == "weekly",
            Report.period_start == prev_start,
            Report.period_end == prev_end,
        )
        .first()
    )
    if existing and existing.status == "sent":
        return existing

    members = _participating_members(db, tenant.id, curr_to)

    prev_challenges = (
        db.query(Challenge)
        .filter(Challenge.tenant_id == tenant.id, Challenge.deadline_at.between(prev_from, prev_to))
        .all()
    )

    completed_count = late_count = missing_count = 0
    late_items: list[dict] = []
    missing_items: list[dict] = []

    for challenge in prev_challenges:
        for member in members:
            progress = (
                db.query(Progress)
                .filter(Progress.member_id == member.id, Progress.challenge_id == challenge.id)
                .first()
            )
            status = progress.status if progress else None
            if status in (ProgressStatus.DONE, ProgressStatus.EARLY):
                completed_count += 1
            elif status == ProgressStatus.LATE:
                late_count += 1
                late_items.append({"member_name": member.full_name, "challenge_title": challenge.title})
            else:  # ProgressStatus.MISSING or no Progress row at all
                missing_count += 1
                missing_items.append({"member_name": member.full_name, "challenge_title": challenge.title})

    total_count = completed_count + late_count + missing_count
    completion_pct = round(completed_count / total_count * 100, 1) if total_count else 0.0

    curr_challenges = (
        db.query(Challenge)
        .filter(Challenge.tenant_id == tenant.id, Challenge.deadline_at.between(curr_from, curr_to))
        .all()
    )
    early_items: list[dict] = []
    for challenge in curr_challenges:
        for member in members:
            progress = (
                db.query(Progress)
                .filter(Progress.member_id == member.id, Progress.challenge_id == challenge.id)
                .first()
            )
            if progress and progress.status == ProgressStatus.EARLY:
                early_items.append({"member_name": member.full_name, "challenge_title": challenge.title})

    content = render_template(
        "weekly_report_email.txt.j2",
        tenant_name=tenant.name,
        period_start=prev_start.isoformat(),
        period_end=prev_end.isoformat(),
        current_period_start=curr_start.isoformat(),
        current_period_end=curr_end.isoformat(),
        completed_count=completed_count,
        total_count=total_count,
        completion_pct=completion_pct,
        late_count=late_count,
        missing_count=missing_count,
        early_items=early_items,
        late_items=late_items,
        missing_items=missing_items,
    )

    if existing:
        # existing.status == "draft" here (the "sent" case already
        # returned above) — refresh it in place rather than inserting a
        # second row for the same period.
        existing.content = content
        existing.generated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    report = Report(
        tenant_id=tenant.id,
        semester_id=semester.id,
        type="weekly",
        period_start=prev_start,
        period_end=prev_end,
        generated_at=datetime.now(timezone.utc),
        status="draft",
        content=content,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def compute_semester_report_data(db: Session, tenant: Tenant, semester: Semester) -> dict:
    """PRD §6.11 (v0.2 spec, restated by the user): per-member Done/Late/
    Missing + cumulative Challenge.points (our own point value, NOT Root
    Me's global score — see Phase 5 plan) + internal ranking, lab-wide
    weekly trend grouped by Challenge.week_number (deliberately NOT the
    calendar-week grouping Phase 4's weekly report uses — different report,
    different natural unit), and an explicit platform-switch annotation
    when the semester's challenges span more than one Platform.

    Challenge.platform_id is fixed per-challenge at creation time and
    never changes retroactively (PRD design principle #6), so grouping by
    it directly is suffient — no separate "focus history" table needed.
    """
    members = sorted(
        _participating_members(db, tenant.id, _day_bounds_utc(semester.end_date, semester.end_date)[1]),
        key=lambda m: m.full_name,
    )
    challenges = (
        db.query(Challenge).filter(Challenge.semester_id == semester.id).order_by(Challenge.week_number).all()
    )

    platform_ids = {c.platform_id for c in challenges}
    platforms = {p.id: p for p in db.query(Platform).filter(Platform.id.in_(platform_ids)).all()} if platform_ids else {}
    spans_switch = len(platform_ids) > 1

    challenge_ids = [c.id for c in challenges]
    progress_rows = db.query(Progress).filter(Progress.challenge_id.in_(challenge_ids)).all() if challenge_ids else []
    progress_by_pair = {(p.member_id, p.challenge_id): p for p in progress_rows}

    weeks: dict[int, list[Challenge]] = {}
    for c in challenges:
        weeks.setdefault(c.week_number, []).append(c)

    weekly_trend = []
    for week_number in sorted(weeks):
        week_challenges = weeks[week_number]
        week_platform_names = sorted(
            {platforms[c.platform_id].name for c in week_challenges if c.platform_id in platforms}
        )
        total_pairs = len(week_challenges) * len(members)
        completed_pairs = sum(
            1
            for c in week_challenges
            for m in members
            if (p := progress_by_pair.get((m.id, c.id))) and p.status in (ProgressStatus.DONE, ProgressStatus.EARLY)
        )
        weekly_trend.append(
            {
                "week_number": week_number,
                "platform_names": week_platform_names,
                "challenge_count": len(week_challenges),
                "completion_pct": round(completed_pairs / total_pairs * 100, 1) if total_pairs else 0.0,
            }
        )

    member_rows = []
    for m in members:
        done = late = missing = 0
        points = 0
        by_platform: dict[str, dict] = {}
        for c in challenges:
            platform_name = platforms[c.platform_id].name if c.platform_id in platforms else "Unknown"
            bucket = by_platform.setdefault(platform_name, {"done": 0, "late": 0, "missing": 0, "points": 0})
            progress = progress_by_pair.get((m.id, c.id))
            status = progress.status if progress else None
            if status in (ProgressStatus.DONE, ProgressStatus.EARLY):
                done += 1
                bucket["done"] += 1
                if c.points:
                    points += c.points
                    bucket["points"] += c.points
            elif status == ProgressStatus.LATE:
                late += 1
                bucket["late"] += 1
            else:  # ProgressStatus.MISSING or no Progress row at all
                missing += 1
                bucket["missing"] += 1

        member_rows.append(
            {
                "member_id": str(m.id),
                "member_name": m.full_name,
                "done_count": done,
                "late_count": late,
                "missing_count": missing,
                "cumulative_points": points,
                # Only populated when the semester actually spans a switch
                # — keeps the common single-platform case uncluttered.
                "by_platform": (
                    [{"platform_name": name, **stats} for name, stats in by_platform.items()] if spans_switch else []
                ),
            }
        )

    member_rows.sort(key=lambda r: (-r["cumulative_points"], r["member_name"]))
    for rank, row in enumerate(member_rows, start=1):
        row["rank"] = rank

    return {
        "semester_name": semester.name,
        "period_start": semester.start_date.isoformat(),
        "period_end": semester.end_date.isoformat(),
        "platforms_used": [{"id": str(pid), "name": platforms[pid].name} for pid in platform_ids if pid in platforms],
        "spans_platform_switch": spans_switch,
        "weekly_trend": weekly_trend,
        "members": member_rows,
    }


def generate_semester_report_for_tenant(db: Session, tenant: Tenant, semester: Semester) -> Report:
    """Manual trigger only (Lab Leader, from Semester Management) — never
    fires automatically on semester end_date, since closing out a
    semester is an administrative decision (Phase 5 plan).

    Same idempotency contract as generate_weekly_report_for_tenant, for
    the same DB constraint (uq_report_tenant_semester_type_period, which
    doesn't distinguish report type): repeated generation refreshes an
    existing draft in place rather than erroring or duplicating, and an
    already-sent semester report comes back untouched.
    """
    existing = (
        db.query(Report)
        .filter(
            Report.tenant_id == tenant.id,
            Report.semester_id == semester.id,
            Report.type == "semester",
            Report.period_start == semester.start_date,
            Report.period_end == semester.end_date,
        )
        .first()
    )
    if existing and existing.status == "sent":
        return existing

    data = compute_semester_report_data(db, tenant, semester)
    content = render_template("semester_report_email.txt.j2", tenant_name=tenant.name, **data)

    if existing:
        existing.content = content
        existing.data = data
        existing.generated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    report = Report(
        tenant_id=tenant.id,
        semester_id=semester.id,
        type="semester",
        period_start=semester.start_date,
        period_end=semester.end_date,
        generated_at=datetime.now(timezone.utc),
        status="draft",
        content=content,
        data=data,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
