"""add media_assets table

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=True),
        sa.Column("file_url", sa.String(length=1024), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_assets_user_id", "media_assets", ["user_id"])
    op.create_index(
        "ix_media_assets_user_created",
        "media_assets",
        ["user_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_media_assets_user_created", table_name="media_assets")
    op.drop_index("ix_media_assets_user_id", table_name="media_assets")
    op.drop_table("media_assets")
