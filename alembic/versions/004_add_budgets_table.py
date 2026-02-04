"""Add budgets table

Revision ID: 004
Revises: 003
Create Date: 2026-02-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),  # spending_limit, income_goal, savings_goal, profit_goal
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('period', sa.String(20), default='monthly'),  # weekly, monthly, yearly
        sa.Column('current_amount', sa.Float, default=0),
        sa.Column('alert_at_percent', sa.Float, default=80),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('period_start', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_budgets_user_id', 'budgets', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_budgets_user_id')
    op.drop_table('budgets')
