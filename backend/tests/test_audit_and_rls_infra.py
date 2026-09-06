from sqlalchemy import text

from app.db.session import bind_super_admin_context
from app.services.audit_service import record_audit
from tests.conftest import make_member, set_tenant_context


def test_audit_log_written_in_tenant_context(db, tenant, lab_leader):
    set_tenant_context(db, tenant.id)
    record_audit(
        db,
        tenant_id=tenant.id,
        actor=lab_leader,
        action="member.created",
        summary="created test",
        target_type="member",
        target_id=lab_leader.id,
    )
    db.commit()
    set_tenant_context(db, tenant.id)
    rows = db.execute(text("SELECT action FROM audit_logs WHERE tenant_id = :t"), {"t": str(tenant.id)}).fetchall()
    assert [r[0] for r in rows] == ["member.created"]


def test_audit_log_cross_tenant_hidden_without_super_admin(db, tenant, other_tenant, lab_leader):
    set_tenant_context(db, tenant.id)
    record_audit(db, tenant_id=tenant.id, actor=lab_leader, action="x", summary="s")
    db.commit()

    set_tenant_context(db, other_tenant.id)
    rows = db.execute(text("SELECT action FROM audit_logs")).fetchall()
    assert rows == []


def test_super_admin_can_delete_tenant_cascade(db, tenant):
    """Regression test for the retroactive super-admin DELETE bypass —
    without it, this raises InsufficientPrivilege partway through the
    cascade instead of cleanly deleting the tenant and its members."""
    make_member(db, tenant, email="doomed@example.com")
    tenant_id = tenant.id  # cache before deleting — the ORM object gets expired on commit below

    bind_super_admin_context(db)
    # No exception here is itself the main proof: without the retroactive
    # DELETE-bypass policies, this raises InsufficientPrivilege partway
    # through the FK cascade instead of completing.
    db.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": str(tenant_id)})
    db.commit()

    set_tenant_context(db, tenant_id)
    remaining = db.execute(
        text("SELECT count(*) FROM members WHERE tenant_id = :id"), {"id": str(tenant_id)}
    ).scalar()
    assert remaining == 0
