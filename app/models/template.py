import enum
import uuid
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.sql import func
from app.extensions import db


class TemplateCategory(str, enum.Enum):
    business = "business"
    gym = "gym"
    spa = "spa"
    real_estate = "real_estate"
    restaurant = "restaurant"
    portfolio = "portfolio"
    agency = "agency"
    medical = "medical"
    education = "education"
    ecommerce = "ecommerce"


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False, index=True)
    category = db.Column(ENUM(TemplateCategory, name="template_category", create_type=True), nullable=False)
    description = db.Column(db.Text)
    thumbnail_url = db.Column(db.String(500))
    preview_url = db.Column(db.String(500))
    sections_config = db.Column(JSONB, nullable=False)
    # Full multi-page template document. When present, it should include the
    # default slugs: home/about/services/contact. We keep `sections_config` for
    # backward-compatibility (home page seed).
    pages = db.Column(JSONB, nullable=False, default=dict)
    global_styles = db.Column(JSONB, nullable=False, default=dict)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    usage_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    sites = db.relationship("Site", backref="template", lazy=True)
