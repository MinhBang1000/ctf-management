"""§8 sync and automation history."""
from unittest.mock import patch

from app.models.job_run_log import JobRunLog
from app.models.sync_log import SyncLog
from app.models.system_job_run_log import SystemJobRunLog
from tests.conftest import login_as, make_member, make_platform, make_semester, set_super_admin_context, set_tenant_context
from app.models.member import MemberRole


def test_sync_run_history_includes_counts(leader_client, db, tenant):
    platform = make_platform(db, tenant, auth_config={"api_key": "x"})
    set_tenant_context(db, tenant.id)
    db.add(
        SyncLog(
            tenant_id=tenant.id, platform_id=platform.id, status="ok",
            members_checked=3, updated_count=2, conflicts_count=1,
        )
    )
    db.commit()

    resp = leader_client.get("/api/v1/automation/sync-runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["updated_count"] == 2
    assert body[0]["conflicts_count"] == 1
    assert body[0]["platform_name"] == platform.name


def test_job_run_history_scoped_to_tenant(leader_client, db, tenant, other_tenant):
    set_tenant_context(db, tenant.id)
    db.add(JobRunLog(tenant_id=tenant.id, job_type="reminder", status="ok"))
    db.commit()

    set_tenant_context(db, other_tenant.id)
    db.add(JobRunLog(tenant_id=other_tenant.id, job_type="reminder", status="ok"))
    db.commit()

    resp = leader_client.get("/api/v1/automation/job-runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_non_leader_cannot_view_automation_history(client, tenant, db):
    member = make_member(db, tenant, email="m3@example.com", role=MemberRole.MEMBER)
    login_as(client, member.email, "testpass123")
    resp = client.get("/api/v1/automation/sync-runs")
    assert resp.status_code == 403


def test_retry_weekly_report_is_idempotent_like_the_original(leader_client, db, tenant):
    make_semester(db, tenant)
    resp1 = leader_client.post("/api/v1/automation/retry", json={"job_type": "weekly_report"})
    resp2 = leader_client.post("/api/v1/automation/retry", json={"job_type": "weekly_report"})
    assert resp1.status_code == 200 and resp2.status_code == 200
    from app.models.report import Report

    set_tenant_context(db, tenant.id)
    count = db.query(Report).filter(Report.tenant_id == tenant.id, Report.type == "weekly").count()
    assert count == 1


def test_retry_sync_respects_cooldown(leader_client, db, tenant):
    platform = make_platform(db, tenant, auth_config={"api_key": "x"}, is_focus=True)
    with patch("app.api.v1.automation.run_sync_for_platform") as mock_sync:
        mock_sync.return_value = {"members_checked": 0, "updated": [], "conflicts": [], "errors": []}
        first = leader_client.post("/api/v1/automation/retry", json={"job_type": "sync"})
    assert first.status_code == 200

    from app.services.sync_service import SyncCooldownError

    with patch("app.api.v1.automation.run_sync_for_platform", side_effect=SyncCooldownError(600)):
        second = leader_client.post("/api/v1/automation/retry", json={"job_type": "sync"})
    assert second.status_code == 429


def test_retry_rejects_unknown_job_type(leader_client):
    resp = leader_client.post("/api/v1/automation/retry", json={"job_type": "nonsense"})
    assert resp.status_code == 400


def test_system_job_runs_super_admin_only(client, db):
    from tests.conftest import make_super_admin, login_as_super_admin

    admin = make_super_admin(db)
    set_super_admin_context(db)
    db.add(SystemJobRunLog(job_type="backup", status="ok"))
    db.commit()

    login_as_super_admin(client, admin.email, "adminpass123")
    resp = client.get("/admin/system/job-runs")
    assert resp.status_code == 200
    assert resp.json()[0]["job_type"] == "backup"


def test_lab_leader_cannot_hit_super_admin_system_endpoint(leader_client):
    resp = leader_client.get("/admin/system/job-runs")
    assert resp.status_code in (401, 403)
