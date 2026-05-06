import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.extensions import db


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=True)
    file_url = db.Column(db.String(1024), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(64), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
