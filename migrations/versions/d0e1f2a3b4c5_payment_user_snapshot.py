"""preserve payments after user delete: snapshot columns + SET NULL FK

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-05-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


FK_NAME = "payments_user_id_fkey"


def upgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_email_snapshot", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("user_name_snapshot", sa.String(length=150), nullable=True))
        batch_op.alter_column("user_id", existing_type=sa.UUID(), nullable=True)
        batch_op.drop_constraint(FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(
            FK_NAME,
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute(
        """
        UPDATE payments AS p
        SET user_email_snapshot = u.email,
            user_name_snapshot = u.name
        FROM users AS u
        WHERE p.user_id = u.id
          AND p.user_email_snapshot IS NULL
        """
    )


def downgrade():
    # Drop orphan rows so we can restore NOT NULL on user_id.
    op.execute("DELETE FROM payments WHERE user_id IS NULL")

    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(FK_NAME, "users", ["user_id"], ["id"])
        batch_op.alter_column("user_id", existing_type=sa.UUID(), nullable=False)
        batch_op.drop_column("user_name_snapshot")
        batch_op.drop_column("user_email_snapshot")
