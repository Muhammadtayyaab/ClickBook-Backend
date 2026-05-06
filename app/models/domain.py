import enum
import uuid
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.sql import func
from app.extensions import db


class DomainType(str, enum.Enum):
    subdomain = "subdomain"
    custom = "custom"


class Domain(db.Model):
    __tablename__ = "domains"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    domain = db.Column(db.String(255), unique=True, nullable=False)
    type = db.Column(ENUM(DomainType, name="domain_type", create_type=True), nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(100))
    ssl_status = db.Column(db.String(50), default="pending", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
