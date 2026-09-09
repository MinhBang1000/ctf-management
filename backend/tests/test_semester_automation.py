"""Semester-report automation trigger: defaults from end_date at creation,
independently editable afterward, never re-synced when end_date changes."""
from tests.conftest import login_as


def test_create_defaults_report_trigger_date_to_end_date(leader_client):
    resp = leader_client.post(
        "/api/v1/semesters", json={"name": "Fall", "start_date": "2026-08-01", "end_date": "2026-12-15"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["report_trigger_date"] == "2026-12-15"
    assert body["report_automation_enabled"] is True
    assert body["report_auto_send"] is False


def test_report_trigger_date_editable_independently(leader_client):
    semester = leader_client.post(
        "/api/v1/semesters", json={"name": "Fall", "start_date": "2026-08-01", "end_date": "2026-12-15"}
    ).json()

    resp = leader_client.patch(
        f"/api/v1/semesters/{semester['id']}",
        json={"report_trigger_date": "2026-12-20", "report_auto_send": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_trigger_date"] == "2026-12-20"
    assert body["report_auto_send"] is True
    assert body["end_date"] == "2026-12-15"  # untouched


def test_changing_end_date_does_not_resync_trigger_date(leader_client):
    semester = leader_client.post(
        "/api/v1/semesters", json={"name": "Fall", "start_date": "2026-08-01", "end_date": "2026-12-15"}
    ).json()
    leader_client.patch(f"/api/v1/semesters/{semester['id']}", json={"report_trigger_date": "2026-12-20"})

    resp = leader_client.patch(f"/api/v1/semesters/{semester['id']}", json={"end_date": "2026-12-22"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["end_date"] == "2026-12-22"
    assert body["report_trigger_date"] == "2026-12-20"  # still the manually-set value


def test_disable_report_automation(leader_client):
    semester = leader_client.post(
        "/api/v1/semesters", json={"name": "Fall", "start_date": "2026-08-01", "end_date": "2026-12-15"}
    ).json()
    resp = leader_client.patch(f"/api/v1/semesters/{semester['id']}", json={"report_automation_enabled": False})
    assert resp.status_code == 200
    assert resp.json()["report_automation_enabled"] is False


def test_non_leader_cannot_edit_semester_automation(client, tenant, presenter, lab_leader):
    login_as(client, lab_leader.email, "leaderpass123")
    semester = client.post(
        "/api/v1/semesters", json={"name": "Fall", "start_date": "2026-08-01", "end_date": "2026-12-15"}
    ).json()

    login_as(client, presenter.email, "presenterpass123")
    resp = client.patch(f"/api/v1/semesters/{semester['id']}", json={"report_auto_send": True})
    assert resp.status_code == 403
