import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.adapters.base import AdapterError
from app.adapters.registry import ADAPTER_REGISTRY, get_adapter
from app.core.deps import get_current_member, get_db, require_roles
from app.models.member import Member, MemberRole
from app.models.platform import Platform
from app.schemas.platform import (
    ChallengeLookupResult,
    ChallengeSearchResultOut,
    PlatformCreate,
    PlatformOut,
    PlatformUpdate,
    ResolveUserResult,
    SyncNowResult,
    TestConnectionResult,
)
from app.services.audit_service import record_audit
from app.services.sync_service import SyncCooldownError, run_sync_for_platform

router = APIRouter(prefix="/platforms", tags=["platforms"])


def _query(db: Session, tenant_id: uuid.UUID):
    return db.query(Platform).filter(Platform.tenant_id == tenant_id)


def _get_or_404(db: Session, tenant_id: uuid.UUID, platform_id: uuid.UUID) -> Platform:
    platform = _query(db, tenant_id).filter(Platform.id == platform_id).first()
    if not platform:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
    return platform


@router.get("", response_model=list[PlatformOut])
def list_platforms(db: Session = Depends(get_db), current: Member = Depends(get_current_member)):
    return _query(db, current.tenant_id).all()


@router.post("", response_model=PlatformOut, status_code=status.HTTP_201_CREATED)
def create_platform(
    payload: PlatformCreate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    if payload.adapter_type not in ADAPTER_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No adapter implemented for adapter_type={payload.adapter_type!r}",
        )
    platform = Platform(
        tenant_id=current.tenant_id,
        name=payload.name,
        adapter_type=payload.adapter_type,
        base_url=payload.base_url,
        auth_config=payload.auth_config,
    )
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return platform


@router.patch("/{platform_id}", response_model=PlatformOut)
def update_platform(
    platform_id: uuid.UUID,
    payload: PlatformUpdate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    # is_focus is deliberately not settable here — switching focus is a
    # dedicated, atomic action (see set_focus below), not a casual field
    # toggle on a generic edit form (PRD §4.1).
    platform = _get_or_404(db, current.tenant_id, platform_id)
    data = payload.model_dump(exclude_unset=True)
    # §7 — "Invalidate the verification state when API credentials, base
    # URL, or adapter type change." adapter_type isn't editable via this
    # endpoint at all (not in PlatformUpdate), so only these two apply.
    if ("auth_config" in data and data["auth_config"] != platform.auth_config) or (
        "base_url" in data and data["base_url"] != platform.base_url
    ):
        platform.credentials_verified_at = None
    for key, value in data.items():
        setattr(platform, key, value)
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="platform.updated",
        summary=f"Updated platform {platform.name} ({', '.join(data.keys())})",
        target_type="platform",
        target_id=platform.id,
    )
    db.commit()
    db.refresh(platform)
    return platform


@router.post("/{platform_id}/focus", response_model=PlatformOut)
def set_focus(
    platform_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Explicit, atomic focus switch — unsets every other Platform in this
    Lab and sets this one, per PRD §4.1 ('chỉ 1 Platform is_focus=true
    trong phạm vi 1 Lab tại 1 thời điểm ... đổi focus ... có xác nhận').

    Hard server-side gate (Phase 3 hardening): a Platform with no
    credentials configured can never become focus, full stop — Phase 3's
    scheduler iterates every tenant's focus platform automatically, so an
    unconfigured one must be structurally unreachable, not just
    discouraged in the UI."""
    platform = _get_or_404(db, current.tenant_id, platform_id)
    if not platform.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot make this the focus platform: it is inactive.",
        )
    # §7 — "Require a successful verification before a platform can become
    # the focus" supersedes the old has_credentials-only check: a
    # credential can be present but never actually proven to work (or
    # proven once, then invalidated by an edit since — see update_platform).
    if platform.credentials_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot make this the focus platform: run Test Connection successfully first.",
        )
    _query(db, current.tenant_id).filter(Platform.id != platform_id).update({Platform.is_focus: False})
    platform.is_focus = True
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="platform.focus_changed",
        summary=f"Set {platform.name} as the focus platform",
        target_type="platform",
        target_id=platform.id,
    )
    db.commit()
    db.refresh(platform)
    return platform


@router.post("/{platform_id}/test-connection", response_model=TestConnectionResult)
def test_connection(
    platform_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Mirrors the PRD's own verified test (real call to /auteurs/1) —
    proves the saved credentials actually work before you rely on them."""
    platform = _get_or_404(db, current.tenant_id, platform_id)
    try:
        adapter = get_adapter(platform)
        adapter.get_user_completed_challenges("1")
    except AdapterError as exc:
        return TestConnectionResult(ok=False, detail=str(exc))
    # §7 — this timestamp, not "auth_config is non-empty", is what
    # set_focus actually checks now.
    platform.credentials_verified_at = datetime.now(timezone.utc)
    db.commit()
    return TestConnectionResult(ok=True, detail="Connection OK")


@router.post("/{platform_id}/sync-now", response_model=SyncNowResult)
def sync_now(
    platform_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Manual on-demand sync for debugging/testing the adapter end to end.
    No scheduling here — Celery beat + the shared cross-tenant rate
    limiter are Phase 3."""
    platform = _get_or_404(db, current.tenant_id, platform_id)
    try:
        result = run_sync_for_platform(db, current.tenant_id, platform)
    except SyncCooldownError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Sync ran recently for this Lab — try again in {exc.retry_after_seconds}s",
        ) from exc
    except AdapterError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return SyncNowResult(**result)


@router.get("/{platform_id}/resolve-user", response_model=ResolveUserResult)
def resolve_user(
    platform_id: uuid.UUID,
    username: str = Query(min_length=1),
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Backs the optional 'Tra cứu ID' helper on the Member form (PRD
    §6.3) — a lookup convenience only. The Admin still has to see and
    confirm the value; nothing here writes to the database."""
    platform = _get_or_404(db, current.tenant_id, platform_id)
    try:
        adapter = get_adapter(platform)
        external_user_id = adapter.resolve_user(username)
    except AdapterError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return ResolveUserResult(external_user_id=external_user_id, matched=external_user_id is not None)


@router.get("/{platform_id}/challenge-lookup", response_model=ChallengeLookupResult)
def challenge_lookup(
    platform_id: uuid.UUID,
    external_challenge_id: str = Query(min_length=1),
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Optional prefill helper for the Challenge form — not in the PRD
    explicitly, added as the natural counterpart to resolve-user, giving
    get_challenge_detail an actual caller."""
    platform = _get_or_404(db, current.tenant_id, platform_id)
    try:
        adapter = get_adapter(platform)
        detail = adapter.get_challenge_detail(external_challenge_id)
    except AdapterError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return ChallengeLookupResult(title=detail.title, category=detail.category, score=detail.score, url=detail.url)


@router.get("/{platform_id}/challenge-search", response_model=list[ChallengeSearchResultOut])
def challenge_search(
    platform_id: uuid.UUID,
    title: str = Query(min_length=1),
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """§1 — search by title instead of requiring a numeric ID up front.
    Every call goes through the backend (this endpoint), so the
    platform's api_key is never exposed to the browser."""
    platform = _get_or_404(db, current.tenant_id, platform_id)
    try:
        adapter = get_adapter(platform)
        results = adapter.search_challenges(title)
    except AdapterError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [
        ChallengeSearchResultOut(
            external_challenge_id=r.external_challenge_id, title=r.title, category=r.category, language=r.language, url=r.url
        )
        for r in results
    ]
