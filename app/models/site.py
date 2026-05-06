import enum
import uuid
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.sql import func
from app.extensions import db


class SiteStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    unpublished = "unpublished"


class Site(db.Model):
    __tablename__ = "sites"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = db.Column(UUID(as_uuid=True), db.ForeignKey("templates.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    subdomain = db.Column(db.String(100), unique=True)
    custom_domain = db.Column(db.String(255), unique=True)
    global_styles = db.Column(JSONB, nullable=False, default=dict)
    status = db.Column(ENUM(SiteStatus, name="site_status", create_type=True), default=SiteStatus.draft, nullable=False)
    hosted_url = db.Column(db.String(500))
    favicon_url = db.Column(db.String(500))
    meta_title = db.Column(db.String(255))
    meta_description = db.Column(db.Text)
    page_views = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    pages = db.relationship("Page", backref="site", lazy=True, cascade="all, delete-orphan")
    domains = db.relationship("Domain", backref="site", lazy=True, cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="site", lazy=True)
