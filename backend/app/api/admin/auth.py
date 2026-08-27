from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_super_admin, get_db
from app.core.security import create_access_token, verify_password
from app.models.super_admin import SuperAdmin
from app.schemas.auth import LoginRequest, SuperAdminMe

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

COOKIE_NAME = "access_token"


@router.post("/login", response_model=SuperAdminMe)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    admin = db.query(SuperAdmin).filter(SuperAdmin.email == payload.email).first()
    if not admin or not admin.active or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(admin.id), "scope": "super_admin"})
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV == "production",
        max_age=60 * 60 * 12,
    )
    return admin


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=SuperAdminMe)
def me(admin: SuperAdmin = Depends(get_current_super_admin)):
    return admin
