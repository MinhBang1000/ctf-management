"""phase 6: enable row-level security

Revision ID: ac2110e101bb
Revises: c68f4b6942a5
Create Date: 2026-08-25 22:43:02.293109

PRD §3.2's defense-in-depth backstop: the app already filters every
query by tenant_id at the service layer — this is the second layer for
the day some future query forgets to. `hslab` OWNS every table (verified
via \\dt before writing this), and Postgres does NOT apply RLS to a
table's owner unless FORCE ROW LEVEL SECURITY is set — so FORCE is used
throughout, not just ENABLE, or this would be security theater.

Session variables the app sets to satisfy these policies (see
app/core/deps.py, app/db/session.py::tenant_session, app/api/v1/auth.py,
app/api/admin/labs.py):
  - app.current_tenant_id  — set from the verified JWT (HTTP) or an
    explicit tenant_id parameter (Celery tasks), never client input.
  - app.is_super_admin     — set only by get_current_super_admin.
  - app.is_email_lookup    — set only by the two call sites that
    legitimately need a cross-tenant email lookup (member login,
    create_lab's uniqueness check) — SELECT-only, members table only.

Bypass policies are granted per-table, per-operation, matching exactly
what's confirmed necessary by code review (PRD §9 item 6) — not a
blanket "super admin sees everything":
  - members:   NO super-admin SELECT/UPDATE/DELETE bypass at all (this
               is the "no impersonation" guarantee, enforced at the DB
               layer, not just the app layer). Only a narrow INSERT-only
               bypass (create_lab provisioning the first Lab Leader) and
               a narrow SELECT-only email-lookup bypass.
  - platforms: SELECT + INSERT super-admin bypass (dashboard aggregation
               + auto-seeded Platform on Lab creation).
  - sync_logs: SELECT-only super-admin bypass (dashboard aggregation).
  - everything else (semesters, challenges, progress, reminder_logs,
    reports, member_platform_accounts, job_run_logs): strict tenant-only,
    zero bypass — nothing in the code ever needs cross-tenant access.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ac2110e101bb"
down_revision: Union[str, None] = "c68f4b6942a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# NULLIF(..., '') matters: a custom Postgres GUC that's NEVER been set on
# a connection reads as NULL, but once SET LOCAL has touched it even once
# (e.g. an earlier request reusing this pooled connection), it reverts to
# '' — not NULL — once that transaction ends. Without the NULLIF, a
# Super-Admin request landing on a connection previously used for a Lab
# request would hit ''::uuid and raise, instead of correctly evaluating
# to "no tenant context". Confirmed via direct reproduction, not a guess.
TENANT_ID_EXPR = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
IS_SUPER_ADMIN_EXPR = "current_setting('app.is_super_admin', true) = 'true'"
IS_EMAIL_LOOKUP_EXPR = "current_setting('app.is_email_lookup', true) = 'true'"

# Tables with a direct tenant_id column, no bypass needed anywhere.
DIRECT_STRICT_TABLES = ["semesters", "challenges", "reports", "job_run_logs"]

# Tables scoped indirectly via a parent FK's tenant_id, no bypass needed.
# (table, fk_column, parent_table)
INDIRECT_STRICT_TABLES = [
    ("progress", "challenge_id", "challenges"),
    ("reminder_logs", "challenge_id", "challenges"),
    ("member_platform_accounts", "member_id", "members"),
]


def _enable_force(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def _disable(table: str) -> None:
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    # --- Direct tenant_id column, strict tenant-only ---
    for table in DIRECT_STRICT_TABLES:
        _enable_force(table)
        op.execute(
            f"CREATE POLICY {table}_tenant_all ON {table} "
            f"FOR ALL USING (tenant_id = {TENANT_ID_EXPR}) WITH CHECK (tenant_id = {TENANT_ID_EXPR})"
        )

    # --- Indirect via parent FK, strict tenant-only ---
    for table, fk_column, parent in INDIRECT_STRICT_TABLES:
        _enable_force(table)
        op.execute(
            f"CREATE POLICY {table}_tenant_all ON {table} "
            f"FOR ALL USING (EXISTS (SELECT 1 FROM {parent} p WHERE p.id = {table}.{fk_column} "
            f"AND p.tenant_id = {TENANT_ID_EXPR})) "
            f"WITH CHECK (EXISTS (SELECT 1 FROM {parent} p WHERE p.id = {table}.{fk_column} "
            f"AND p.tenant_id = {TENANT_ID_EXPR}))"
        )

    # --- members: NO super-admin SELECT/UPDATE/DELETE bypass (enforces
    # "no impersonation" at the DB layer) + two narrow, single-purpose
    # bypasses ---
    _enable_force("members")
    op.execute(
        f"CREATE POLICY members_tenant_all ON members "
        f"FOR ALL USING (tenant_id = {TENANT_ID_EXPR}) WITH CHECK (tenant_id = {TENANT_ID_EXPR})"
    )
    op.execute(f"CREATE POLICY members_email_lookup ON members FOR SELECT USING ({IS_EMAIL_LOOKUP_EXPR})")
    op.execute(f"CREATE POLICY members_super_admin_insert ON members FOR INSERT WITH CHECK ({IS_SUPER_ADMIN_EXPR})")

    # --- platforms: dashboard aggregation (SELECT) + auto-seed on Lab
    # creation (INSERT) ---
    _enable_force("platforms")
    op.execute(
        f"CREATE POLICY platforms_tenant_all ON platforms "
        f"FOR ALL USING (tenant_id = {TENANT_ID_EXPR}) WITH CHECK (tenant_id = {TENANT_ID_EXPR})"
    )
    op.execute(f"CREATE POLICY platforms_super_admin_select ON platforms FOR SELECT USING ({IS_SUPER_ADMIN_EXPR})")
    op.execute(
        f"CREATE POLICY platforms_super_admin_insert ON platforms FOR INSERT WITH CHECK ({IS_SUPER_ADMIN_EXPR})"
    )

    # --- sync_logs: dashboard aggregation (SELECT) only ---
    _enable_force("sync_logs")
    op.execute(
        f"CREATE POLICY sync_logs_tenant_all ON sync_logs "
        f"FOR ALL USING (tenant_id = {TENANT_ID_EXPR}) WITH CHECK (tenant_id = {TENANT_ID_EXPR})"
    )
    op.execute(f"CREATE POLICY sync_logs_super_admin_select ON sync_logs FOR SELECT USING ({IS_SUPER_ADMIN_EXPR})")


def downgrade() -> None:
    for table in [*DIRECT_STRICT_TABLES, *[t for t, _, _ in INDIRECT_STRICT_TABLES]]:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_all ON {table}")
        _disable(table)

    for policy in ["members_tenant_all", "members_email_lookup", "members_super_admin_insert"]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON members")
    _disable("members")

    for policy in ["platforms_tenant_all", "platforms_super_admin_select", "platforms_super_admin_insert"]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON platforms")
    _disable("platforms")

    for policy in ["sync_logs_tenant_all", "sync_logs_super_admin_select"]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON sync_logs")
    _disable("sync_logs")
