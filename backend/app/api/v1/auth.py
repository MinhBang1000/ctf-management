from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_member, get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import bind_email_lookup_context
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.auth import ChangePasswordRequest, ForgotPasswordRequest, LoginRequest, MemberMe, ResetPasswordRequest
from app.services.password_reset_service import InvalidResetTokenError, request_password_reset, reset_password_with_token

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

    token = create_access_token(
        {"sub": str(member.id), "tenant_id": str(member.tenant_id), "scope": "member", "tv": member.token_version}
    )
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


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    """§2 — self-service change, for every role (Lab Leader included, per
    the explicit addendum to REQUIRED_FEATURES.md §2/§5)."""
    if not verify_password(payload.current_password, member.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    member.password_hash = hash_password(payload.new_password)
    member.token_version += 1
    db.commit()

    # This request's own cookie is now for a stale token_version — reissue
    # one immediately so the caller isn't logged out by their own action.
    token = create_access_token(
        {"sub": str(member.id), "tenant_id": str(member.tenant_id), "scope": "member", "tv": member.token_version}
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV == "production",
        max_age=60 * 60 * 12,
    )
    return {"ok": True}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    request_password_reset(db, payload.email)
    # Same response whether or not the email exists/has an active account
    # — see request_password_reset's own docstring for why.
    return {"detail": "If that email exists, a password reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        reset_password_with_token(db, payload.token, payload.new_password)
    except InvalidResetTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"ok": True}
