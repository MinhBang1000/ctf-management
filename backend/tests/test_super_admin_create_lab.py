"""POST /admin/labs — creating a new Lab + its first Lab Leader.

Regression coverage for a real RLS gap found while smoke-testing §15/§16/
§17/§18 end to end: the ORM's INSERT ... RETURNING (needed to read back
Member.joined_at's server_default) is checked by Postgres against the
table's SELECT policy, not just the INSERT policy — and Super Admin has
no SELECT bypass on members (by design). The super-admin-only INSERT
bypass alone let the INSERT itself through but then failed on the
implicit RETURNING check, so every single Lab creation raised "new row
violates row-level security policy for table members". No test ever
exercised this endpoint for real before (existing fixtures build tenants/
members directly via set_tenant_context, bypassing this code path
entirely), so it went undetected.
"""
from app.models.member import Member, MemberRole
from app.models.platform import Platform
from tests.conftest import login_as_super_admin, make_super_admin, set_tenant_context


def _admin_client(client, db):
    admin = make_super_admin(db, email="root2@example.com", password="rootpass123")
    login_as_super_admin(client, admin.email, "rootpass123")
    return client


def test_create_lab_succeeds_and_seeds_leader_and_platform(client, db):
    admin_client = _admin_client(client, db)
    resp = admin_client.post(
        "/admin/labs",
        json={
            "name": "New Lab Via API",
            "slug": "new-lab-via-api",
            "lab_leader_full_name": "API Leader",
            "lab_leader_email": "api-leader@example.com",
            "lab_leader_password": "apileaderpass123",
        },
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    set_tenant_context(db, tenant_id)
    leader = db.query(Member).filter(Member.tenant_id == tenant_id).first()
    assert leader is not None
    assert leader.role == MemberRole.LAB_LEADER
    assert leader.email == "api-leader@example.com"
    assert leader.joined_at is not None  # the RETURNING value that used to blow up RLS

    platform = db.query(Platform).filter(Platform.tenant_id == tenant_id).first()
    assert platform is not None
    assert platform.is_focus is True

    # Login as the freshly-provisioned leader works end to end too.
    login_resp = client.post(
        "/api/v1/auth/login", json={"email": "api-leader@example.com", "password": "apileaderpass123"}
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["role"] == "lab_leader"


def test_create_lab_rejects_duplicate_slug(client, db):
    admin_client = _admin_client(client, db)
    body = {
        "name": "Dup Slug Lab",
        "slug": "dup-slug-lab",
        "lab_leader_full_name": "L1",
        "lab_leader_email": "dup-slug-1@example.com",
        "lab_leader_password": "dupslugpass1",
    }
    assert admin_client.post("/admin/labs", json=body).status_code == 201
    body2 = dict(body, lab_leader_email="dup-slug-2@example.com")
    resp = admin_client.post("/admin/labs", json=body2)
    assert resp.status_code == 409


def test_create_lab_rejects_globally_duplicate_leader_email(client, db, tenant):
    from tests.conftest import make_member

    make_member(db, tenant, email="already-taken@example.com")
    admin_client = _admin_client(client, db)
    resp = admin_client.post(
        "/admin/labs",
        json={
            "name": "Another Lab",
            "slug": "another-lab-dup-email",
            "lab_leader_full_name": "L",
            "lab_leader_email": "already-taken@example.com",
            "lab_leader_password": "somepassword123",
        },
    )
    assert resp.status_code == 409
