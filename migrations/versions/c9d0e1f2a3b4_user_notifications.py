"""add notification preferences to users

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "email_notifications_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(sa.Column("contact_email", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("contact_email")
        batch_op.drop_column("email_notifications_enabled")
