import enum
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.sql import func
from app.extensions import db


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class UserPlan(str, enum.Enum):
    free = "free"
    starter = "starter"
    pro = "pro"
    business = "business"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(ENUM(UserRole, name="user_role", create_type=True), default=UserRole.user, nullable=False)
    plan = db.Column(ENUM(UserPlan, name="user_plan", create_type=True), default=UserPlan.free, nullable=False)
    plan_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    avatar_url = db.Column(db.String(500))
    last_login_at = db.Column(db.DateTime(timezone=True))
    email_notifications_enabled = db.Column(db.Boolean, default=True, nullable=False, server_default=db.true())
    contact_email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    @property
    def notification_email(self) -> str:
        """The address contact-form messages should be delivered to."""
        return self.contact_email or self.email

    sites = db.relationship("Site", backref="owner", lazy=True, cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="user", lazy=True, passive_deletes=True)
    media_assets = db.relationship("MediaAsset", backref="user", lazy=True, cascade="all, delete-orphan")

    def _active_plan_grants(self) -> list[tuple["UserPlan", datetime]]:
        """(plan, expires_at) for every completed non-template payment whose
        paid period hasn't elapsed. This is the single source of truth for
        what the user is currently entitled to — both the displayed plan
        and the publish-slot count are derived from it, so they can never
        desync."""
        from app.models.payment import Payment, PaymentStatus

        payments = Payment.query.filter(
            Payment.user_id == self.id,
            Payment.status == PaymentStatus.completed,
            Payment.template_id.is_(None),
        ).all()

        now = datetime.now(timezone.utc)
        active: list[tuple[UserPlan, datetime]] = []
        for p in payments:
            try:
                plan = UserPlan(p.plan)
            except ValueError:
                continue
            if plan == UserPlan.free:
                continue
            days = 365 if (p.billing_period or "").lower() == "yearly" else 30
            granted_at = p.created_at
            if granted_at.tzinfo is None:
                granted_at = granted_at.replace(tzinfo=timezone.utc)
            expires_at = granted_at + timedelta(days=days)
            if expires_at <= now:
                continue
            active.append((plan, expires_at))
        return active

    def is_plan_active(self) -> bool:
        return len(self._active_plan_grants()) > 0

    def effective_plan(self) -> "UserPlan":
        rank = {UserPlan.free: 0, UserPlan.starter: 1, UserPlan.pro: 2, UserPlan.business: 3}
        grants = self._active_plan_grants()
        if not grants:
            return UserPlan.free
        return max(grants, key=lambda g: rank.get(g[0], 0))[0]

    def cancel_active_subscriptions(self) -> int:
        """Soft-cancel all currently-active subscription grants. We mark the
        underlying payments as failed because PaymentStatus has no
        dedicated 'cancelled' state — semantically these payments still
        happened, but the grant they conveyed is being revoked. Returns
        the number of cancelled payments."""
        from app.models.payment import Payment, PaymentStatus

        payments = Payment.query.filter(
            Payment.user_id == self.id,
            Payment.status == PaymentStatus.completed,
            Payment.template_id.is_(None),
        ).all()

        now = datetime.now(timezone.utc)
        cancelled = 0
        for p in payments:
            granted_at = p.created_at
            if granted_at.tzinfo is None:
                granted_at = granted_at.replace(tzinfo=timezone.utc)
            days = 365 if (p.billing_period or "").lower() == "yearly" else 30
            if granted_at + timedelta(days=days) <= now:
                continue
            p.status = PaymentStatus.failed
            cancelled += 1
        return cancelled

    def sync_plan_snapshot(self) -> None:
        """Rewrite the User.plan / plan_expires_at columns from the active
        grants so the persisted snapshot always matches effective_plan().
        Call after any change to payment state. The columns exist for
        cheap reads (admin lists, JWT claims) — never as the source of
        truth."""
        rank = {UserPlan.free: 0, UserPlan.starter: 1, UserPlan.pro: 2, UserPlan.business: 3}
        grants = self._active_plan_grants()
        if not grants:
            self.plan = UserPlan.free
            self.plan_expires_at = None
            return
        top_plan = max(grants, key=lambda g: rank.get(g[0], 0))[0]
        # Use the latest expiry across all grants of the top tier — that's
        # when the user will lose this plan tier.
        top_tier_expiry = max(exp for plan, exp in grants if plan == top_plan)
        self.plan = top_plan
        self.plan_expires_at = top_tier_expiry
