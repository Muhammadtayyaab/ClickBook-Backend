"""remove payfast payment provider columns

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint("uq_payments_transaction_id", type_="unique")
        batch_op.drop_column("transaction_id")
        batch_op.drop_column("provider")

    sa.Enum(name="payment_provider").drop(op.get_bind(), checkfirst=True)


def downgrade():
    payment_provider = sa.Enum("stripe", "payfast", name="payment_provider")
    payment_provider.create(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "provider",
                sa.Enum("stripe", "payfast", name="payment_provider"),
                nullable=False,
                server_default="stripe",
            )
        )
        batch_op.add_column(sa.Column("transaction_id", sa.String(length=120), nullable=True))
        batch_op.create_unique_constraint("uq_payments_transaction_id", ["transaction_id"])