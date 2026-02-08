"""Add user business profile fields

Revision ID: 005
Revises: 004
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add business profile columns to users table
    op.add_column('users', sa.Column('business_name', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('business_type', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('industry', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('business_size', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('location', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('years_in_business', sa.Integer, nullable=True))
    op.add_column('users', sa.Column('monthly_revenue_range', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'monthly_revenue_range')
    op.drop_column('users', 'years_in_business')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'location')
    op.drop_column('users', 'business_size')
    op.drop_column('users', 'industry')
    op.drop_column('users', 'business_type')
    op.drop_column('users', 'business_name')
