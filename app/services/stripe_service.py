import stripe
from flask import current_app

PRICE_MAP = {
    "starter": {"monthly": 1900, "yearly": 19000},
    "pro": {"monthly": 4900, "yearly": 49000},
    "business": {"monthly": 9900, "yearly": 99000},
}


def _init_stripe():
    api_key = (current_app.config.get("STRIPE_SECRET_KEY") or "").strip()
    if not api_key or "change_me" in api_key or "replace_me" in api_key:
        raise RuntimeError("Stripe is not configured. Set a valid STRIPE_SECRET_KEY.")
    stripe.api_key = api_key


def create_checkout_session(user_id, site_id, plan, billing_period, *, template_id=None):
    _init_stripe()
    amount = PRICE_MAP[plan][billing_period]
    metadata = {
        "user_id": str(user_id),
        "site_id": str(site_id) if site_id else "",
        "template_id": str(template_id) if template_id else "",
        "plan": plan,
        "billing_period": billing_period,
    }
    session = stripe.checkout.Session.create(
        mode="payment",
        success_url="https://click-book-frontend.vercel.app/billing/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://click-book-frontend.vercel.app/billing/cancel",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"ClickBook {plan.title()} ({billing_period})"},
                "unit_amount": amount,
            },
            "quantity": 1,
        }],
        metadata=metadata,
        payment_intent_data={"metadata": metadata},
    )
    return session, amount


def construct_webhook_event(payload, signature):
    _init_stripe()
    secret = (current_app.config.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise RuntimeError("Stripe webhook secret is not configured.")
    return stripe.Webhook.construct_event(payload, signature, secret)


def retrieve_session(session_id):
    _init_stripe()
    return stripe.checkout.Session.retrieve(session_id)