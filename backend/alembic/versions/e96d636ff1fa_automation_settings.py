"""automation_settings

Revision ID: e96d636ff1fa
Revises: 50d5f15a3667
Create Date: 2026-09-09 20:46:05.866186

Per-Lab automation schedules (reminders, weekly report) in
tenant_automation_settings (1-1 with tenants, RLS'd like every other
tenant-scoped table), plus semester-report's own single-date trigger
columns directly on semesters (report_trigger_date defaults to that row's
own end_date via a data migration below — a server_default can't
reference a sibling column, so existing rows are backfilled with UPDATE
and new rows get it set by the API layer at creation time).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e96d636ff1fa'
down_revision: Union[str, None] = '50d5f15a3667'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_ID_EXPR = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table('tenant_automation_settings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('reminder_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('reminder_repeat', sa.String(length=20), server_default='daily', nullable=False),
    sa.Column('reminder_time_of_day', sa.Time(), server_default=sa.text("'06:00:00'"), nullable=False),
    sa.Column('reminder_day_of_week', sa.Integer(), nullable=True),
    sa.Column('reminder_day_of_month', sa.Integer(), nullable=True),
    sa.Column('reminder_interval_days', sa.Integer(), nullable=True),
    sa.Column('reminder_last_fired_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('weekly_report_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('weekly_report_repeat', sa.String(length=20), server_default='weekly', nullable=False),
    sa.Column('weekly_report_time_of_day', sa.Time(), server_default=sa.text("'00:00:00'"), nullable=False),
    sa.Column('weekly_report_day_of_week', sa.Integer(), server_default=sa.text('1'), nullable=True),
    sa.Column('weekly_report_day_of_month', sa.Integer(), nullable=True),
    sa.Column('weekly_report_interval_days', sa.Integer(), nullable=True),
    sa.Column('weekly_report_auto_send', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('weekly_report_last_fired_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenant_automation_settings_tenant_id'), 'tenant_automation_settings', ['tenant_id'], unique=True)

    op.execute("ALTER TABLE tenant_automation_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_automation_settings FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_automation_settings_tenant_all ON tenant_automation_settings "
        f"FOR ALL USING (tenant_id = {TENANT_ID_EXPR}) WITH CHECK (tenant_id = {TENANT_ID_EXPR})"
    )

    # semesters: report_trigger_date has no single static default (it's
    # "this row's own end_date") — add nullable, backfill, then tighten.
    # semesters is FORCE RLS'd with only a tenant-scoped policy (no super-
    # admin bypass — see Phase 6 migration), so a migration-time UPDATE
    # with no tenant context set would silently touch zero rows. Lift
    # FORCE just for this one backfill statement, same as any other
    # table-owner administrative operation, then restore it immediately.
    op.add_column('semesters', sa.Column('report_trigger_date', sa.Date(), nullable=True))
    op.execute("ALTER TABLE semesters NO FORCE ROW LEVEL SECURITY")
    op.execute("UPDATE semesters SET report_trigger_date = end_date WHERE report_trigger_date IS NULL")
    op.execute("ALTER TABLE semesters FORCE ROW LEVEL SECURITY")
    op.alter_column('semesters', 'report_trigger_date', nullable=False)

    op.add_column('semesters', sa.Column('report_automation_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('semesters', sa.Column('report_auto_send', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('semesters', sa.Column('report_last_fired_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('semesters', 'report_last_fired_at')
    op.drop_column('semesters', 'report_auto_send')
    op.drop_column('semesters', 'report_automation_enabled')
    op.drop_column('semesters', 'report_trigger_date')

    op.execute("DROP POLICY IF EXISTS tenant_automation_settings_tenant_all ON tenant_automation_settings")
    op.execute("ALTER TABLE tenant_automation_settings NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_automation_settings DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f('ix_tenant_automation_settings_tenant_id'), table_name='tenant_automation_settings')
    op.drop_table('tenant_automation_settings')
