from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.base import AdapterError
from app.adapters.registry import get_adapter
from app.core.deps import get_current_member, get_db
from app.models.member import Member
from app.models.member_platform_account import MemberPlatformAccount
from app.models.platform import Platform
from app.schemas.member import PlatformAccountIn, PlatformAccountOut
from app.services.audit_service import record_audit

router = APIRouter(prefix="/me", tags=["self-service"])


@router.put("/platform-accounts", response_model=list[PlatformAccountOut])
def update_own_platform_accounts(
    accounts: list[PlatformAccountIn],
    db: Session = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """§5 self-service — every role manages their OWN linked Root Me
    identity this way; `current` comes only from the verified JWT
    (app.core.deps), never a URL param, so there's no way to point this
    at anyone else's account. Deliberately separate from the Lab-Leader-
    only PUT /members/{id}/platform-accounts, which manages *other*
    members' accounts.

    Validation is best-effort ("when the platform supports it") and never
    blocks the save: unlike the Lab-Leader "Tra cứu ID" flow (a second
    person reviews the value), there's nobody else to defer to here, and
    a resolver hiccup shouldn't lock someone out of saving their own
    correct information — a mismatch is only noted in the audit trail.
    """
    warnings: list[str] = []
    for acc in accounts:
        platform = (
            db.query(Platform).filter(Platform.id == acc.platform_id, Platform.tenant_id == current.tenant_id).first()
        )
        if not platform:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Platform {acc.platform_id} not found in this Lab"
            )
        try:
            resolved_id = get_adapter(platform).resolve_user(acc.external_username)
        except AdapterError:
            resolved_id = None
        if resolved_id is not None and resolved_id != acc.external_user_id:
            warnings.append(
                f"{platform.name}: resolves '{acc.external_username}' to id {resolved_id}, not the entered {acc.external_user_id}"
            )

    db.query(MemberPlatformAccount).filter(MemberPlatformAccount.member_id == current.id).delete()
    for acc in accounts:
        db.add(
            MemberPlatformAccount(
                member_id=current.id,
                platform_id=acc.platform_id,
                external_username=acc.external_username,
                external_user_id=acc.external_user_id,
            )
        )
    summary = f"{current.email} updated their own platform accounts ({len(accounts)} linked)"
    if warnings:
        summary += " — validation warnings: " + "; ".join(warnings)
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="member.self_platform_accounts_updated",
        summary=summary,
        target_type="member",
        target_id=current.id,
    )
    db.commit()
    return db.query(MemberPlatformAccount).filter(MemberPlatformAccount.member_id == current.id).all()
