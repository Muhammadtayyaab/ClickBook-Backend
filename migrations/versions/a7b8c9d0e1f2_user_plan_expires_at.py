"""add plan_expires_at to users

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("plan_expires_at")
