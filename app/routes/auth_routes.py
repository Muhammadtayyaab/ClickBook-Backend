from datetime import datetime, timezone

from itsdangerous import URLSafeTimedSerializer
from flask import Blueprint, current_app, request
from flask_jwt_extended import create_access_token, get_jwt, jwt_required
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.middleware.auth import get_current_user
from app.models import Site, TokenBlocklist, User
from app.models.site import SiteStatus
from app.models.user import UserPlan
from app.schemas.user_schema import (
    ChangePasswordSchema,
    ForgotPasswordSchema,
    LoginSchema,
    ResetPasswordSchema,
    UpdateProfileSchema,
    UserCreateSchema,
    UserOutputSchema,
)
from app.services import email_service
from app.models import User as UserModel
from app.utils.responses import error_response, success_response

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register():
    payload = UserCreateSchema().load(request.get_json() or {})
    if User.query.filter_by(email=payload["email"].lower()).first():
        return error_response("Email is already in use", 409)
    user = User(name=payload["name"], email=payload["email"].lower(), password_hash=generate_password_hash(payload["password"]))
    db.session.add(user)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Registration commit failed: %s", exc)
        return error_response("Could not create account", 500)

    try:
        token = create_access_token(identity=str(user.id))
    except Exception as exc:
        current_app.logger.exception("Token creation failed for user %s: %s", user.id, exc)
        return error_response("Could not create session token", 500)

    # Welcome email is best-effort and must NEVER block signup. SMTP from
    # the request thread can hang past gunicorn's worker timeout (-> 500),
    # so we run it in a background thread with a short socket timeout.
    import socket
    import threading

    def _send_welcome_async(app, target_user_id, target_email, target_name):
        try:
            with app.app_context():
                socket.setdefaulttimeout(5)
                try:
                    email_service._send(
                        target_email,
                        "Welcome to ClickBook",
                        f"<h2>Welcome to ClickBook, {target_name}!</h2>",
                    )
                finally:
                    socket.setdefaulttimeout(None)
        except Exception as exc:
            app.logger.warning("Welcome email failed for %s: %s", target_email, exc)

    try:
        threading.Thread(
            target=_send_welcome_async,
            args=(current_app._get_current_object(), str(user.id), user.email, user.name),
            daemon=True,
        ).start()
    except Exception as exc:
        current_app.logger.warning("Could not dispatch welcome email thread: %s", exc)

    try:
        user_data = UserOutputSchema().dump(user)
    except Exception as exc:
        current_app.logger.exception("User serialization failed for %s: %s", user.id, exc)
        user_data = {"id": str(user.id), "email": user.email, "name": user.name}

    return success_response({"token": token, "user": user_data})


@auth_bp.post("/login")
def login():
    payload = LoginSchema().load(request.get_json() or {})
    user = User.query.filter_by(email=payload["email"].lower()).first()
    if not user or not check_password_hash(user.password_hash, payload["password"]):
        return error_response("Invalid email or password", 401)
    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()
    token = create_access_token(identity=str(user.id))
    return success_response({"token": token, "user": UserOutputSchema().dump(user)})


@auth_bp.get("/me")
@jwt_required()
def me():
    return success_response(UserOutputSchema().dump(get_current_user()))


@auth_bp.get("/me/subscription")
@jwt_required()
def my_subscription():
    """Live snapshot of the user's subscription state for the dashboard.

    Source of truth for the package-status card: derives effective plan,
    days remaining, and publish quota from the User record + Site counts.
    """
    from app.routes.site_routes import get_publish_slots

    user = get_current_user()
    effective = user.effective_plan()
    is_active = user.is_plan_active()

    expires_at = user.plan_expires_at
    days_remaining = 0
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if is_active:
            delta = expires_at - datetime.now(timezone.utc)
            days_remaining = max(0, delta.days)

    publish_limit = get_publish_slots(user)
    publish_used = (
        Site.query.filter(Site.user_id == user.id, Site.status == SiteStatus.published).count()
    )
    publish_remaining = (
        None if publish_limit is None else max(0, publish_limit - publish_used)
    )

    return success_response({
        "plan": user.plan.value if user.plan else UserPlan.free.value,
        "effective_plan": effective.value,
        "is_active": is_active,
        "expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "days_remaining": days_remaining,
        "publish_limit": publish_limit,
        "publish_used": publish_used,
        "publish_remaining": publish_remaining,
    })


@auth_bp.patch("/me")
@jwt_required()
def update_me():
    payload = UpdateProfileSchema().load(request.get_json() or {})
    user = get_current_user()

    if "email" in payload:
        new_email = payload["email"].lower()
        if new_email != user.email:
            if User.query.filter_by(email=new_email).first():
                return error_response("Email is already in use", 409)
            user.email = new_email

    if "name" in payload:
        user.name = payload["name"]

    if "avatar_url" in payload:
        user.avatar_url = payload["avatar_url"]

    db.session.commit()
    return success_response(UserOutputSchema().dump(user))


@auth_bp.post("/me/unsubscribe")
@jwt_required()
def unsubscribe():
    """Cancel the active subscription. The user reverts to the free plan
    immediately and forfeits any remaining paid time — no refund. Sites
    that are already published stay published; only the publish quota
    drops back to free's allowance, which gates *new* publishes."""
    user = get_current_user()
    cancelled = user.cancel_active_subscriptions()
    if cancelled == 0:
        return error_response("You don't have an active subscription", 400)
    db.session.flush()
    user.sync_plan_snapshot()
    db.session.commit()
    return success_response({"message": "Subscription cancelled"})


@auth_bp.post("/logout")
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    db.session.add(TokenBlocklist(jti=jti))
    db.session.commit()
    return success_response({"message": "Logged out"})


@auth_bp.post("/change-password")
@jwt_required()
def change_password():
    payload = ChangePasswordSchema().load(request.get_json() or {})
    user = get_current_user()
    if not check_password_hash(user.password_hash, payload["current_password"]):
        return error_response("Current password is incorrect", 400)
    user.password_hash = generate_password_hash(payload["new_password"])
    db.session.commit()
    return success_response({"message": "Password changed"})


@auth_bp.post("/forgot-password")
def forgot_password():
    payload = ForgotPasswordSchema().load(request.get_json() or {})
    user = User.query.filter_by(email=payload["email"].lower()).first()
    if user:
        s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        token = s.dumps(user.email, salt="password-reset")
        # Prefer the calling frontend's origin so dev ports (8081, etc.) work.
        base_url = request.headers.get("Origin") or current_app.config["CLIENT_URL"]
        link = f"{base_url}/reset-password?token={token}"
        try:
            email_service.send_password_reset_email(user.email, link)
        except Exception as exc:
            current_app.logger.exception("Failed to send password reset email to %s: %s", user.email, exc)
            # Dev-only fallback: return the link so the user can continue testing
            # even if SMTP isn't configured.
            if current_app.debug:
                return success_response(
                    {
                        "message": "Email not configured; use the reset link below.",
                        "reset_link": link,
                    }
                )
    return success_response({"message": "If the email exists, a reset link has been sent"})


@auth_bp.post("/reset-password")
def reset_password():
    payload = ResetPasswordSchema().load(request.get_json() or {})
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = s.loads(payload["token"], salt="password-reset", max_age=3600)
    except Exception:
        return error_response("Invalid or expired token", 400)
    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response("User not found", 404)
    user.password_hash = generate_password_hash(payload["new_password"])
    db.session.commit()
    return success_response({"message": "Password reset successfully"})
