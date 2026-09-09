"""§2 password management, §3 complete member editing, §5 self-service,
§14 final Lab Leader protection."""
import re

import pytest
from sqlalchemy import text

from app.models.member import MemberRole
from tests.conftest import login_as, make_member, make_platform, set_tenant_context


# --- §2 password management -------------------------------------------

def test_change_password_requires_current_password(leader_client):
    resp = leader_client.post(
        "/api/v1/auth/change-password", json={"current_password": "wrong", "new_password": "newpass123"}
    )
    assert resp.status_code == 400


def test_change_password_invalidates_old_session_cookie(client, lab_leader):
    login_as(client, lab_leader.email, "leaderpass123")
    old_cookie = client.cookies.get("access_token")

    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "leaderpass123", "new_password": "brandnewpass123"},
    )
    assert resp.status_code == 200

    # The OLD cookie (pre-change token_version) must now be rejected. Set
    # it via an explicit per-request Cookie header, not client.cookies.set
    # (TestClient's cookie jar can end up holding both the old and the
    # newly-reissued cookie and pick either when merging by domain/path).
    resp2 = client.get("/api/v1/auth/me", headers={"Cookie": f"access_token={old_cookie}"})
    assert resp2.status_code == 401


def test_change_password_reissues_a_working_cookie(client, lab_leader):
    login_as(client, lab_leader.email, "leaderpass123")
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "leaderpass123", "new_password": "brandnewpass123"},
    )
    assert resp.status_code == 200
    # The client's cookie jar now holds the reissued cookie automatically.
    assert client.get("/api/v1/auth/me").status_code == 200


def test_forgot_password_always_returns_generic_success(client, lab_leader):
    r1 = client.post("/api/v1/auth/forgot-password", json={"email": lab_leader.email})
    r2 = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()


def test_forgot_password_reset_flow_end_to_end(client, db, tenant, lab_leader, monkeypatch):
    sent = {}

    def fake_send_email(tenant_, to_address, subject, body):
        sent["to"] = to_address
        sent["body"] = body

    monkeypatch.setattr("app.services.password_reset_service.send_email", fake_send_email)

    resp = client.post("/api/v1/auth/forgot-password", json={"email": lab_leader.email})
    assert resp.status_code == 200
    assert sent["to"] == lab_leader.email
    match = re.search(r"token=([\w\-]+)", sent["body"])
    assert match, sent["body"]
    raw_token = match.group(1)

    # Wrong token rejected
    bad = client.post("/api/v1/auth/reset-password", json={"token": "not-a-real-token", "new_password": "whatever123"})
    assert bad.status_code == 400

    # Real token works
    ok = client.post("/api/v1/auth/reset-password", json={"token": raw_token, "new_password": "resetpass123"})
    assert ok.status_code == 200

    # Token is single-use
    reuse = client.post("/api/v1/auth/reset-password", json={"token": raw_token, "new_password": "anotherpass123"})
    assert reuse.status_code == 400

    # New password actually works, old one doesn't
    assert client.post("/api/v1/auth/login", json={"email": lab_leader.email, "password": "resetpass123"}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": lab_leader.email, "password": "leaderpass123"}).status_code == 401


def test_leader_can_reset_a_members_password(leader_client, member):
    resp = leader_client.post(f"/api/v1/members/{member.id}/reset-password", json={"new_password": "newmemberpass123"})
    assert resp.status_code == 200
    login_resp = leader_client.post("/api/v1/auth/login", json={"email": member.email, "password": "newmemberpass123"})
    assert login_resp.status_code == 200


def test_member_cannot_reset_another_members_password(client, tenant, db):
    member_a = make_member(db, tenant, email="a2@example.com", role=MemberRole.MEMBER, password="pass123456")
    member_b = make_member(db, tenant, email="b2@example.com", role=MemberRole.MEMBER, password="pass123456")
    login_as(client, member_a.email, "pass123456")
    resp = client.post(f"/api/v1/members/{member_b.id}/reset-password", json={"new_password": "hacked1234"})
    assert resp.status_code == 403


# --- §3 complete member editing ----------------------------------------

def test_leader_can_edit_member_full_profile(leader_client, member):
    resp = leader_client.patch(
        f"/api/v1/members/{member.id}",
        json={"full_name": "New Name", "email": "new-email@example.com", "role": "presenter"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_name"] == "New Name"
    assert body["email"] == "new-email@example.com"
    assert body["role"] == "presenter"


def test_edit_member_duplicate_email_across_tenants_returns_409(leader_client, db, tenant, other_tenant, member):
    member_id = member.id  # cache before touching `db`'s context, or the shared
    # session's identity map re-refreshes `member` under other_tenant's RLS
    # context later and (wrongly) looks deleted — a test-harness quirk, not
    # an app bug (see test_change_password_invalidates_old_session_cookie).
    make_member(db, other_tenant, email="taken@example.com")
    resp = leader_client.patch(f"/api/v1/members/{member_id}", json={"email": "taken@example.com"})
    assert resp.status_code == 409


def test_edit_platform_accounts_rejects_platform_from_another_tenant(leader_client, db, other_tenant, member):
    member_id = member.id  # see comment above
    foreign_platform = make_platform(db, other_tenant)
    resp = leader_client.put(
        f"/api/v1/members/{member_id}/platform-accounts",
        json=[{"platform_id": str(foreign_platform.id), "external_username": "x", "external_user_id": "1"}],
    )
    assert resp.status_code == 400


# --- §5 self-service ------------------------------------------------

def test_self_service_platform_accounts_scoped_to_self(client, db, tenant):
    platform = make_platform(db, tenant)
    m = make_member(db, tenant, email="self@example.com", password="selfpass123")
    login_as(client, m.email, "selfpass123")

    resp = client.put(
        "/api/v1/me/platform-accounts",
        json=[{"platform_id": str(platform.id), "external_username": "me", "external_user_id": "42"}],
    )
    assert resp.status_code == 200
    assert resp.json()[0]["external_user_id"] == "42"

    # Confirm it landed on the caller's own row, not anyone else's, by
    # checking the members list only shows one account with this link.
    set_tenant_context(db, tenant.id)
    rows = db.execute(
        text("SELECT member_id FROM member_platform_accounts WHERE external_user_id = '42'")
    ).fetchall()
    assert [str(r[0]) for r in rows] == [str(m.id)]


# --- §14 final Lab Leader protection ------------------------------------

def test_cannot_deactivate_last_lab_leader(leader_client, lab_leader):
    resp = leader_client.patch(f"/api/v1/members/{lab_leader.id}", json={"active": False})
    assert resp.status_code == 409


def test_cannot_demote_last_lab_leader(leader_client, lab_leader):
    resp = leader_client.patch(f"/api/v1/members/{lab_leader.id}", json={"role": "member"})
    assert resp.status_code == 409


def test_cannot_delete_last_lab_leader(leader_client, lab_leader):
    resp = leader_client.delete(f"/api/v1/members/{lab_leader.id}")
    assert resp.status_code == 409


def test_can_demote_a_leader_when_another_leader_exists(leader_client, db, tenant, lab_leader):
    second_leader = make_member(db, tenant, email="second-leader@example.com", role=MemberRole.LAB_LEADER)
    resp = leader_client.patch(f"/api/v1/members/{second_leader.id}", json={"role": "member"})
    assert resp.status_code == 200


def test_can_deactivate_self_when_another_leader_exists(client, db, tenant, lab_leader):
    make_member(db, tenant, email="second-leader2@example.com", role=MemberRole.LAB_LEADER)
    login_as(client, lab_leader.email, "leaderpass123")
    resp = client.patch(f"/api/v1/members/{lab_leader.id}", json={"active": False})
    assert resp.status_code == 200
