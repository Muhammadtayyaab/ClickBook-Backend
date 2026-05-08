from flask import Blueprint, current_app, request
from flask_jwt_extended import jwt_required
import stripe

from app.extensions import db
from app.middleware.auth import get_current_user
from app.models import Domain, Payment, Site, Template, User
from app.models.payment import PaymentStatus
from app.models.site import SiteStatus
from app.schemas.payment_schema import PaymentCreateSchema, PaymentOutputSchema, TemplatePaymentCreateSchema
from app.services import email_service
from app.services.hosting_service import deploy_site_output
from app.services.project_service import create_project_from_template
from app.services.stripe_service import (
    construct_webhook_event,
    create_checkout_session,
    retrieve_session,
)
from app.utils.responses import error_response, success_response

stripe_bp = Blueprint("stripe", __name__, url_prefix="/api/payments/stripe")


def _provision_project_for_payment(payment: Payment) -> Site | None:
    """Idempotently create the site bound to a paid template purchase.

    Returns the bound Site, or None if no template is associated. Safe to call
    multiple times — re-uses an existing site_id if already linked.
    """
    if payment.site_id:
        return Site.query.get(payment.site_id)

    if not payment.template_id:
        return None

    existing = (
        Site.query.filter_by(user_id=payment.user_id, template_id=payment.template_id)
        .order_by(Site.created_at.desc())
        .first()
    )
    if existing:
        payment.site_id = existing.id
        return existing

    site = create_project_from_template(
        user_id=payment.user_id,
        template_id=payment.template_id,
        project_name=f"{payment.plan.title()} Project",
    )
    payment.site_id = site.id
    return site


def _finalize_payment(payment: Payment, payment_intent_id: str | None) -> Payment:
    """Mark payment completed, provision site, send confirmation. Idempotent."""
    if payment.status == PaymentStatus.completed:
        return payment

    payment.status = PaymentStatus.completed
    if payment_intent_id:
        payment.stripe_payment_intent_id = payment_intent_id

    # The User.plan / plan_expires_at columns are a snapshot of what the
    # user's grants currently say — we rewrite them from scratch so the
    # snapshot, effective_plan(), and the publish-slot count can never
    # disagree. The payment row itself (just committed below) is what
    # gets read back to compute the new state.
    db.session.flush()
    if payment.user:
        payment.user.sync_plan_snapshot()

    try:
        site = _provision_project_for_payment(payment)
    except ValueError as exc:
        current_app.logger.error("project provisioning failed for payment %s: %s", payment.id, exc)
        payment.status = PaymentStatus.failed
        db.session.commit()
        return payment

    if not site and payment.site_id:
        site = Site.query.get(payment.site_id)

    if site:
        if payment.template_id:
            # Template purchases land in the dashboard as an editable draft; the
            # user clicks "Publish" when they're ready. Site.status uses an
            # ENUM(draft|published|unpublished) — any other value is invalid.
            site.status = SiteStatus.draft
        else:
            from app.routes.site_routes import get_publish_slots
            limit = get_publish_slots(payment.user)
            used_slots = Site.query.filter(
                Site.user_id == payment.user_id,
                Site.status == SiteStatus.published,
                Site.id != site.id,
            ).count() if payment.user_id else 0
            if limit is None or (used_slots + 1) <= limit:
                site.status = SiteStatus.published
                sub = Domain.query.filter_by(site_id=site.id, type="subdomain").first()
                if sub:
                    site.hosted_url = f"https://{sub.domain}"
            else:
                site.status = SiteStatus.draft

    db.session.commit()

    if site and not payment.template_id:
        try:
            deploy_site_output(site, site.pages)
            sub = Domain.query.filter_by(site_id=site.id, type="subdomain").first()
            if sub:
                site.hosted_url = f"https://{sub.domain}"
            db.session.commit()
        except Exception as exc:
            current_app.logger.warning("deploy_site_output failed for site %s: %s", site.id, exc)
            db.session.rollback()

    try:
        email_service.send_payment_confirmation_email(payment.user, payment)
    except Exception as exc:
        current_app.logger.warning("payment confirmation email failed: %s", exc)

    return payment


@stripe_bp.post("/create-session")
@jwt_required()
def create_session():
    body = request.get_json() or {}
    user = get_current_user()
    if body.get("template_id"):
        payload = TemplatePaymentCreateSchema().load(body)
        template = Template.query.get(payload["template_id"])
        if not template or not template.is_active:
            return error_response("Template not found", 404)
        site = None
    else:
        payload = PaymentCreateSchema().load(body)
        site = Site.query.get(payload["site_id"])
        if not site or str(site.user_id) != str(user.id):
            return error_response("Site not found", 404)
        template = None

    try:
        session, amount = create_checkout_session(
            user.id,
            site.id if site else None,
            payload["plan"],
            payload["billing_period"],
            template_id=template.id if template else None,
        )
    except RuntimeError as exc:
        return error_response(str(exc), 500)
    except stripe.error.StripeError as exc:
        message = getattr(exc, "user_message", None) or str(exc)
        return error_response(f"Stripe checkout failed: {message}", 502)

    payment = Payment(
        user_id=user.id,
        site_id=site.id if site else None,
        template_id=template.id if template else None,
        stripe_session_id=session.id,
        amount=amount,
        currency="usd",
        plan=payload["plan"],
        billing_period=payload["billing_period"],
        status=PaymentStatus.pending,
        user_email_snapshot=user.email,
        user_name_snapshot=user.name,
    )
    db.session.add(payment)
    db.session.commit()
    return success_response({
        "checkout_url": session.url,
        "session_id": session.id,
        "payment_id": str(payment.id),
    })


@stripe_bp.get("/verify-session")
@jwt_required()
def verify_session():
    """Verify a checkout session against Stripe. Source of truth is still the
    webhook, but in environments where webhooks aren't reachable (local dev)
    we also finalize here once Stripe itself confirms the payment — the check
    is server-to-Stripe so the trust boundary is preserved.
    """
    user = get_current_user()
    session_id = (request.args.get("session_id") or "").strip()
    if not session_id:
        return error_response("session_id is required", 400)

    payment = Payment.query.filter_by(stripe_session_id=session_id, user_id=user.id).first()
    if not payment:
        return error_response("Payment not found", 404)

    # Stripe finalizes the payment asynchronously after the user is
    # redirected back, so the first verify-session call can land while
    # Stripe still reports payment_status="unpaid". Poll briefly so the
    # frontend almost always observes "paid" on the first request and
    # we don't flash a misleading "not confirmed" warning.
    import time

    session = None
    payment_status = None
    session_status = None
    paid = False
    last_error: Exception | None = None
    for attempt in range(6):  # ~6 attempts over ~6s
        try:
            session = retrieve_session(session_id)
        except RuntimeError as exc:
            return error_response(str(exc), 500)
        except stripe.error.StripeError as exc:
            last_error = exc
            session = None
            break

        payment_status = getattr(session, "payment_status", None)
        session_status = getattr(session, "status", None)
        paid = payment_status == "paid" or session_status == "complete"
        if paid:
            break
        time.sleep(1.0)

    if session is None and last_error is not None:
        message = getattr(last_error, "user_message", None) or str(last_error)
        return error_response(f"Stripe verification failed: {message}", 502)

    if paid and payment.status != PaymentStatus.completed:
        _finalize_payment(payment, getattr(session, "payment_intent", None))

    return success_response({
        "status": "paid" if paid else "unpaid",
        "payment_status": payment_status,
        "session_status": session_status,
        "local_status": payment.status.value if hasattr(payment.status, "value") else str(payment.status),
        "site_id": str(payment.site_id) if payment.site_id else None,
        "payment": PaymentOutputSchema().dump(payment),
    })


@stripe_bp.post("/webhook")
def stripe_webhook():
    """Stripe-signed webhook. Authoritative source of payment finalization."""
    payload = request.data
    signature = request.headers.get("Stripe-Signature", "")

    try:
        event = construct_webhook_event(payload, signature)
    except RuntimeError as exc:
        current_app.logger.error("webhook config error: %s", exc)
        return error_response(str(exc), 500)
    except stripe.error.SignatureVerificationError:
        current_app.logger.warning("rejected webhook with bad signature")
        return error_response("Invalid webhook signature", 400)
    except ValueError:
        return error_response("Invalid webhook payload", 400)
    except Exception as exc:
        current_app.logger.exception("webhook construct failed: %s", exc)
        return error_response("Invalid webhook signature", 400)

    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "checkout.session.completed":
        session_id = obj.get("id")
        payment = Payment.query.filter_by(stripe_session_id=session_id).first()

        if not payment:
            metadata = obj.get("metadata") or {}
            user_id = metadata.get("user_id")
            template_id = metadata.get("template_id")
            site_id = metadata.get("site_id") or None
            plan = metadata.get("plan") or "starter"
            billing_period = metadata.get("billing_period") or "monthly"
            amount = obj.get("amount_total") or 0
            if user_id:
                payer = User.query.get(user_id)
                payment = Payment(
                    user_id=user_id,
                    site_id=site_id or None,
                    template_id=template_id or None,
                    stripe_session_id=session_id,
                    amount=amount,
                    currency=(obj.get("currency") or "usd"),
                    plan=plan,
                    billing_period=billing_period,
                    status=PaymentStatus.pending,
                    user_email_snapshot=payer.email if payer else None,
                    user_name_snapshot=payer.name if payer else None,
                )
                db.session.add(payment)
                db.session.flush()
            else:
                current_app.logger.warning("webhook checkout.session.completed without local payment row: %s", session_id)
                return success_response({"received": True, "match": False})

        if payment.status == PaymentStatus.completed:
            return success_response({"received": True, "already_processed": True})

        _finalize_payment(payment, obj.get("payment_intent"))

    elif etype in {"checkout.session.expired", "payment_intent.payment_failed"}:
        if etype == "checkout.session.expired":
            sid = obj.get("id")
        else:
            sid = (obj.get("metadata") or {}).get("stripe_session_id")
        payment = Payment.query.filter_by(stripe_session_id=sid).first() if sid else None
        if payment and payment.status != PaymentStatus.completed:
            payment.status = PaymentStatus.failed
            db.session.commit()

    return success_response({"received": True})