"""job_history_schema

Revision ID: c629da038ca5
Revises: 996b9d1b3606
Create Date: 2026-09-06 16:21:03.088050

§8 Sync and Automation History: sync_logs gets real updated/conflicts
counts (previously computed per-member then discarded), and a new
system_job_run_logs table gives the full-database backup job (the one
job with no single-Tenant scope) a persisted run history too — Super-
Admin-only, matching §8's "system-wide operational visibility restricted
to Super Admins."
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c629da038ca5'
down_revision: Union[str, None] = '996b9d1b3606'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IS_SUPER_ADMIN_EXPR = "current_setting('app.is_super_admin', true) = 'true'"


def upgrade() -> None:
    op.create_table('system_job_run_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('run_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('sync_logs', sa.Column('updated_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('sync_logs', sa.Column('conflicts_count', sa.Integer(), nullable=False, server_default='0'))

    op.execute("ALTER TABLE system_job_run_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE system_job_run_logs FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY system_job_run_logs_super_admin_all ON system_job_run_logs FOR ALL USING ({IS_SUPER_ADMIN_EXPR})")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS system_job_run_logs_super_admin_all ON system_job_run_logs")
    op.execute("ALTER TABLE system_job_run_logs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE system_job_run_logs DISABLE ROW LEVEL SECURITY")
    op.drop_column('sync_logs', 'conflicts_count')
    op.drop_column('sync_logs', 'updated_count')
    op.drop_table('system_job_run_logs')
