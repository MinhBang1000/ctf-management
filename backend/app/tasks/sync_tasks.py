import logging
import uuid

from celery import chord, group

from app.adapters.base import AdapterError
from app.adapters.registry import get_adapter
from app.celery_app import celery_app
from app.db.session import SessionLocal, tenant_session
from app.models.member import Member
from app.models.member_platform_account import MemberPlatformAccount
from app.models.platform import Platform
from app.models.sync_log import SyncLog
from app.models.tenant import Tenant
from app.services.alerting_service import check_and_alert
from app.services.sync_service import get_challenges_by_ext_id, sync_one_member

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.sync_tasks.sync_all_tenants")
def sync_all_tenants() -> None:
    """Celery beat entrypoint (PRD §4.2.1 step 2) — loops every active
    Tenant, resolves its focus Platform, and fans out one sync_member_task
    per linked active Member. No resolve-on-sync step: external_user_id
    is already required and stored at Member creation (Phase 1) — this
    reads it straight from member_platform_accounts.
    """
    db = SessionLocal()
    try:
        tenant_ids = [t.id for t in db.query(Tenant).filter(Tenant.is_active.is_(True)).all()]
    finally:
        db.close()

    for tenant_id in tenant_ids:
        _dispatch_tenant_sync(tenant_id)


def _dispatch_tenant_sync(tenant_id: uuid.UUID) -> None:
    with tenant_session(tenant_id) as db:
        platform = (
            db.query(Platform)
            .filter(Platform.tenant_id == tenant_id, Platform.is_focus.is_(True), Platform.is_active.is_(True))
            .first()
        )
        if not platform:
            # Shouldn't happen in practice (every Lab is seeded with one
            # focus platform, and /focus always keeps exactly one active) —
            # no platform_id to attach a sync_log row to, so just log.
            logger.warning("Tenant %s has no active focus platform, skipping scheduled sync", tenant_id)
            return

        if not platform.has_credentials:
            # Hardening: /focus already refuses to point at an
            # unconfigured platform, but a Lab could still remove
            # credentials after the fact. Surface this via sync_log so
            # the dashboard (§6.12, Phase 3 requirement 7) can show it —
            # never let this fail the whole run.
            db.add(
                SyncLog(
                    tenant_id=tenant_id,
                    platform_id=platform.id,
                    status="skipped_not_configured",
                    members_checked=0,
                    errors="Focus platform has no credentials configured",
                )
            )
            db.commit()
            return

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
        if not accounts:
            db.add(
                SyncLog(tenant_id=tenant_id, platform_id=platform.id, status="ok", members_checked=0, errors=None)
            )
            db.commit()
            return

        platform_id = platform.id
        member_args = [(str(a.member_id), a.external_user_id) for a in accounts]

    # Fan-out/fan-in: one task per Member (isolation — one Member's
    # failure never aborts another's, or the run), joined by a callback
    # that writes exactly one sync_log row for this tenant+platform+run.
    header = group(
        sync_member_task.s(str(tenant_id), str(platform_id), member_id, external_user_id)
        for member_id, external_user_id in member_args
    )
    chord(header)(finalize_sync_log_task.s(str(tenant_id), str(platform_id)))


@celery_app.task(name="app.tasks.sync_tasks.sync_member_task")
def sync_member_task(tenant_id: str, platform_id: str, member_id: str, external_user_id: str) -> dict:
    """One Member's sync, run as an independent Celery task.

    MUST NEVER RAISE: this task is one member of a Celery `group` joined
    by a `chord` — an uncaught exception here produces a ChordError that
    breaks the whole run's aggregation, defeating the per-member isolation
    this design exists to guarantee. Every failure path returns a result
    dict with an "error" field instead. sync_one_member already has its
    own internal try/except for the same reason (defense in depth, in
    case it's ever called from elsewhere without this wrapper).
    """
    try:
        with tenant_session(tenant_id) as db:
            try:
                platform = db.get(Platform, uuid.UUID(platform_id))
                if not platform:
                    return {"member_id": member_id, "updated": [], "conflicts": [], "error": "platform not found"}
                adapter = get_adapter(platform)
            except AdapterError as exc:
                return {"member_id": member_id, "updated": [], "conflicts": [], "error": str(exc)}

            challenges_by_ext_id = get_challenges_by_ext_id(db, uuid.UUID(tenant_id), uuid.UUID(platform_id))
            result = sync_one_member(db, uuid.UUID(member_id), external_user_id, adapter, challenges_by_ext_id)
            db.commit()
            return result
    except Exception as exc:  # noqa: BLE001 - see docstring: must always return, never raise
        logger.exception("sync_member_task unexpected failure for member %s", member_id)
        return {"member_id": member_id, "updated": [], "conflicts": [], "error": f"unexpected error: {exc}"}


@celery_app.task(name="app.tasks.sync_tasks.finalize_sync_log_task")
def finalize_sync_log_task(results: list[dict], tenant_id: str, platform_id: str) -> None:
    """Chord callback: aggregates every sync_member_task result for this
    run into exactly one sync_log row (PRD §4.2.1 step 6)."""
    try:
        with tenant_session(tenant_id) as db:
            errors = [f"member {r['member_id']}: {r['error']}" for r in results if r.get("error")]
            db.add(
                SyncLog(
                    tenant_id=uuid.UUID(tenant_id),
                    platform_id=uuid.UUID(platform_id),
                    status="ok" if not errors else "partial_error",
                    members_checked=len(results),
                    errors="; ".join(errors) if errors else None,
                )
            )
            db.commit()
            # Phase 6 alerting: checks trailing sync_log history for this
            # tenant and emails Super Admin once if it just crossed
            # ALERT_FAILURE_THRESHOLD consecutive partial_error runs.
            check_and_alert(db, uuid.UUID(tenant_id), "sync")
    except Exception:  # noqa: BLE001 - never let the aggregation step crash the scheduler
        logger.exception("finalize_sync_log_task failed to write sync_log for tenant %s", tenant_id)
