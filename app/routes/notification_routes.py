"""User notification preferences + public contact-form endpoint.

The contact-form endpoint is unauthenticated (it's invoked from published
sites visited by anonymous users), so it carries a small in-memory rate
limiter to slow obvious abuse without requiring Redis. Production should
front this with a real limiter (Flask-Limiter + Redis) — this is a basic
guardrail, not a substitute.
"""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from flask import Blueprint, current_app, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.middleware.auth import get_current_user
from app.models import Site, User
from app.models.site import SiteStatus
from app.schemas.user_schema import (
    ContactFormSchema,
    NotificationPrefsSchema,
    UserOutputSchema,
)
from app.services import email_service
from app.utils.responses import error_response, success_response

notifications_bp = Blueprint("notifications", __name__)


# --- Simple per-IP sliding-window rate limiter --------------------------------
_RATE_WINDOW_SECONDS = 60 * 10  # 10 minutes
_RATE_MAX_REQUESTS = 5
_rate_log: dict[str, deque] = defaultdict(deque)
_rate_lock = Lock()


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    if fwd and "," in fwd:
        fwd = fwd.split(",", 1)[0].strip()
    return fwd or "unknown"


def _allow_contact(ip: str) -> bool:
    now = monotonic()
    with _rate_lock:
        bucket = _rate_log[ip]
        cutoff = now - _RATE_WINDOW_SECONDS
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= _RATE_MAX_REQUESTS:
            return False
        bucket.append(now)
        return True


# --- Authenticated preference management --------------------------------------
@notifications_bp.get("/api/user/notifications")
@jwt_required()
def get_notifications():
    user = get_current_user()
    if not user:
        return error_response("Authentication required", 401)
    return success_response({
        "email_notifications_enabled": user.email_notifications_enabled,
        "contact_email": user.contact_email or user.email,
        "is_default_email": user.contact_email is None,
    })


@notifications_bp.put("/api/user/notifications")
@jwt_required()
def update_notifications():
    user = get_current_user()
    if not user:
        return error_response("Authentication required", 401)

    payload = NotificationPrefsSchema().load(request.get_json() or {})

    if "email_notifications_enabled" in payload:
        user.email_notifications_enabled = bool(payload["email_notifications_enabled"])

    if "contact_email" in payload:
        contact = payload["contact_email"]
        # Treat empty string / null / the account email as "use default".
        user.contact_email = (
            None if not contact or contact.lower() == user.email.lower() else contact.lower()
        )

    db.session.commit()
    return success_response(UserOutputSchema().dump(user))


# --- Public contact-form endpoint --------------------------------------------
@notifications_bp.post("/api/contact/<uuid:site_id>")
def submit_contact_form(site_id):
    """Send a contact-form submission to the site's owner via Mailtrap."""
    if not _allow_contact(_client_ip()):
        return error_response("Too many requests, please try again later.", 429)

    site = Site.query.get(site_id)
    if not site or site.status != SiteStatus.published:
        return error_response("Site not found", 404)

    payload = ContactFormSchema().load(request.get_json() or {})

    owner = User.query.get(site.user_id)
    if not owner or not owner.is_active:
        return error_response("Site owner unavailable", 404)

    if not owner.email_notifications_enabled:
        # Owner opted out — pretend success so we don't leak preference state
        # to anonymous senders, but skip sending.
        return success_response({"message": "Message received."})

    try:
        email_service.send_contact_form_email(
            owner=owner,
            site=site,
            sender_name=payload["name"].strip(),
            sender_email=payload["email"].lower(),
            message=payload["message"].strip(),
        )
    except RuntimeError as exc:
        current_app.logger.warning("Contact form: email not configured: %s", exc)
        return error_response("Email service is not configured.", 503)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Contact form delivery failed: %s", exc)
        return error_response("Failed to send message.", 502)

    return success_response({"message": "Message sent successfully."})
