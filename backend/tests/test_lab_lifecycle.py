"""§16 Lab deletion, §17 per-Lab export, §18 per-Lab backup/restore."""
import json

from app.models.member import MemberRole
from app.models.tenant import Tenant
from tests.conftest import (
    login_as_super_admin,
    make_challenge,
    make_member,
    make_platform,
    make_semester,
    make_super_admin,
    set_tenant_context,
)


def _admin_client(client, db):
    admin = make_super_admin(db, email="root@example.com", password="rootpass123")
    login_as_super_admin(client, admin.email, "rootpass123")
    return client


# --- §16 Lab deletion ----------------------------------------------------

def test_deletion_requires_exact_name_match(client, db, tenant):
    admin_client = _admin_client(client, db)
    resp = admin_client.request(
        "DELETE", f"/admin/labs/{tenant.id}", json={"confirm_name": "wrong name"}
    )
    assert resp.status_code == 400


def test_deletion_preview_shows_counts(client, db, tenant):
    make_member(db, tenant)
    admin_client = _admin_client(client, db)
    resp = admin_client.get(f"/admin/labs/{tenant.id}/deletion-preview")
    assert resp.status_code == 200
    assert resp.json()["member_count"] >= 1


def test_deletion_actually_removes_the_lab(client, db, tenant):
    tenant_id = tenant.id
    make_member(db, tenant)
    admin_client = _admin_client(client, db)
    resp = admin_client.request(
        "DELETE", f"/admin/labs/{tenant_id}", json={"confirm_name": "Test Lab"}
    )
    assert resp.status_code == 204

    still_there = db.get(Tenant, tenant_id)
    assert still_there is None


# --- §17 per-Lab export ---------------------------------------------------

def test_leader_can_export_own_lab(leader_client, db, tenant):
    make_member(db, tenant, email="x@example.com")
    resp = leader_client.get("/api/v1/export")
    assert resp.status_code == 200
    bundle = resp.json()
    assert bundle["tenant"]["name"] == tenant.name
    emails = {m["email"] for m in bundle["members"]}
    assert "x@example.com" in emails
    # Never includes credentials.
    assert all("auth_config" not in p for p in bundle["platforms"])


def test_super_admin_can_export_any_lab(client, db, tenant):
    admin_client = _admin_client(client, db)
    resp = admin_client.get(f"/admin/labs/{tenant.id}/export")
    assert resp.status_code == 200
    assert resp.json()["tenant"]["name"] == tenant.name


def test_member_cannot_export(client, db, tenant):
    m = make_member(db, tenant, email="plain@example.com")
    from tests.conftest import login_as

    login_as(client, m.email, "testpass123")
    resp = client.get("/api/v1/export")
    assert resp.status_code == 403


# --- §18 per-Lab backup/restore -------------------------------------------

def test_backup_and_restore_as_new_lab(client, db, tenant):
    """The realistic "new_lab" scenario: the Lab this bundle came from is
    gone by the time it's restored (disaster recovery / moving to a new
    environment) — restoring "new_lab" onto a still-alive original would
    correctly skip every Member as an email conflict instead (email is
    globally unique), covered by test_restore_skips_conflicting_email_with_a_warning.
    """
    platform = make_platform(db, tenant, auth_config={"api_key": "secret"})
    semester = make_semester(db, tenant)
    make_challenge(db, tenant, semester, platform, title="Chall A")
    make_member(db, tenant, email="restoreme-unique@example.com", full_name="Restore Me")

    admin_client = _admin_client(client, db)
    backup_resp = admin_client.post(f"/admin/labs/{tenant.id}/backup")
    assert backup_resp.status_code == 201
    job = backup_resp.json()
    assert job["status"] == "done"

    download_resp = admin_client.get(f"/admin/labs/backups/{job['id']}/download")
    assert download_resp.status_code == 200
    bundle = download_resp.json()

    # The original Lab is now gone — the actual precondition for a
    # member-for-member-clean "new_lab" restore.
    tenant_id = tenant.id
    admin_client.request("DELETE", f"/admin/labs/{tenant_id}", json={"confirm_name": "Test Lab"})

    restore_resp = admin_client.post(
        "/admin/labs/restore", json={"bundle": bundle, "mode": "new_lab"}
    )
    assert restore_resp.status_code == 200, restore_resp.text
    body = restore_resp.json()
    new_tenant_id = body["tenant_id"]
    assert new_tenant_id != str(tenant.id)
    assert not any("Skipped member" in w for w in body["warnings"])

    from app.models.challenge import Challenge
    from app.models.member import Member
    from app.models.platform import Platform

    set_tenant_context(db, new_tenant_id)
    restored_members = db.query(Member).filter(Member.tenant_id == new_tenant_id).all()
    assert any(m.full_name == "Restore Me" for m in restored_members)

    set_tenant_context(db, new_tenant_id)
    restored_challenges = db.query(Challenge).filter(Challenge.tenant_id == new_tenant_id).all()
    assert any(c.title == "Chall A" for c in restored_challenges)

    set_tenant_context(db, new_tenant_id)
    restored_platforms = db.query(Platform).filter(Platform.tenant_id == new_tenant_id).all()
    assert len(restored_platforms) == 1
    assert restored_platforms[0].auth_config is None

    # Credentials never restored.
    from app.models.platform import Platform

    restored_platforms = db.query(Platform).filter(Platform.tenant_id == new_tenant_id).all()
    assert all(p.auth_config is None for p in restored_platforms)


def test_restore_skips_conflicting_email_with_a_warning(client, db, tenant, other_tenant):
    make_member(db, tenant, email="unique-for-backup@example.com")
    # Someone in a DIFFERENT tenant already owns this email.
    make_member(db, other_tenant, email="already-taken@example.com")

    admin_client = _admin_client(client, db)
    export_resp = admin_client.get(f"/admin/labs/{tenant.id}/export")
    bundle = export_resp.json()
    # Force a conflict: rewrite one member's email in the bundle to the
    # one already used in other_tenant.
    bundle["members"][0]["email"] = "already-taken@example.com"

    restore_resp = admin_client.post("/admin/labs/restore", json={"bundle": bundle, "mode": "new_lab"})
    assert restore_resp.status_code == 200
    assert any("Skipped member" in w for w in restore_resp.json()["warnings"])


def test_restore_rejects_unsupported_format_version(client, db, tenant):
    admin_client = _admin_client(client, db)
    resp = admin_client.post(
        "/admin/labs/restore",
        json={"bundle": {"format_version": "999", "tenant": {}, "members": [], "platforms": [],
                          "member_platform_accounts": [], "semesters": [], "challenges": [], "progress": [],
                          "reports": [], "reminder_logs": [], "sync_logs": [], "job_run_logs": []},
              "mode": "new_lab"},
    )
    assert resp.status_code == 400


def test_lab_leader_cannot_call_admin_endpoints(leader_client, tenant):
    resp = leader_client.get(f"/admin/labs/{tenant.id}/export")
    assert resp.status_code in (401, 403)
