"""required_features_schema

Revision ID: f62320436a69
Revises: ac2110e101bb
Create Date: 2026-09-06 15:28:59.347242

Schema + RLS for REQUIRED_FEATURES.md (all 19 sections):
  - New tables: audit_logs, notifications, password_reset_tokens,
    report_send_attempts, tenant_data_jobs.
  - New columns: challenges.external_url (§1), platforms.credentials_verified_at
    (§7), reports.recipient_email (§10).
  - A DB-level uniqueness constraint on reports (§9 weekly-report idempotency):
    one report per (tenant, semester, type, period_start, period_end).
  - A new `app.is_password_reset_lookup` RLS bypass GUC, mirroring
    `app.is_email_lookup`, for the one step of the forgot-password flow
    where the caller has a raw token but no known tenant yet (see
    app/db/session.py::bind_password_reset_lookup_context).
  - A `<table>_super_admin_delete` bypass policy on every tenant-owned
    table (added retroactively here, not by editing the Phase 6 RLS
    migration) — needed for §16 Lab deletion: Postgres's own FK cascade
    from `tenants` down through every child table fires as ordinary
    per-table DELETEs, and RLS (FORCE'd on every one of these tables)
    applies to those exactly like any other DELETE. Without this, a
    Super Admin deleting a Tenant would have the cascade silently blocked
    by RLS partway through, instead of a clean full deletion.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f62320436a69'
down_revision: Union[str, None] = 'ac2110e101bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_ID_EXPR = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
IS_SUPER_ADMIN_EXPR = "current_setting('app.is_super_admin', true) = 'true'"
IS_PASSWORD_RESET_LOOKUP_EXPR = "current_setting('app.is_password_reset_lookup', true) = 'true'"

# Every tenant-owned table that cascades (directly or transitively) from
# `tenants` — needs a super-admin DELETE bypass so §16 Lab deletion's
# cascade isn't blocked by RLS partway through. audit_logs and
# tenant_data_jobs are deliberately excluded: they don't FK to tenants at
# all (by design, so they survive the Tenant they describe being deleted).
CASCADE_TABLES_NEEDING_DELETE_BYPASS = [
    "members",
    "semesters",
    "challenges",
    "platforms",
    "reports",
    "job_run_logs",
    "sync_logs",
    "progress",
    "reminder_logs",
    "member_platform_accounts",
    "notifications",
    "password_reset_tokens",
    "report_send_attempts",
]


def _enable_force(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def _disable(table: str) -> None:
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    # ---------------------------------------------------------------
    # Schema (tables/columns/constraint)
    # ---------------------------------------------------------------
    op.create_table('audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('actor_type', sa.String(length=20), nullable=False),
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('actor_label', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.Column('target_id', sa.UUID(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_tenant_id'), 'audit_logs', ['tenant_id'], unique=False)

    op.create_table('tenant_data_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('job_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('format_version', sa.String(length=20), nullable=False),
        sa.Column('requested_by_email', sa.String(length=255), nullable=False),
        sa.Column('downloaded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tenant_data_jobs_tenant_id'), 'tenant_data_jobs', ['tenant_id'], unique=False)

    op.create_table('notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('recipient_member_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.Column('target_id', sa.UUID(), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['recipient_member_id'], ['members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_recipient_member_id'), 'notifications', ['recipient_member_id'], unique=False)
    op.create_index(op.f('ix_notifications_tenant_id'), 'notifications', ['tenant_id'], unique=False)

    op.create_table('password_reset_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('member_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_password_reset_tokens_member_id'), 'password_reset_tokens', ['member_id'], unique=False)
    op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)

    op.create_table('report_send_attempts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('report_id', sa.UUID(), nullable=False),
        sa.Column('attempted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_detail', sa.Text(), nullable=True),
        sa.Column('attempted_by_email', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_report_send_attempts_report_id'), 'report_send_attempts', ['report_id'], unique=False)

    op.add_column('challenges', sa.Column('external_url', sa.String(length=500), nullable=True))
    op.add_column('platforms', sa.Column('credentials_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('reports', sa.Column('recipient_email', sa.String(length=255), nullable=True))

    # §9 — DB-level weekly-report idempotency guard.
    op.create_unique_constraint(
        "uq_report_tenant_semester_type_period",
        "reports",
        ["tenant_id", "semester_id", "type", "period_start", "period_end"],
    )

    # ---------------------------------------------------------------
    # RLS — new tables
    # ---------------------------------------------------------------
    _enable_force("audit_logs")
    op.execute(
        f"CREATE POLICY audit_logs_tenant_all ON audit_logs "
        f"FOR ALL USING (tenant_id = {TENANT_ID_EXPR}) WITH CHECK (tenant_id = {TENANT_ID_EXPR})"
    )
    # Super Admin needs full (not just SELECT) access here: Super-Admin-
    # initiated actions with no tenant-bound member session (create_lab,
    # suspend/reactivate, delete_lab) still need to INSERT an audit row.
    op.execute(f"CREATE POLICY audit_logs_super_admin_all ON audit_logs FOR ALL USING ({IS_SUPER_ADMIN_EXPR})")

    _enable_force("tenant_data_jobs")
    op.execute(
        f"CREATE POLICY tenant_data_jobs_tenant_all ON tenant_data_jobs "
        f"FOR ALL USING (tenant_id = {TENANT_ID_EXPR}) WITH CHECK (tenant_id = {TENANT_ID_EXPR})"
    )
    op.execute(
        f"CREATE POLICY tenant_data_jobs_super_admin_all ON tenant_data_jobs FOR ALL USING ({IS_SUPER_ADMIN_EXPR})"
    )

    _enable_force("notifications")
    op.execute(
        f"CREATE POLICY notifications_tenant_all ON notifications "
        f"FOR ALL USING (tenant_id = {TENANT_ID_EXPR}) WITH CHECK (tenant_id = {TENANT_ID_EXPR})"
    )

    _enable_force("password_reset_tokens")
    op.execute(
        f"CREATE POLICY password_reset_tokens_tenant_all ON password_reset_tokens "
        f"FOR ALL USING (EXISTS (SELECT 1 FROM members p WHERE p.id = password_reset_tokens.member_id "
        f"AND p.tenant_id = {TENANT_ID_EXPR})) "
        f"WITH CHECK (EXISTS (SELECT 1 FROM members p WHERE p.id = password_reset_tokens.member_id "
        f"AND p.tenant_id = {TENANT_ID_EXPR}))"
    )
    # The one step of forgot-password where the caller has a raw token but
    # the tenant isn't known yet (can't bind_tenant_context before finding
    # the Member the token belongs to) — narrow, single-purpose, mirrors
    # members_email_lookup's shape exactly.
    op.execute(
        f"CREATE POLICY password_reset_tokens_reset_lookup ON password_reset_tokens "
        f"FOR SELECT USING ({IS_PASSWORD_RESET_LOOKUP_EXPR})"
    )
    op.execute(
        f"CREATE POLICY password_reset_tokens_reset_update ON password_reset_tokens "
        f"FOR UPDATE USING ({IS_PASSWORD_RESET_LOOKUP_EXPR}) WITH CHECK ({IS_PASSWORD_RESET_LOOKUP_EXPR})"
    )

    _enable_force("report_send_attempts")
    op.execute(
        f"CREATE POLICY report_send_attempts_tenant_all ON report_send_attempts "
        f"FOR ALL USING (EXISTS (SELECT 1 FROM reports p WHERE p.id = report_send_attempts.report_id "
        f"AND p.tenant_id = {TENANT_ID_EXPR})) "
        f"WITH CHECK (EXISTS (SELECT 1 FROM reports p WHERE p.id = report_send_attempts.report_id "
        f"AND p.tenant_id = {TENANT_ID_EXPR}))"
    )

    # ---------------------------------------------------------------
    # RLS — retroactive super-admin DELETE bypass for §16 Lab deletion's
    # cascade (see module docstring)
    # ---------------------------------------------------------------
    for table in CASCADE_TABLES_NEEDING_DELETE_BYPASS:
        op.execute(f"CREATE POLICY {table}_super_admin_delete ON {table} FOR DELETE USING ({IS_SUPER_ADMIN_EXPR})")


def downgrade() -> None:
    for table in CASCADE_TABLES_NEEDING_DELETE_BYPASS:
        op.execute(f"DROP POLICY IF EXISTS {table}_super_admin_delete ON {table}")

    for policy in ["report_send_attempts_tenant_all"]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON report_send_attempts")
    _disable("report_send_attempts")

    for policy in [
        "password_reset_tokens_tenant_all",
        "password_reset_tokens_reset_lookup",
        "password_reset_tokens_reset_update",
    ]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON password_reset_tokens")
    _disable("password_reset_tokens")

    op.execute("DROP POLICY IF EXISTS notifications_tenant_all ON notifications")
    _disable("notifications")

    for policy in ["tenant_data_jobs_tenant_all", "tenant_data_jobs_super_admin_all"]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON tenant_data_jobs")
    _disable("tenant_data_jobs")

    for policy in ["audit_logs_tenant_all", "audit_logs_super_admin_all"]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON audit_logs")
    _disable("audit_logs")

    op.drop_constraint("uq_report_tenant_semester_type_period", "reports", type_="unique")

    op.drop_column('reports', 'recipient_email')
    op.drop_column('platforms', 'credentials_verified_at')
    op.drop_column('challenges', 'external_url')

    op.drop_index(op.f('ix_report_send_attempts_report_id'), table_name='report_send_attempts')
    op.drop_table('report_send_attempts')
    op.drop_index(op.f('ix_password_reset_tokens_token_hash'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_member_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index(op.f('ix_notifications_tenant_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_recipient_member_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_tenant_data_jobs_tenant_id'), table_name='tenant_data_jobs')
    op.drop_table('tenant_data_jobs')
    op.drop_index(op.f('ix_audit_logs_tenant_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')
