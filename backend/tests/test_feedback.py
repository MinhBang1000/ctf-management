"""Platform feedback — submittable by any role, reviewed by Super Admin
cross-tenant from the Console."""
from app.models.feedback import PlatformFeedback
from tests.conftest import (
    login_as_super_admin,
    make_member,
    make_super_admin,
    set_super_admin_context,
)


def _admin_client(client, db):
    admin = make_super_admin(db, email="feedback-admin@example.com", password="rootpass123")
    login_as_super_admin(client, admin.email, "rootpass123")
    return client


def test_lab_leader_can_submit_feedback(leader_client):
    resp = leader_client.post("/api/v1/feedback", json={"message": "Please add dark mode"})
    assert resp.status_code == 201


def test_presenter_and_member_can_submit_feedback(client, db, tenant, presenter, member):
    from tests.conftest import login_as

    login_as(client, presenter.email, "presenterpass123")
    assert client.post("/api/v1/feedback", json={"message": "from presenter"}).status_code == 201

    login_as(client, member.email, "memberpass123")
    assert client.post("/api/v1/feedback", json={"message": "from member"}).status_code == 201


def test_empty_message_rejected(leader_client):
    resp = leader_client.post("/api/v1/feedback", json={"message": ""})
    assert resp.status_code == 422


def test_super_admin_sees_feedback_across_every_tenant(client, db, tenant, other_tenant, lab_leader):
    from app.models.member import MemberRole
    from tests.conftest import login_as

    # Cache primitives before creating another Member on the same shared
    # session — a later commit expires `lab_leader`, and by then this
    # session's RLS context has moved to other_tenant, so refreshing
    # lab_leader's attributes would be blocked by RLS and raise
    # ObjectDeletedError instead of just re-fetching it.
    leader_email = lab_leader.email
    make_member(db, other_tenant, email="other-leader@example.com", role=MemberRole.LAB_LEADER)

    login_as(client, leader_email, "leaderpass123")
    client.post("/api/v1/feedback", json={"message": "feedback from tenant A"})

    login_as(client, "other-leader@example.com", "testpass123")
    client.post("/api/v1/feedback", json={"message": "feedback from tenant B"})

    admin_client = _admin_client(client, db)
    resp = admin_client.get("/admin/feedback")
    assert resp.status_code == 200
    messages = {row["message"] for row in resp.json()}
    assert "feedback from tenant A" in messages
    assert "feedback from tenant B" in messages


def test_rls_blocks_reading_other_tenants_feedback_directly(db, tenant, other_tenant, lab_leader):
    """Not just an app-level filter: RLS itself must block a session bound
    to tenant A's context from ever seeing tenant B's feedback row, even
    via a raw ORM query with no WHERE clause."""
    from sqlalchemy import text

    from tests.conftest import set_tenant_context

    leader_id = lab_leader.id
    set_super_admin_context(db)
    db.add(
        PlatformFeedback(
            tenant_id=other_tenant.id,
            tenant_name=other_tenant.name,
            member_id=leader_id,
            member_email="someone@other.example.com",
            member_role="lab_leader",
            message="tenant B only",
        )
    )
    db.commit()

    # This test harness's `db.commit()` only releases a SAVEPOINT (see
    # conftest's join_transaction_mode="create_savepoint" docstring) — it
    # does NOT end the real underlying transaction, so a SET LOCAL from
    # set_super_admin_context above stays in effect across it. Reset it
    # explicitly, or the super-admin bypass policy alone would make every
    # row visible regardless of the tenant_id filter below, defeating the
    # entire point of this test.
    db.execute(text("SET LOCAL app.is_super_admin = 'false'"))
    set_tenant_context(db, tenant.id)
    rows = db.query(PlatformFeedback).all()
    assert all(r.tenant_id == tenant.id for r in rows)
    assert not any(r.message == "tenant B only" for r in rows)
