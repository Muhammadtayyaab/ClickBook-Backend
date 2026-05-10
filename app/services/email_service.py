"""Email delivery via Mailtrap HTTP API.

Railway (and most modern PaaS) blocks outbound SMTP, so we send through
Mailtrap's HTTP endpoint instead. Configure with:
  MAILTRAP_API_TOKEN — Bearer token from Mailtrap → Settings → API Tokens
  MAILTRAP_INBOX_ID  — sandbox inbox ID (numeric, in the Integrations URL)
  MAILTRAP_API_URL   — optional override (default: sandbox endpoint)
  MAIL_DEFAULT_SENDER — From address (e.g. no-reply@clickbook.com)
"""

import os
from html import escape

import requests
from flask import current_app, render_template_string


def _send(to, subject, html, reply_to=None):
    token = os.getenv("MAILTRAP_API_TOKEN")
    inbox_id = os.getenv("MAILTRAP_INBOX_ID")
    if not token or not inbox_id:
        raise RuntimeError(
            "Mailtrap not configured (set MAILTRAP_API_TOKEN and MAILTRAP_INBOX_ID)"
        )

    base = os.getenv("MAILTRAP_API_URL", "https://sandbox.api.mailtrap.io")
    url = f"{base.rstrip('/')}/api/send/{inbox_id}"

    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or "no-reply@clickbook.com"
    payload = {
        "from": {"email": sender, "name": "ClickBook"},
        "to": [{"email": to}],
        "subject": subject,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = {"email": reply_to}

    resp = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Mailtrap send failed {resp.status_code}: {resp.text}")


def send_email(to, subject, body, reply_to=None):
    """Generic public sender. `body` is treated as HTML."""
    _send(to, subject, body, reply_to=reply_to)


def send_welcome_email(user):
    html = render_template_string("<h2>Welcome to ClickBook, {{ name }}!</h2>", name=user.name)
    _send(user.email, "Welcome to ClickBook", html)


def send_password_reset_email(email, link):
    html = render_template_string("<p>Reset password: <a href='{{ link }}'>{{ link }}</a></p>", link=link)
    _send(email, "Reset your ClickBook password", html)


def send_payment_confirmation_email(user, payment):
    html = render_template_string("<p>Payment of ${{ amount }} for {{ plan }} was successful.</p>", amount=payment.amount / 100, plan=payment.plan)
    _send(user.email, "Payment confirmation", html)


def send_site_published_notification_email(user, site):
    html = render_template_string("<p>Your site {{ name }} is now published at {{ url }}</p>", name=site.name, url=site.hosted_url)
    _send(user.email, "Your site is live", html)


def send_contact_form_email(owner, site, sender_name, sender_email, message):
    """Deliver a website contact-form submission to the site's owner.

    Sets `Reply-To` to the visitor's address so the owner can reply directly.
    """
    safe_message = escape(message).replace("\n", "<br>")
    html = render_template_string(
        """
        <div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; color:#0f172a;">
          <h2 style="margin:0 0 8px;">New message from your website</h2>
          <p style="margin:0 0 16px; color:#475569;">
            Sent via <strong>{{ site_name }}</strong>
          </p>
          <table cellpadding="6" style="border-collapse:collapse; font-size:14px;">
            <tr><td style="color:#64748b;">Name</td><td><strong>{{ name }}</strong></td></tr>
            <tr><td style="color:#64748b;">Email</td><td><a href="mailto:{{ email }}">{{ email }}</a></td></tr>
          </table>
          <div style="margin-top:16px; padding:12px 14px; background:#f8fafc; border-radius:8px; line-height:1.5;">
            {{ message|safe }}
          </div>
          <p style="margin-top:24px; font-size:12px; color:#94a3b8;">
            Reply directly to this email to respond to {{ name }}.
          </p>
        </div>
        """,
        name=sender_name,
        email=sender_email,
        message=safe_message,
        site_name=site.name,
    )
    _send(
        owner.notification_email,
        f"New message from {site.name}",
        html,
        reply_to=sender_email,
    )
