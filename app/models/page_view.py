import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.extensions import db


class PageView(db.Model):
    """One row per visit to a published site. Aggregated on read for analytics."""

    __tablename__ = "page_views"
    __table_args__ = (
        db.Index("ix_page_views_site_ts", "site_id", "ts"),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_slug = db.Column(db.String(100), nullable=True, index=True)
    ts = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_hash = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    referrer = db.Column(db.String(500), nullable=True)