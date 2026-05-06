"""add template pages jsonb

Revision ID: c3f1a2b4c5d6
Revises: b2c3d4e5f6g7
Create Date: 2026-04-27 06:45:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c3f1a2b4c5d6"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    # Add pages JSONB with a safe default for existing rows.
    op.add_column(
        "templates",
        sa.Column(
            "pages",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # Remove server_default so app-level default (dict) controls new rows.
    op.alter_column("templates", "pages", server_default=None)


def downgrade():
    op.drop_column("templates", "pages")

