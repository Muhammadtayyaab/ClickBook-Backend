import uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from app.extensions import db


class Page(db.Model):
    __tablename__ = "pages"
    __table_args__ = (db.UniqueConstraint("site_id", "slug", name="uq_site_slug"),)

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, default=0, nullable=False)
    is_homepage = db.Column(db.Boolean, default=False, nullable=False)
    sections = db.Column(JSONB, nullable=False, default=list)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
