"""add_action_nuggets_cache_to_user

Revision ID: d8a485abe140
Revises: 005
Create Date: 2026-02-07 23:13:22.619716

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd8a485abe140'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('cached_action_nuggets', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('action_nuggets_generated_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('action_nuggets_tx_hash', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'action_nuggets_tx_hash')
    op.drop_column('users', 'action_nuggets_generated_at')
    op.drop_column('users', 'cached_action_nuggets')
