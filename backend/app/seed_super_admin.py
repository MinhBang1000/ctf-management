"""Creates the first Super Admin account from SUPER_ADMIN_BOOTSTRAP_EMAIL /
SUPER_ADMIN_BOOTSTRAP_PASSWORD in .env. The PRD has no self-service Super
Admin signup (§9 open question 4 assumes manual-only onboarding by Super
Admin) and SUPER_ADMIN is a standalone table (§5.1) with no seed data, so
this script is the one-time bootstrap step. Safe to re-run: no-ops if an
account with that email already exists.

Usage: python -m app.seed_super_admin
"""
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.super_admin import SuperAdmin


def main() -> None:
    if not settings.SUPER_ADMIN_BOOTSTRAP_EMAIL or not settings.SUPER_ADMIN_BOOTSTRAP_PASSWORD:
        raise SystemExit(
            "Set SUPER_ADMIN_BOOTSTRAP_EMAIL and SUPER_ADMIN_BOOTSTRAP_PASSWORD in .env first."
        )

    db = SessionLocal()
    try:
        existing = db.query(SuperAdmin).filter(SuperAdmin.email == settings.SUPER_ADMIN_BOOTSTRAP_EMAIL).first()
        if existing:
            print(f"Super Admin {settings.SUPER_ADMIN_BOOTSTRAP_EMAIL} already exists, skipping.")
            return
        admin = SuperAdmin(
            email=settings.SUPER_ADMIN_BOOTSTRAP_EMAIL,
            password_hash=hash_password(settings.SUPER_ADMIN_BOOTSTRAP_PASSWORD),
            active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Created Super Admin {settings.SUPER_ADMIN_BOOTSTRAP_EMAIL}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
