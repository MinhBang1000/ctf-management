from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_member, get_db
from app.core.security import create_access_token, verify_password
from app.db.session import bind_email_lookup_context
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.auth import LoginRequest, MemberMe

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "access_token"


@router.post("/login", response_model=MemberMe)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    # System resolves the user's Lab purely from their (globally unique)
    # email, per PRD §6.1 — no manual Lab selection at login. This is a
    # genuinely cross-tenant lookup by design, so it needs a narrow,
    # SELECT-only RLS bypass (Phase 6) — nothing else about this request
    # is exempted; tenant_id for everything downstream still comes only
    # from the verified token created below, never from this lookup's
    # caller-supplied email.
    bind_email_lookup_context(db)
    member = db.query(Member).filter(Member.email == payload.email).first()
    if not member or not member.active or not verify_password(payload.password, member.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    tenant = db.get(Tenant, member.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lab is inactive")

    token = create_access_token({"sub": str(member.id), "tenant_id": str(member.tenant_id), "scope": "member"})
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV == "production",
        max_age=60 * 60 * 12,
    )
    return MemberMe(
        id=member.id,
        tenant_id=member.tenant_id,
        tenant_name=tenant.name,
        full_name=member.full_name,
        email=member.email,
        role=member.role,
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=MemberMe)
def me(member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, member.tenant_id)
    return MemberMe(
        id=member.id,
        tenant_id=member.tenant_id,
        tenant_name=tenant.name,
        full_name=member.full_name,
        email=member.email,
        role=member.role,
    )
