"""§12 persistent notifications."""
from app.models.member import MemberRole
from app.models.notification import Notification
from app.services.notification_service import mark_all_read, notify_lab_leaders
from tests.conftest import make_member, set_tenant_context


def test_notify_creates_one_row_per_active_lab_leader_only(db, tenant, lab_leader):
    make_member(db, tenant, email="p@example.com", role=MemberRole.PRESENTER)
    make_member(db, tenant, email="m@example.com", role=MemberRole.MEMBER)
    inactive_leader = make_member(db, tenant, email="inactive-leader@example.com", role=MemberRole.LAB_LEADER, active=False)

    set_tenant_context(db, tenant.id)
    notify_lab_leaders(db, tenant.id, type="test", title="hello")
    db.commit()

    set_tenant_context(db, tenant.id)
    rows = db.query(Notification).filter(Notification.tenant_id == tenant.id).all()
    recipients = {r.recipient_member_id for r in rows}
    assert recipients == {lab_leader.id}


def test_notify_dedupes_by_default(db, tenant, lab_leader):
    set_tenant_context(db, tenant.id)
    notify_lab_leaders(db, tenant.id, type="test", title="one", target_type="x", target_id=None)
    notify_lab_leaders(db, tenant.id, type="test", title="two", target_type="x", target_id=None)
    db.commit()
    set_tenant_context(db, tenant.id)
    count = db.query(Notification).filter(Notification.tenant_id == tenant.id).count()
    assert count == 1


def test_notify_no_dedupe_creates_multiple(db, tenant, lab_leader):
    set_tenant_context(db, tenant.id)
    notify_lab_leaders(db, tenant.id, type="sync_error", title="one", dedupe=False)
    notify_lab_leaders(db, tenant.id, type="sync_error", title="two", dedupe=False)
    db.commit()
    set_tenant_context(db, tenant.id)
    count = db.query(Notification).filter(Notification.tenant_id == tenant.id).count()
    assert count == 2


def test_notifications_api_scoped_to_self_and_tenant(leader_client, db, tenant, other_tenant, lab_leader):
    set_tenant_context(db, tenant.id)
    notify_lab_leaders(db, tenant.id, type="test", title="For me")
    db.commit()

    other_leader = make_member(db, other_tenant, email="other-leader@example.com", role=MemberRole.LAB_LEADER)
    set_tenant_context(db, other_tenant.id)
    notify_lab_leaders(db, other_tenant.id, type="test", title="Not for me")
    db.commit()

    resp = leader_client.get("/api/v1/notifications")
    assert resp.status_code == 200
    titles = [n["title"] for n in resp.json()]
    assert titles == ["For me"]


def test_mark_read_and_dismiss(leader_client, db, tenant, lab_leader):
    set_tenant_context(db, tenant.id)
    notify_lab_leaders(db, tenant.id, type="test", title="hi")
    db.commit()

    notif = leader_client.get("/api/v1/notifications").json()[0]
    assert notif["read_at"] is None

    read_resp = leader_client.post(f"/api/v1/notifications/{notif['id']}/read")
    assert read_resp.status_code == 200
    assert read_resp.json()["read_at"] is not None

    dismiss_resp = leader_client.post(f"/api/v1/notifications/{notif['id']}/dismiss")
    assert dismiss_resp.status_code == 204

    remaining = leader_client.get("/api/v1/notifications").json()
    assert remaining == []


def test_mark_all_read(db, tenant, lab_leader):
    set_tenant_context(db, tenant.id)
    notify_lab_leaders(db, tenant.id, type="a", title="1", dedupe=False)
    notify_lab_leaders(db, tenant.id, type="b", title="2", dedupe=False)
    db.commit()

    set_tenant_context(db, tenant.id)
    count = mark_all_read(db, tenant.id, lab_leader.id)
    db.commit()
    assert count == 2
