"""Shared pytest fixtures.

No dedicated test database exists in this environment (no CREATEDB
permission, no passwordless sudo to create one) — tests instead run
against the same database DATABASE_URL points at (the real dev DB,
already migrated with RLS applied), with every test wrapped in an outer
transaction that is rolled back at teardown. Nothing a test does is ever
committed permanently: the ORM's own `session.commit()` calls only
release/recreate a SAVEPOINT inside that outer transaction (SQLAlchemy's
`join_transaction_mode="create_savepoint"`), so RLS's own SET LOCAL
context and the application's normal multi-commit code paths behave
exactly as they do in production, but everything vanishes on rollback.

Set TEST_DATABASE_URL to point this at a real separate database instead
(e.g. once `sudo -u postgres createdb hslab_ctf_test` has been run) —
no code changes needed.
"""
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

os.environ.setdefault("APP_ENV", "test")

from app.core import deps  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.challenge import Challenge  # noqa: E402
from app.models.member import Member, MemberRole  # noqa: E402
from app.models.platform import Platform  # noqa: E402
from app.models.progress import Progress, ProgressStatus  # noqa: E402
from app.models.semester import Semester  # noqa: E402
from app.models.super_admin import SuperAdmin  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", settings.DATABASE_URL)
engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)


@pytest.fixture()
def db_connection():
    connection = engine.connect()
    trans = connection.begin()
    try:
        yield connection
    finally:
        trans.rollback()
        connection.close()


@pytest.fixture()
def db(db_connection):
    """A Session for direct fixture setup / assertions in a test body."""
    session = Session(bind=db_connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_connection):
    """A TestClient whose every request gets its own fresh Session bound
    to the same connection/transaction as the `db` fixture — matching
    production's one-Session-per-request shape (app.core.deps.get_db)
    instead of sharing one long-lived Session across requests."""

    def _override_get_db():
        session = Session(bind=db_connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --- Factories -------------------------------------------------------

def set_tenant_context(db: Session, tenant_id) -> None:
    """One-shot SET LOCAL for the current transaction — unlike
    app.db.session.bind_tenant_context (a sticky after_begin hook meant
    for a whole request/task's possibly-multi-commit lifetime), factory
    helpers just need it applied to the single commit they're about to
    do, and registering a sticky hook here would be a no-op for that
    commit anyway (the session's current transaction already began
    before the hook could attach)."""
    db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": str(tenant_id)})


def set_super_admin_context(db: Session) -> None:
    """One-shot equivalent of app.db.session.bind_super_admin_context, for
    the CURRENT transaction only — see set_tenant_context's docstring for
    why factories/tests need the one-shot form instead of the sticky one."""
    db.execute(text("SET LOCAL app.is_super_admin = 'true'"))


def make_tenant(db: Session, name: str = "Test Lab", slug: str | None = None, is_active: bool = True) -> Tenant:
    tenant = Tenant(name=name, slug=slug or f"test-{uuid.uuid4().hex[:8]}", is_active=is_active)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def make_member(
    db: Session,
    tenant: Tenant,
    email: str | None = None,
    role: MemberRole = MemberRole.MEMBER,
    password: str = "testpass123",
    active: bool = True,
    full_name: str = "Test User",
    joined_at: datetime | None = None,
) -> Member:
    set_tenant_context(db, tenant.id)
    member = Member(
        tenant_id=tenant.id,
        full_name=full_name,
        email=email or f"{uuid.uuid4().hex[:10]}@example.com",
        password_hash=hash_password(password),
        role=role,
        active=active,
    )
    db.add(member)
    db.commit()
    if joined_at is not None:
        # joined_at is a server_default — set it explicitly post-insert
        # when a test needs a Member who "joined" at a specific historical
        # moment (e.g. §13's "active throughout a past semester" fixtures).
        member.joined_at = joined_at
        db.commit()
    db.refresh(member)
    return member


def make_platform(
    db: Session,
    tenant: Tenant,
    name: str = "Root Me",
    is_focus: bool = False,
    is_active: bool = True,
    auth_config: dict | None = None,
) -> Platform:
    set_tenant_context(db, tenant.id)
    platform = Platform(
        tenant_id=tenant.id,
        name=name,
        adapter_type="rootme",
        base_url="https://api.www.root-me.org",
        is_focus=is_focus,
        is_active=is_active,
        auth_config=auth_config,
    )
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return platform


def make_semester(
    db: Session,
    tenant: Tenant,
    name: str = "Test Semester",
    start_date: date | None = None,
    end_date: date | None = None,
    is_current: bool = True,
) -> Semester:
    set_tenant_context(db, tenant.id)
    today = datetime.now(timezone.utc).date()
    semester = Semester(
        tenant_id=tenant.id,
        name=name,
        start_date=start_date or (today - timedelta(days=30)),
        end_date=end_date or (today + timedelta(days=60)),
        is_current=is_current,
    )
    db.add(semester)
    db.commit()
    db.refresh(semester)
    return semester


def make_challenge(
    db: Session,
    tenant: Tenant,
    semester: Semester,
    platform: Platform,
    title: str = "Test Challenge",
    week_number: int = 1,
    deadline_at: datetime | None = None,
    points: int | None = 100,
    presenter_id: uuid.UUID | None = None,
) -> Challenge:
    set_tenant_context(db, tenant.id)
    challenge = Challenge(
        tenant_id=tenant.id,
        semester_id=semester.id,
        platform_id=platform.id,
        week_number=week_number,
        title=title,
        deadline_at=deadline_at or (datetime.now(timezone.utc) + timedelta(days=7)),
        points=points,
        presenter_id=presenter_id,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def make_progress(
    db: Session,
    member: Member,
    challenge: Challenge,
    status: ProgressStatus = ProgressStatus.DONE,
    completed_at: datetime | None = None,
) -> Progress:
    set_tenant_context(db, member.tenant_id)
    progress = Progress(
        member_id=member.id,
        challenge_id=challenge.id,
        status=status,
        completed_at=completed_at or datetime.now(timezone.utc),
    )
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress


def make_super_admin(db: Session, email: str | None = None, password: str = "adminpass123") -> SuperAdmin:
    admin = SuperAdmin(email=email or f"admin-{uuid.uuid4().hex[:8]}@example.com", password_hash=hash_password(password))
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def login_as(client: TestClient, email: str, password: str) -> None:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text


def login_as_super_admin(client: TestClient, email: str, password: str) -> None:
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text


@pytest.fixture()
def tenant(db):
    return make_tenant(db)


@pytest.fixture()
def other_tenant(db):
    return make_tenant(db, name="Other Lab")


@pytest.fixture()
def lab_leader(db, tenant):
    return make_member(db, tenant, email="leader@example.com", role=MemberRole.LAB_LEADER, password="leaderpass123")


@pytest.fixture()
def presenter(db, tenant):
    return make_member(db, tenant, email="presenter@example.com", role=MemberRole.PRESENTER, password="presenterpass123")


@pytest.fixture()
def member(db, tenant):
    return make_member(db, tenant, email="member@example.com", role=MemberRole.MEMBER, password="memberpass123")


@pytest.fixture()
def leader_client(client, lab_leader):
    login_as(client, lab_leader.email, "leaderpass123")
    return client
