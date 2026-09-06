import uuid
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _bind_session_var(session: Session, sql: str, params: dict | None = None) -> None:
    """Registers a SET LOCAL to re-run every time a new transaction begins
    on this session — not just once.

    A GUC set via SET LOCAL only lasts one transaction. If the session's
    caller commits more than once (record_job_run does: write the row,
    commit, then check_and_alert queries again), a one-time SET LOCAL at
    session-open silently stops applying after the first commit — and
    because of the NULLIF bug found in the RLS migration (a touched-then-
    reverted custom GUC reads back as '', not NULL), that doesn't error,
    it just quietly returns zero rows. Hooking after_begin makes the
    context "sticky" for the session's full lifetime instead of assuming
    single-commit usage everywhere.
    """

    def _set(_session, _transaction, connection):
        connection.execute(text(sql), params or {})

    event.listen(session, "after_begin", _set)


def bind_tenant_context(session: Session, tenant_id: uuid.UUID | str) -> None:
    _bind_session_var(session, "SET LOCAL app.current_tenant_id = :tid", {"tid": str(tenant_id)})


def bind_super_admin_context(session: Session) -> None:
    _bind_session_var(session, "SET LOCAL app.is_super_admin = 'true'")


def bind_email_lookup_context(session: Session) -> None:
    _bind_session_var(session, "SET LOCAL app.is_email_lookup = 'true'")


def bind_password_reset_lookup_context(session: Session) -> None:
    """§2 forgot-password: the one step where the caller has a raw reset
    token but the tenant isn't known yet (can't bind_tenant_context before
    finding which Member the token belongs to) — same shape as
    bind_email_lookup_context, narrow and single-purpose."""
    _bind_session_var(session, "SET LOCAL app.is_password_reset_lookup = 'true'")


def enable_email_lookup_now(session: Session) -> None:
    """One-shot version of bind_email_lookup_context, for the CURRENT
    transaction only — not the next one.

    bind_email_lookup_context's after_begin hook only fires when a new
    transaction/savepoint *begins*; at login and create_lab it works
    because it's the first thing that happens on a fresh session, before
    that request's transaction has started. Anywhere else — e.g. a
    duplicate-email check inside an update endpoint, where
    get_current_member's own earlier query already opened the
    transaction — the hook registers too late to affect the check that
    needs it right now, and the bypass silently doesn't apply (RLS hides
    the very rows the check needs to see, so it reports "no duplicate"
    and lets the DB's own constraint raise an uncaught IntegrityError on
    commit instead). Use this version for exactly that mid-request case.
    """
    session.execute(text("SET LOCAL app.is_email_lookup = 'true'"))


@contextmanager
def tenant_session(tenant_id: uuid.UUID | str) -> Generator[Session, None, None]:
    """The Celery-task equivalent of what get_current_member does for HTTP
    requests. Celery tasks never go through that dependency chain — they
    open their own sessions directly — but every task that operates on a
    specific Tenant's data already receives tenant_id as a parameter, so
    the same RLS context mechanism applies here."""
    db = SessionLocal()
    bind_tenant_context(db, tenant_id)
    try:
        yield db
    finally:
        db.close()
