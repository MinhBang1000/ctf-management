"""encrypt platform auth_config

Revision ID: edd9741b1d3a
Revises: 4e4c28eb0260
Create Date: 2026-08-25 15:56:11.204496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'edd9741b1d3a'
down_revision: Union[str, None] = '4e4c28eb0260'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Platform.auth_config moves from plain JSONB to Fernet-encrypted text
    # (see app/db/types.py EncryptedJSON). Safe schema-only change: every
    # existing row (the auto-seeded "Root Me" platform created per Lab in
    # Phase 1) has auth_config = NULL, so there is no plaintext data to
    # migrate or lose. `auth_config::text` correctly keeps NULL as NULL.
    op.alter_column(
        "platforms",
        "auth_config",
        type_=sa.Text(),
        postgresql_using="auth_config::text",
    )


def downgrade() -> None:
    # Not reversible in general: encrypted text is not valid JSON. Since
    # upgrade() only ever ran against NULL values in practice, downgrading
    # just drops back to an empty JSONB column.
    op.alter_column(
        "platforms",
        "auth_config",
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="NULL",
    )
