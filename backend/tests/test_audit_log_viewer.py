"""§19 audit log viewer + coverage of the remaining actions (semesters,
settings)."""
from tests.conftest import login_as_super_admin, make_super_admin, set_super_admin_context


def test_semester_actions_are_audited(leader_client, db, tenant):
    create = leader_client.post(
        "/api/v1/semesters", json={"name": "Fall 2026", "start_date": "2026-08-01", "end_date": "2026-12-01"}
    )
    semester_id = create.json()["id"]
    leader_client.patch(f"/api/v1/semesters/{semester_id}", json={"is_current": True})
    leader_client.delete(f"/api/v1/semesters/{semester_id}")

    resp = leader_client.get("/api/v1/audit-log")
    actions = [e["action"] for e in resp.json()]
    assert "semester.created" in actions
    assert "semester.current_changed" in actions
    assert "semester.deleted" in actions


def test_settings_actions_are_audited(leader_client):
    leader_client.patch(
        "/api/v1/settings/smtp",
        json={"host": "smtp.example.com", "port": 587, "username": None, "password": "x", "from_address": None, "use_tls": True},
    )
    leader_client.patch("/api/v1/settings/professor-email", json={"professor_email": "prof@example.com"})

    resp = leader_client.get("/api/v1/audit-log")
    actions = [e["action"] for e in resp.json()]
    assert "settings.smtp_updated" in actions
    assert "settings.professor_email_updated" in actions


def test_audit_log_filters_by_action(leader_client, tenant):
    leader_client.post(
        "/api/v1/semesters", json={"name": "S1", "start_date": "2026-01-01", "end_date": "2026-06-01"}
    )
    resp = leader_client.get("/api/v1/audit-log", params={"action": "semester.created"})
    assert all(e["action"] == "semester.created" for e in resp.json())


def test_audit_log_scoped_to_tenant(leader_client, db, tenant, other_tenant):
    from tests.conftest import make_member, set_tenant_context

    set_tenant_context(db, other_tenant.id)
    from app.services.audit_service import record_audit
    from app.models.member import MemberRole

    other_leader = make_member(db, other_tenant, email="ol@example.com", role=MemberRole.LAB_LEADER)
    record_audit(db, tenant_id=other_tenant.id, actor=other_leader, action="x", summary="not yours")
    db.commit()

    resp = leader_client.get("/api/v1/audit-log")
    assert not any(e["summary"] == "not yours" for e in resp.json())


def test_admin_audit_log_sees_lab_deleted_entries(client, db, tenant):
    admin = make_super_admin(db, email="rootaudit@example.com", password="rootpass123")
    login_as_super_admin(client, admin.email, "rootpass123")
    tenant_id = tenant.id
    client.request("DELETE", f"/admin/labs/{tenant_id}", json={"confirm_name": "Test Lab"})

    resp = client.get("/admin/audit-log", params={"action": "lab.deleted"})
    assert resp.status_code == 200
    assert any(str(e["target_id"]) == str(tenant_id) for e in resp.json())
