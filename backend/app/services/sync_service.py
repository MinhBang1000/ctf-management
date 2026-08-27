import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.adapters.base import AdapterError, PlatformAdapter
from app.adapters.registry import get_adapter
from app.models.challenge import Challenge
from app.models.member import Member
from app.models.member_platform_account import MemberPlatformAccount
from app.models.platform import Platform
from app.models.progress import DetectedBy, Progress, ProgressStatus
from app.models.sync_log import SyncLog

# Early vs Done isn't defined anywhere in the PRD text available to us —
# confirmed with the user: a fixed cutoff before the deadline. Not backed
# by a PRD citation beyond that confirmation; adjust freely if the real
# product definition turns out to differ.
EARLY_THRESHOLD = timedelta(hours=48)

# Manual "Sync now" cooldown per §4.2.1 step 7 ("tối thiểu 15 phút/lần/Lab").
# This is a per-Lab check against sync_logs, not the shared cross-tenant
# rate limiter (Redis token bucket, app/core/rate_limiter.py).
SYNC_COOLDOWN = timedelta(minutes=15)

CONFLICT_NOTE_MARKER = "[sync conflict]"


class SyncCooldownError(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Sync on cooldown, retry after {retry_after_seconds}s")


def classify_status(completed_at: datetime, deadline_at: datetime) -> ProgressStatus:
    if completed_at <= deadline_at - EARLY_THRESHOLD:
        return ProgressStatus.EARLY
    if completed_at <= deadline_at:
        return ProgressStatus.DONE
    return ProgressStatus.LATE


def _with_conflict_note(existing_note: str | None, message: str) -> str:
    """Replaces any previous sync-conflict line rather than accumulating a
    duplicate one on every run; keeps whatever else the Admin wrote."""
    marker_line = f"{CONFLICT_NOTE_MARKER} {message}"
    if not existing_note:
        return marker_line
    kept = [ln for ln in existing_note.splitlines() if not ln.startswith(CONFLICT_NOTE_MARKER)]
    kept.append(marker_line)
    return "\n".join(kept)


def sync_one_member(
    db: Session,
    member_id: uuid.UUID,
    external_user_id: str,
    adapter: PlatformAdapter,
    challenges_by_ext_id: dict[str, Challenge],
) -> dict:
    """The PRD §4.2.1 diff algorithm for one Member. Shared by both the
    manual /sync-now endpoint and the scheduled Celery task (Phase 3) —
    written once, called from both, never duplicated.

    Never raises: any adapter failure becomes an "error" entry in the
    returned dict, so a group/chord of these (Celery) can't produce a
    ChordError from one bad Member breaking the whole batch."""
    try:
        validations = adapter.get_user_completed_challenges(external_user_id)
    except AdapterError as exc:
        return {"member_id": str(member_id), "updated": [], "conflicts": [], "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - must never propagate out of here
        return {"member_id": str(member_id), "updated": [], "conflicts": [], "error": f"unexpected error: {exc}"}

    validations_by_ext_id = {v.id_challenge: v for v in validations}
    updated: list[dict] = []
    conflicts: list[dict] = []

    for ext_id, challenge in challenges_by_ext_id.items():
        validation = validations_by_ext_id.get(ext_id)
        if not validation or not validation.completed_at:
            continue  # not solved yet, per Root Me

        progress = (
            db.query(Progress)
            .filter(Progress.member_id == member_id, Progress.challenge_id == challenge.id)
            .first()
        )
        if progress and progress.status == ProgressStatus.DONE:
            continue  # already resolved, nothing to recheck (§4.2.1 step 4)
        if progress and progress.detected_by == DetectedBy.MANUAL:
            # Manual override wins — never overwrite. Log it on the record
            # itself so the Lab Admin sees the conflict even on a
            # scheduled run nobody is watching interactively (§4.2.1 step 5).
            progress.note = _with_conflict_note(
                progress.note,
                f"Root Me shows completed_at={validation.completed_at.isoformat()} but manual entry was kept.",
            )
            conflicts.append(
                {
                    "member_id": str(member_id),
                    "challenge_id": str(challenge.id),
                    "detected_completed_at": validation.completed_at.isoformat(),
                }
            )
            continue

        status = classify_status(validation.completed_at, challenge.deadline_at)
        if not progress:
            progress = Progress(member_id=member_id, challenge_id=challenge.id)
            db.add(progress)
        progress.status = status
        progress.completed_at = validation.completed_at
        progress.detected_by = DetectedBy.SYNC

        updated.append(
            {
                "member_id": str(member_id),
                "challenge_id": str(challenge.id),
                "status": status.value,
                "completed_at": validation.completed_at.isoformat(),
            }
        )

    return {"member_id": str(member_id), "updated": updated, "conflicts": conflicts, "error": None}


def get_challenges_by_ext_id(db: Session, tenant_id: uuid.UUID, platform_id: uuid.UUID) -> dict[str, Challenge]:
    challenges = (
        db.query(Challenge)
        .filter(
            Challenge.tenant_id == tenant_id,
            Challenge.platform_id == platform_id,
            Challenge.external_challenge_id.isnot(None),
        )
        .all()
    )
    return {c.external_challenge_id: c for c in challenges}


def run_sync_for_platform(db: Session, tenant_id: uuid.UUID, platform: Platform) -> dict:
    """Synchronous path used by the manual /sync-now endpoint: one DB
    session, one HTTP-bound loop over this Lab's members."""
    last_log = (
        db.query(SyncLog)
        .filter(SyncLog.tenant_id == tenant_id, SyncLog.platform_id == platform.id)
        .order_by(SyncLog.run_at.desc())
        .first()
    )
    if last_log:
        elapsed = datetime.now(timezone.utc) - last_log.run_at
        if elapsed < SYNC_COOLDOWN:
            raise SyncCooldownError(retry_after_seconds=int((SYNC_COOLDOWN - elapsed).total_seconds()))

    adapter = get_adapter(platform)

    accounts = (
        db.query(MemberPlatformAccount)
        .join(Member, Member.id == MemberPlatformAccount.member_id)
        .filter(
            Member.tenant_id == tenant_id,
            Member.active.is_(True),
            MemberPlatformAccount.platform_id == platform.id,
        )
        .all()
    )
    challenges_by_ext_id = get_challenges_by_ext_id(db, tenant_id, platform.id)

    updated: list[dict] = []
    conflicts: list[dict] = []
    errors: list[str] = []

    for account in accounts:
        result = sync_one_member(db, account.member_id, account.external_user_id, adapter, challenges_by_ext_id)
        updated.extend(result["updated"])
        conflicts.extend(result["conflicts"])
        if result["error"]:
            errors.append(f"member {result['member_id']}: {result['error']}")

    db.add(
        SyncLog(
            tenant_id=tenant_id,
            platform_id=platform.id,
            status="ok" if not errors else "partial_error",
            members_checked=len(accounts),
            errors="; ".join(errors) if errors else None,
        )
    )
    db.commit()

    return {
        "members_checked": len(accounts),
        "updated": updated,
        "conflicts": conflicts,
        "errors": errors,
    }
