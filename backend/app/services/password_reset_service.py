import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.core.templates import render_template
from app.db.session import bind_email_lookup_context, bind_password_reset_lookup_context, bind_tenant_context
from app.models.member import Member
from app.models.password_reset_token import PasswordResetToken
from app.models.tenant import Tenant
from app.services.email_service import EmailConfigError, EmailSendError, send_email


class InvalidResetTokenError(Exception):
    """Covers "no such token", "already used", and "expired" alike — never
    tell the caller which one, so a token can't be used to probe state."""


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def request_password_reset(db: Session, email: str) -> None:
    """§2 forgot-password, step 1. Deliberately behaves identically whether
    or not the email exists / has an active account — no account-
    enumeration signal via response shape or timing-sensitive branching."""
    bind_email_lookup_context(db)
    member = db.query(Member).filter(Member.email == email).first()
    if not member or not member.active:
        return

    bind_tenant_context(db, member.tenant_id)
    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            member_id=member.id,
            token_hash=_hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
    )
    db.commit()

    tenant = db.get(Tenant, member.tenant_id)
    reset_url = f"{settings.PUBLIC_APP_URL}/reset-password?token={raw_token}"
    body = render_template(
        "password_reset_email.txt.j2",
        member_name=member.full_name,
        email=member.email,
        reset_url=reset_url,
        expires_minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    )
    try:
        send_email(tenant, member.email, subject="Reset your HSLab CTF Classroom password", body=body)
    except (EmailConfigError, EmailSendError):
        # Same "always looks like it worked" contract as above — an admin
        # would notice a broken SMTP config via Settings' test-email
        # button or job history, not via this endpoint's response.
        pass


def reset_password_with_token(db: Session, raw_token: str, new_password: str) -> None:
    """§2 forgot-password, step 2. Raises InvalidResetTokenError for any
    of "no such token" / "already used" / "expired" — see that class."""
    bind_password_reset_lookup_context(db)
    token_hash = _hash_token(raw_token)
    token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    now = datetime.now(timezone.utc)
    if not token or token.used_at is not None or token.expires_at < now:
        raise InvalidResetTokenError("This reset link is invalid or has expired.")

    member = db.get(Member, token.member_id)
    if not member:
        raise InvalidResetTokenError("This reset link is invalid or has expired.")

    member.password_hash = hash_password(new_password)
    member.token_version += 1  # invalidate every session issued before this reset
    token.used_at = now
    db.commit()
