from .admin_routes import admin_bp
from .auth_routes import auth_bp
from .checkout_routes import checkout_bp
from .domain_routes import domains_bp
from .page_routes import pages_bp
from .payment_routes import payments_bp
from .site_routes import sites_bp
from .template_routes import templates_bp

__all__ = ["auth_bp", "templates_bp", "sites_bp", "pages_bp", "domains_bp", "checkout_bp", "payments_bp", "admin_bp"]
