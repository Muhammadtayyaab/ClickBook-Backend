import os
from marshmallow import ValidationError
from dotenv import load_dotenv
from flask import Flask

from config import config_by_name
from app.extensions import cors, db, jwt, mail, ma, migrate
from app.models import TokenBlocklist
from app.routes.admin_routes import admin_bp
from app.routes.analytics_routes import analytics_bp
from app.routes.auth_routes import auth_bp
from app.routes.checkout_routes import checkout_bp
from app.routes.domain_routes import domains_bp
from app.routes.media_routes import media_bp
from app.routes.notification_routes import notifications_bp
from app.routes.page_routes import pages_bp
from app.routes.payment_routes import payments_bp
from app.routes.public_routes import public_bp
from app.routes.site_routes import sites_bp
from app.routes.stripe_routes import stripe_bp
from app.routes.template_routes import templates_bp
from app.routes.upload_routes import upload_bp
from app.utils.responses import error_response

load_dotenv()


def create_app(config_name=None):
    app = Flask(__name__)
    env = config_name or os.getenv("FLASK_ENV", "development")
    cfg = config_by_name.get(env, config_by_name["development"])
    app.config.from_object(cfg)
    if hasattr(cfg, "init_app"):
        cfg.init_app(app)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)
    mail.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": "*"}, r"/static/*": {"origins": "*"}},
    )

    # Ensure the uploads folder exists at startup so url_for works on first hit.
    uploads_path = os.path.join(app.static_folder or "static", "uploads")
    os.makedirs(uploads_path, exist_ok=True)

    app.register_blueprint(auth_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(sites_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(domains_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(stripe_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(notifications_bp)

    register_error_handlers(app)
    register_custom_domain_routing(app)

    @jwt.token_in_blocklist_loader
    def token_check(_, jwt_payload):
        return TokenBlocklist.query.filter_by(jti=jwt_payload["jti"]).first() is not None

    return app


def register_custom_domain_routing(app):
    """Map an incoming request whose Host header matches a verified custom
    domain to the SPA's hosted-site renderer. Skips /api/*, /static/*, and any
    request whose host matches the SERVER_HOSTS allowlist (the API's own
    domains). In production this is best handled at the reverse proxy (nginx /
    Cloudflare) but the same lookup table is reused so the behavior is
    consistent everywhere.
    """
    from flask import redirect, request
    from app.models import Site
    from app.models.site import SiteStatus

    def _server_hosts():
        raw = os.getenv("SERVER_HOSTS", "localhost,127.0.0.1")
        return {h.strip().lower() for h in raw.split(",") if h.strip()}

    @app.before_request
    def route_custom_domain():
        path = request.path or "/"
        if path.startswith("/api/") or path.startswith("/static/"):
            return None
        host = (request.host or "").lower()
        if ":" in host:
            host = host.split(":", 1)[0]
        if not host or host in _server_hosts():
            return None
        site = Site.query.filter(
            db.func.lower(Site.custom_domain) == host,
            Site.status == SiteStatus.published,
        ).first()
        if not site:
            return None
        client_url = os.getenv("CLIENT_URL", "http://localhost:8080").rstrip("/")
        return redirect(f"{client_url}/site/{site.id}", code=302)


def register_error_handlers(app):
    for code, message in {
        400: "Bad request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Resource not found",
        405: "Method not allowed",
        422: "Validation error",
        429: "Too many requests",
        500: "Internal server error",
    }.items():

        @app.errorhandler(code)
        def handler(err, msg=message, c=code):
            return error_response(msg, c)

    @app.errorhandler(ValidationError)
    def handle_validation(err):
        return error_response("Validation error", 422, errors=err.messages)
