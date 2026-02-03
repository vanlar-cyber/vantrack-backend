"""Add drafts table

Revision ID: 002
Revises: 001
Create Date: 2026-02-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create draftstatus enum
    op.execute("CREATE TYPE draftstatus AS ENUM ('pending', 'confirmed', 'discarded')")
    
    op.create_table('drafts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('account', sa.String(), nullable=False),
        sa.Column('contact_name', sa.String(), nullable=True),
        sa.Column('contact_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('linked_transaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'confirmed', 'discarded', name='draftstatus', create_type=False), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['linked_transaction_id'], ['transactions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_drafts_user_id', 'drafts', ['user_id'])
    op.create_index('ix_drafts_status', 'drafts', ['status'])


def downgrade() -> None:
    op.drop_index('ix_drafts_status', table_name='drafts')
    op.drop_index('ix_drafts_user_id', table_name='drafts')
    op.drop_table('drafts')
    op.execute("DROP TYPE draftstatus")
