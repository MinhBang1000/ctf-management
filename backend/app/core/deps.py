import uuid
from typing import Generator

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal, bind_super_admin_context, bind_tenant_context
from app.models.member import Member, MemberRole
from app.models.super_admin import SuperAdmin


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _decode_or_401(token: str | None) -> dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return payload


def get_current_member(
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None),
) -> Member:
    """Resolves the logged-in Lab user (lab_leader/presenter/member).

    tenant_id is ALWAYS taken from the verified JWT/member row, never from
    client input (PRD §3.2).

    Phase 6 RLS: sets the Postgres session's tenant context from the JWT's
    own tenant_id claim BEFORE even the Member row lookup — that lookup is
    itself subject to Row-Level Security once RLS is enabled, so the
    context has to exist before this function's first query, not after.
    Sourced from the verified token, never from client input, same as
    every other tenant_id use in this codebase. Uses bind_tenant_context
    (not a one-time SET LOCAL) so it stays in effect even if this
    request's session commits more than once.
    """
    payload = _decode_or_401(access_token)
    if payload.get("scope") != "member":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a Lab account")
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    bind_tenant_context(db, tenant_id)
    member = db.get(Member, uuid.UUID(payload["sub"]))
    if not member or not member.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or inactive")
    # §2 — a password change/reset bumps token_version; any JWT issued
    # before that (this one included, if it predates the bump) must stop
    # working immediately, not just at its natural expiry.
    if payload.get("tv") != member.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalidated, please sign in again")
    return member


def get_current_super_admin(
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None),
) -> SuperAdmin:
    """Phase 6 RLS: marks this session as a Super Admin session. This does
    NOT grant blanket cross-tenant access — only the specific tables/
    operations that already legitimately need it (Platform/SyncLog reads
    for the dashboard, Member inserts for create_lab provisioning) have a
    matching bypass policy. Everything else stays strictly tenant-scoped,
    matching the confirmed "no impersonation" design (PRD §9 item 6)."""
    payload = _decode_or_401(access_token)
    if payload.get("scope") != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a Super Admin account")
    bind_super_admin_context(db)
    admin = db.get(SuperAdmin, uuid.UUID(payload["sub"]))
    if not admin or not admin.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or inactive")
    return admin


def require_roles(*roles: MemberRole):
    def _checker(member: Member = Depends(get_current_member)) -> Member:
        if member.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return member

    return _checker
