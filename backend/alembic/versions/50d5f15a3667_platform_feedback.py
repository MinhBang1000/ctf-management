"""platform_feedback

Revision ID: 50d5f15a3667
Revises: 29ee5f6808ef
Create Date: 2026-09-07 07:49:31.690865

Adds platform_feedback (any Member, any role, can submit free-text
feedback about the platform; Super Admin reviews it from the Console) and
its RLS policies. Mirrors audit_logs exactly: no FK to tenants/members
(feedback should outlive the Lab/account that submitted it), tenant-
scoped FOR ALL for the submitting side, Super-Admin FOR ALL for the
Console's cross-tenant listing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50d5f15a3667'
down_revision: Union[str, None] = '29ee5f6808ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_ID_EXPR = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
IS_SUPER_ADMIN_EXPR = "current_setting('app.is_super_admin', true) = 'true'"


def upgrade() -> None:
    op.create_table('platform_feedback',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('tenant_name', sa.String(length=255), nullable=False),
    sa.Column('member_id', sa.UUID(), nullable=False),
    sa.Column('member_email', sa.String(length=255), nullable=False),
    sa.Column('member_role', sa.String(length=20), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_platform_feedback_created_at'), 'platform_feedback', ['created_at'], unique=False)
    op.create_index(op.f('ix_platform_feedback_tenant_id'), 'platform_feedback', ['tenant_id'], unique=False)

    op.execute("ALTER TABLE platform_feedback ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE platform_feedback FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY platform_feedback_tenant_all ON platform_feedback "
        f"FOR ALL USING (tenant_id = {TENANT_ID_EXPR}) WITH CHECK (tenant_id = {TENANT_ID_EXPR})"
    )
    op.execute(
        f"CREATE POLICY platform_feedback_super_admin_all ON platform_feedback "
        f"FOR ALL USING ({IS_SUPER_ADMIN_EXPR})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS platform_feedback_super_admin_all ON platform_feedback")
    op.execute("DROP POLICY IF EXISTS platform_feedback_tenant_all ON platform_feedback")
    op.execute("ALTER TABLE platform_feedback NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE platform_feedback DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f('ix_platform_feedback_tenant_id'), table_name='platform_feedback')
    op.drop_index(op.f('ix_platform_feedback_created_at'), table_name='platform_feedback')
    op.drop_table('platform_feedback')
