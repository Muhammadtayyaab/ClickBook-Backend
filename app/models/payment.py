import enum
import uuid
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.sql import func
from app.extensions import db


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    site_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sites.id"), nullable=True)
    template_id = db.Column(UUID(as_uuid=True), db.ForeignKey("templates.id"), nullable=True)
    stripe_session_id = db.Column(db.String(300), unique=True)
    stripe_payment_intent_id = db.Column(db.String(300))
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), default="usd", nullable=False)
    status = db.Column(ENUM(PaymentStatus, name="payment_status", create_type=True), default=PaymentStatus.pending, nullable=False)
    plan = db.Column(db.String(50), nullable=False)
    billing_period = db.Column(db.String(20), nullable=False)
    user_email_snapshot = db.Column(db.String(255), nullable=True)
    user_name_snapshot = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
