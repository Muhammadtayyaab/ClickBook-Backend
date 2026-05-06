from html import escape

from flask import current_app, render_template_string
from flask_mail import Message
from app.extensions import mail


def _send(to, subject, html, reply_to=None):
    # In dev this project ships with placeholder Mailtrap creds in `.env`.
    # If they aren't replaced, sending will always fail; raise a clear error
    # so callers can surface a fallback (e.g., logging a reset link).
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    if username in (None, "", "change-me") or password in (None, "", "change-me"):
        raise RuntimeError("Email is not configured (set MAIL_USERNAME / MAIL_PASSWORD in .env)")
    msg = Message(
        subject=subject,
        recipients=[to],
        html=html,
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
        reply_to=reply_to,
    )
    mail.send(msg)


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
