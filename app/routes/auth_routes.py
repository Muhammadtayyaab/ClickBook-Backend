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
    try:
        user = User(name=payload["name"], email=payload["email"].lower(), password_hash=generate_password_hash(payload["password"]))
        db.session.add(user)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Register insert failed for %s", payload.get("email"))
        return error_response(f"Registration failed (insert): {exc.__class__.__name__}: {exc}", 500)

    try:
        token = create_access_token(identity=str(user.id))
    except Exception as exc:
        current_app.logger.exception("Register token failed for %s", user.email)
        return error_response(f"Registration failed (token): {exc.__class__.__name__}: {exc}", 500)

    # Fire-and-forget: SMTP from Railway can hang past worker timeout,
    # which would crash the worker and return Railway's edge 500 HTML.
    import threading
    app_obj = current_app._get_current_object()
    user_email = user.email
    user_name = user.name
    def _send_welcome_async():
        with app_obj.app_context():
            try:
                from types import SimpleNamespace
                email_service.send_welcome_email(SimpleNamespace(email=user_email, name=user_name))
            except Exception:
                app_obj.logger.exception("Welcome email failed for %s", user_email)
    threading.Thread(target=_send_welcome_async, daemon=True).start()

    try:
        user_dump = UserOutputSchema().dump(user)
    except Exception as exc:
        current_app.logger.exception("Register dump failed for %s", user.email)
        return error_response(f"Registration failed (serialize): {exc.__class__.__name__}: {exc}", 500)

    return success_response({"token": token, "user": user_dump})


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
    current_app.logger.warning("FORGOT-PASSWORD requested for %s", payload.get("email"))
    user = User.query.filter_by(email=payload["email"].lower()).first()
    current_app.logger.warning("FORGOT-PASSWORD user lookup result: %s", "FOUND" if user else "NOT FOUND")
    if user:
        s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        token = s.dumps(user.email, salt="password-reset")
        # Prefer the calling frontend's origin so dev ports (8081, etc.) work.
        base_url = request.headers.get("Origin") or current_app.config["CLIENT_URL"]
        link = f"{base_url}/reset-password?token={token}"

        # SMTP from Railway can hang past the worker timeout, which makes the
        # edge return an HTML error page instead of our JSON — surfacing as
        # "Could not send reset link" on the client. Send asynchronously.
        import threading
        app_obj = current_app._get_current_object()
        recipient = user.email
        def _send_async():
            with app_obj.app_context():
                try:
                    email_service.send_password_reset_email(recipient, link)
                    app_obj.logger.warning("FORGOT-PASSWORD email SENT to %s", recipient)
                except Exception as exc:
                    app_obj.logger.warning("FORGOT-PASSWORD email FAILED for %s: %r", recipient, exc)
                    app_obj.logger.exception("Traceback:")
        threading.Thread(target=_send_async, daemon=True).start()

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
