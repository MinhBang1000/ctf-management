"""§15 (decided) — Super Admin adds a new Lab Leader when a Lab has none active."""
from app.models.member import Member, MemberRole
from tests.conftest import login_as_super_admin, make_member, make_super_admin


def _admin_client(client, db):
    admin = make_super_admin(db, email="root@example.com", password="rootpass123")
    login_as_super_admin(client, admin.email, "rootpass123")
    return client


def test_refuses_when_lab_already_has_an_active_leader(client, db, tenant, lab_leader):
    admin_client = _admin_client(client, db)
    resp = admin_client.post(
        f"/admin/labs/{tenant.id}/assign-leader",
        json={"full_name": "New Leader", "email": "newleader@example.com", "password": "newpass123"},
    )
    assert resp.status_code == 400
    assert "already has an active Lab Leader" in resp.json()["detail"]


def test_assigns_new_leader_when_none_active(client, db, tenant):
    # tenant has no members at all yet.
    admin_client = _admin_client(client, db)
    resp = admin_client.post(
        f"/admin/labs/{tenant.id}/assign-leader",
        json={"full_name": "Rescue Leader", "email": "rescue@example.com", "password": "rescuepass123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "lab_leader"
    assert body["email"] == "rescue@example.com"

    login_resp = client.post("/api/v1/auth/login", json={"email": "rescue@example.com", "password": "rescuepass123"})
    assert login_resp.status_code == 200
    assert login_resp.json()["role"] == "lab_leader"


def test_assigns_new_leader_when_only_leader_is_inactive(client, db, tenant):
    make_member(db, tenant, email="old-leader@example.com", role=MemberRole.LAB_LEADER, active=False)
    admin_client = _admin_client(client, db)
    resp = admin_client.post(
        f"/admin/labs/{tenant.id}/assign-leader",
        json={"full_name": "Rescue Leader", "email": "rescue2@example.com", "password": "rescuepass123"},
    )
    assert resp.status_code == 201


def test_rejects_globally_duplicate_email(client, db, tenant, other_tenant):
    make_member(db, other_tenant, email="dup@example.com", role=MemberRole.MEMBER)
    admin_client = _admin_client(client, db)
    resp = admin_client.post(
        f"/admin/labs/{tenant.id}/assign-leader",
        json={"full_name": "Rescue Leader", "email": "dup@example.com", "password": "rescuepass123"},
    )
    assert resp.status_code == 409


def test_unknown_lab_returns_404(client, db):
    admin_client = _admin_client(client, db)
    resp = admin_client.post(
        "/admin/labs/00000000-0000-0000-0000-000000000000/assign-leader",
        json={"full_name": "X", "email": "x@example.com", "password": "xxxxxxxx"},
    )
    assert resp.status_code == 404
