"""Per-Lab automation settings API — schema validation, defaults, tenant
isolation (RLS, not just app-level filtering), and audit logging."""
from app.models.automation_settings import TenantAutomationSettings
from tests.conftest import login_as, set_tenant_context


def _payload(reminder_repeat="daily", weekly_repeat="weekly", **overrides):
    body = {
        "reminder": {"enabled": True, "repeat": reminder_repeat, "time_of_day": "07:00:00"},
        "weekly_report": {
            "enabled": True, "repeat": weekly_repeat, "time_of_day": "08:00:00", "day_of_week": 2,
        },
        "weekly_report_auto_send": False,
    }
    body.update(overrides)
    return body


def test_get_creates_default_row_with_expected_defaults(leader_client):
    resp = leader_client.get("/api/v1/settings/automation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reminder"]["repeat"] == "daily"
    assert body["reminder"]["enabled"] is True
    assert body["weekly_report"]["repeat"] == "weekly"
    assert body["weekly_report"]["day_of_week"] == 0  # Monday — see model's convention-mismatch note
    assert body["weekly_report_auto_send"] is False


def test_patch_updates_and_returns_new_values(leader_client):
    resp = leader_client.patch(
        "/api/v1/settings/automation",
        json=_payload(reminder_repeat="daily", weekly_repeat="monthly", weekly_report={
            "enabled": True, "repeat": "monthly", "time_of_day": "09:30:00", "day_of_month": 5,
        }, weekly_report_auto_send=True),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["weekly_report"]["repeat"] == "monthly"
    assert body["weekly_report"]["day_of_month"] == 5
    assert body["weekly_report_auto_send"] is True

    again = leader_client.get("/api/v1/settings/automation").json()
    assert again["weekly_report"]["repeat"] == "monthly"


def test_weekly_without_day_of_week_rejected(leader_client):
    resp = leader_client.patch(
        "/api/v1/settings/automation",
        json=_payload(weekly_repeat="weekly", weekly_report={"enabled": True, "repeat": "weekly", "time_of_day": "08:00:00"}),
    )
    assert resp.status_code == 422


def test_monthly_without_day_of_month_rejected(leader_client):
    resp = leader_client.patch(
        "/api/v1/settings/automation",
        json=_payload(weekly_report={"enabled": True, "repeat": "monthly", "time_of_day": "08:00:00"}),
    )
    assert resp.status_code == 422


def test_custom_without_interval_days_rejected(leader_client):
    resp = leader_client.patch(
        "/api/v1/settings/automation",
        json=_payload(reminder_repeat="custom"),
    )
    assert resp.status_code == 422


def test_non_leader_forbidden(client, presenter):
    login_as(client, presenter.email, "presenterpass123")
    assert client.get("/api/v1/settings/automation").status_code == 403
    assert client.patch("/api/v1/settings/automation", json=_payload()).status_code == 403


def test_editing_does_not_reset_last_fired_anchor(leader_client, db, tenant):
    # Establish the row first, then simulate the dispatcher having fired it.
    leader_client.get("/api/v1/settings/automation")
    set_tenant_context(db, tenant.id)
    row = db.query(TenantAutomationSettings).filter(TenantAutomationSettings.tenant_id == tenant.id).first()
    from datetime import datetime, timezone

    fixed = datetime(2020, 1, 1, tzinfo=timezone.utc)
    row.reminder_last_fired_at = fixed
    db.commit()

    leader_client.patch("/api/v1/settings/automation", json=_payload())
    set_tenant_context(db, tenant.id)
    row = db.query(TenantAutomationSettings).filter(TenantAutomationSettings.tenant_id == tenant.id).first()
    assert row.reminder_last_fired_at == fixed


def test_rls_blocks_reading_other_tenants_automation_settings(db, tenant, other_tenant):
    set_tenant_context(db, other_tenant.id)
    db.add(TenantAutomationSettings(tenant_id=other_tenant.id))
    db.commit()

    set_tenant_context(db, tenant.id)
    rows = db.query(TenantAutomationSettings).all()
    assert all(r.tenant_id == tenant.id for r in rows)


def test_audit_log_written_on_update(leader_client, db, tenant):
    from app.models.audit_log import AuditLog

    leader_client.patch("/api/v1/settings/automation", json=_payload())
    set_tenant_context(db, tenant.id)
    entries = db.query(AuditLog).filter(AuditLog.action == "settings.automation_updated").all()
    assert len(entries) == 1
