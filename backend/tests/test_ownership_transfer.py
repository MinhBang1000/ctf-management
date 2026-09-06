"""§15 Lab ownership transfer."""
from app.models.member import MemberRole
from tests.conftest import make_member


def test_transfer_requires_confirmation(leader_client, db, tenant):
    target = make_member(db, tenant, email="target@example.com", role=MemberRole.MEMBER)
    resp = leader_client.post(f"/api/v1/members/{target.id}/transfer-ownership", json={"confirm": False})
    assert resp.status_code == 400


def test_transfer_promotes_target_and_keeps_initiator_as_leader_by_default(leader_client, db, tenant, lab_leader):
    target = make_member(db, tenant, email="target2@example.com", role=MemberRole.MEMBER)
    resp = leader_client.post(f"/api/v1/members/{target.id}/transfer-ownership", json={"confirm": True})
    assert resp.status_code == 200
    assert resp.json()["role"] == "lab_leader"

    # Initiator untouched (no demote_self_to given) — still a Leader too.
    me = leader_client.get("/api/v1/auth/me").json()
    assert me["role"] == "lab_leader"


def test_transfer_can_demote_initiator(leader_client, db, tenant, lab_leader):
    target = make_member(db, tenant, email="target3@example.com", role=MemberRole.MEMBER)
    resp = leader_client.post(
        f"/api/v1/members/{target.id}/transfer-ownership",
        json={"confirm": True, "demote_self_to": "presenter"},
    )
    assert resp.status_code == 200
    me = leader_client.get("/api/v1/auth/me").json()
    assert me["role"] == "presenter"


def test_cannot_transfer_to_self(leader_client, lab_leader):
    resp = leader_client.post(
        f"/api/v1/members/{lab_leader.id}/transfer-ownership", json={"confirm": True}
    )
    assert resp.status_code == 400


def test_cannot_transfer_to_inactive_member(leader_client, db, tenant):
    target = make_member(db, tenant, email="inactive-target@example.com", role=MemberRole.MEMBER, active=False)
    resp = leader_client.post(f"/api/v1/members/{target.id}/transfer-ownership", json={"confirm": True})
    assert resp.status_code == 400
