import uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(80), nullable=False, index=True)  # e.g. user.create
    target_type = db.Column(db.String(50), nullable=True)  # e.g. user, template, payment
    target_id = db.Column(db.String(100), nullable=True)
    meta = db.Column(JSONB, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    actor = db.relationship("User", foreign_keys=[actor_user_id], lazy="joined")
