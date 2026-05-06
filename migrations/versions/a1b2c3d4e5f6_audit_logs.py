"""add audit_logs table

Revision ID: a1b2c3d4e5f6
Revises: 645e1d58bd95
Create Date: 2026-04-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'a1b2c3d4e5f6'
down_revision = '645e1d58bd95'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('actor_user_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=80), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.Column('target_id', sa.String(length=100), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_actor_user_id'), ['actor_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_created_at'), ['created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_created_at'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_action'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_actor_user_id'))
    op.drop_table('audit_logs')
