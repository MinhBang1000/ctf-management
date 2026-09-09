"""§18 restore mode="overwrite_existing"."""
from tests.conftest import login_as_super_admin, make_member, make_platform, make_super_admin, set_tenant_context


def test_overwrite_existing_replaces_target_lab_data(client, db, tenant):
    tenant_id = tenant.id  # cache — restore's DELETE+recreate expires this ORM object
    make_platform(db, tenant, auth_config={"api_key": "secret"})
    make_member(db, tenant, email="original@example.com", full_name="Original Member")

    admin = make_super_admin(db, email="root2@example.com", password="rootpass123")
    login_as_super_admin(client, admin.email, "rootpass123")

    backup_resp = client.post(f"/admin/labs/{tenant_id}/backup")
    bundle = client.get(f"/admin/labs/backups/{backup_resp.json()['id']}/download").json()

    # Change the target Lab's data after the backup, to prove overwrite
    # actually replaces it rather than merging.
    make_member(db, tenant, email="should-be-gone@example.com", full_name="Should Be Gone")

    restore_resp = client.post(
        "/admin/labs/restore",
        json={"bundle": bundle, "mode": "overwrite_existing", "target_tenant_id": str(tenant_id)},
    )
    assert restore_resp.status_code == 200, restore_resp.text
    assert restore_resp.json()["tenant_id"] == str(tenant_id)

    from app.models.member import Member

    set_tenant_context(db, tenant_id)
    members = db.query(Member).filter(Member.tenant_id == tenant_id).all()
    names = {m.full_name for m in members}
    assert "Original Member" in names
    assert "Should Be Gone" not in names


def test_overwrite_existing_requires_target_tenant_id(client, db):
    admin = make_super_admin(db, email="root3@example.com", password="rootpass123")
    login_as_super_admin(client, admin.email, "rootpass123")
    resp = client.post(
        "/admin/labs/restore",
        json={
            "bundle": {
                "format_version": "1", "tenant": {"id": "00000000-0000-0000-0000-000000000000", "name": "x", "slug": "x"},
                "members": [], "platforms": [], "member_platform_accounts": [], "semesters": [], "challenges": [],
                "progress": [], "reports": [], "reminder_logs": [], "sync_logs": [], "job_run_logs": [],
            },
            "mode": "overwrite_existing",
        },
    )
    assert resp.status_code == 400
