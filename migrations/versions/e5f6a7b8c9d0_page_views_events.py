"""add page_views events table for analytics

Revision ID: e5f6a7b8c9d0
Revises: c3f1a2b4c5d6, d4e5f6a7b8c9
Create Date: 2026-04-27 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e5f6a7b8c9d0"
down_revision = ("c3f1a2b4c5d6", "d4e5f6a7b8c9")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "page_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_slug", sa.String(length=100), nullable=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("referrer", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_page_views_site_id", "page_views", ["site_id"])
    op.create_index("ix_page_views_page_slug", "page_views", ["page_slug"])
    op.create_index("ix_page_views_site_ts", "page_views", ["site_id", "ts"])


def downgrade():
    op.drop_index("ix_page_views_site_ts", table_name="page_views")
    op.drop_index("ix_page_views_page_slug", table_name="page_views")
    op.drop_index("ix_page_views_site_id", table_name="page_views")
    op.drop_table("page_views")