"""password_reset_members_bypass

Revision ID: 996b9d1b3606
Revises: 7f011b3268dc
Create Date: 2026-09-06 15:40:00.000000

§2 forgot-password, step 2 (reset-with-token): the caller only has a raw
token, not a tenant — so the Member row it belongs to can't be read/
updated under the normal tenant-scoped members_tenant_all policy. Two
narrow bypasses under app.is_password_reset_lookup, same shape as the
existing members_email_lookup (SELECT-only) bypass, plus an UPDATE one
since this step actually writes the new password_hash + token_version.
Members keeps its "no super-admin SELECT/UPDATE/DELETE bypass" guarantee
untouched — this is a member-initiated flow, not a Super Admin one.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '996b9d1b3606'
down_revision: Union[str, None] = '7f011b3268dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IS_PASSWORD_RESET_LOOKUP_EXPR = "current_setting('app.is_password_reset_lookup', true) = 'true'"


def upgrade() -> None:
    op.execute(
        f"CREATE POLICY members_password_reset_lookup ON members "
        f"FOR SELECT USING ({IS_PASSWORD_RESET_LOOKUP_EXPR})"
    )
    op.execute(
        f"CREATE POLICY members_password_reset_update ON members "
        f"FOR UPDATE USING ({IS_PASSWORD_RESET_LOOKUP_EXPR}) WITH CHECK ({IS_PASSWORD_RESET_LOOKUP_EXPR})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS members_password_reset_lookup ON members")
    op.execute("DROP POLICY IF EXISTS members_password_reset_update ON members")
