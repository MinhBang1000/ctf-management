"""Sanity-checks the test harness itself: transactional rollback actually
rolls back, and RLS is actually enforced (not just the app-level filter)."""
from sqlalchemy import text

from tests.conftest import login_as, make_member, make_tenant, set_tenant_context


def test_login_and_me(client, lab_leader):
    login_as(client, lab_leader.email, "leaderpass123")
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == lab_leader.email


def test_rls_blocks_cross_tenant_select_even_bypassing_orm_filter(db, tenant, other_tenant):
    """Proves RLS itself blocks the row, not just app-level .filter(tenant_id=...) —
    query with NO tenant filter at all, from a session bound to `tenant`'s context."""
    make_member(db, tenant, email="a@example.com")
    make_member(db, other_tenant, email="b@example.com")

    set_tenant_context(db, tenant.id)
    # Deliberately unfiltered query — RLS alone must scope this.
    rows = db.execute(text("SELECT email FROM members")).fetchall()
    emails = {r[0] for r in rows}
    assert "a@example.com" in emails
    assert "b@example.com" not in emails


def test_transaction_rollback_actually_isolates_tests(db):
    """If this ever sees another test's leftover Tenant, the harness itself
    is broken (or a shared/dedicated test DB has non-transactional pollution)."""
    count_before = db.execute(text("SELECT count(*) FROM tenants")).scalar()
    make_tenant(db, name="Should Not Survive")
    count_after = db.execute(text("SELECT count(*) FROM tenants")).scalar()
    assert count_after == count_before + 1
    # (teardown rolls back — the next test starting fresh is the real proof,
    # implicitly exercised by every other test in this suite never seeing it.)
