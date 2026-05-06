"""Legacy /api/checkout/* aliases.

The authoritative implementation lives in backend/app/routes/stripe_routes.py at
/api/payments/stripe/*. These shims exist only so older clients pointing at
the old paths keep working — they delegate to the same handlers.
"""
from flask import Blueprint

from app.routes.stripe_routes import (
    create_session as _create_session,
    stripe_webhook as _stripe_webhook,
)

checkout_bp = Blueprint("checkout", __name__, url_prefix="/api/checkout")


@checkout_bp.post("/create-session")
def create_session():
    return _create_session()


@checkout_bp.post("/webhook")
def stripe_webhook():
    return _stripe_webhook()