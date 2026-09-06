"""member_token_version

Revision ID: 7f011b3268dc
Revises: f62320436a69
Create Date: 2026-09-06 15:34:01.637936

§2 — bumped on every password change/reset to invalidate every JWT issued
before that moment (JWTs are stateless, no server-side session store).
server_default='0' backfills existing rows; the app itself always writes
an explicit value going forward so the default is only for this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f011b3268dc'
down_revision: Union[str, None] = 'f62320436a69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('members', sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('members', 'token_version')
