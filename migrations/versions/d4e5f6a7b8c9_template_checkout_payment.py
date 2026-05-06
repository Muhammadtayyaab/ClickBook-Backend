"""support template-first payment checkout flow

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-04-27 11:55:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.alter_column("site_id", existing_type=sa.UUID(), nullable=True)
        batch_op.add_column(sa.Column("template_id", sa.UUID(), nullable=True))
        batch_op.create_foreign_key("fk_payments_template_id_templates", "templates", ["template_id"], ["id"])


def downgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint("fk_payments_template_id_templates", type_="foreignkey")
        batch_op.drop_column("template_id")
        batch_op.alter_column("site_id", existing_type=sa.UUID(), nullable=False)
