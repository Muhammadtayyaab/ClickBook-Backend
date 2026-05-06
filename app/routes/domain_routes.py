import dns.resolver
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.middleware.auth import get_current_user
from app.models import Domain, Site
from app.models.domain import DomainType
from app.schemas.domain_schema import (
    ClaimSubdomainSchema,
    CustomDomainSchema,
    DomainSchema,
    SubdomainCheckSchema,
    VerifyCustomDomainSchema,
)

from app.utils.helpers import generate_verification_token
from app.utils.responses import error_response, success_response

domains_bp = Blueprint("domains", __name__, url_prefix="/api/domains")


@domains_bp.post("/check-subdomain")
@jwt_required()
def check_subdomain():
    payload = SubdomainCheckSchema().load(request.get_json() or {})
    fqdn = f"{payload['subdomain']}.sitecraft.app"
    available = Domain.query.filter_by(domain=fqdn).first() is None
    return success_response({"available": available})


@domains_bp.post("/claim-subdomain")
@jwt_required()
def claim_subdomain():
    payload = ClaimSubdomainSchema().load(request.get_json() or {})
    site = Site.query.get(payload["site_id"])
    user = get_current_user()
    if not site:
        return error_response("Site not found", 404)
    if user.role.value != "admin" and str(site.user_id) != str(user.id):
        return error_response("Forbidden", 403)
    fqdn = f"{payload['subdomain']}.sitecraft.app"
    if Domain.query.filter_by(domain=fqdn).first():
        return error_response("Subdomain is not available", 409)
    domain = Domain(site_id=site.id, domain=fqdn, type="subdomain", is_verified=True, ssl_status="active")
    site.subdomain = payload["subdomain"]
    db.session.add(domain)
    db.session.commit()
    return success_response(DomainSchema().dump(domain))


@domains_bp.post("/add-custom-domain")
@jwt_required()
def add_custom_domain():
    payload = CustomDomainSchema().load(request.get_json() or {})
    site = Site.query.get(payload["site_id"])
    user = get_current_user()
    if not site:
        return error_response("Site not found", 404)
    if user.role.value != "admin" and str(site.user_id) != str(user.id):
        return error_response("Forbidden", 403)
    token = generate_verification_token()
    domain = Domain(site_id=site.id, domain=payload["domain"], type="custom", verification_token=token, is_verified=False)
    db.session.add(domain)
    db.session.commit()
    return success_response({"domain": DomainSchema().dump(domain), "instructions": f"Create TXT record _sitecraft-verification.{payload['domain']} = {token}"})


@domains_bp.post("/verify-custom-domain")
@jwt_required()
def verify_custom_domain():
    payload = VerifyCustomDomainSchema().load(request.get_json() or {})
    domain = Domain.query.filter_by(domain=payload["domain"], type="custom").first()
    if not domain:
        return error_response("Domain not found", 404)
    txt_name = f"_sitecraft-verification.{domain.domain}"
    try:
        records = dns.resolver.resolve(txt_name, "TXT")
        values = {r.to_text().strip('"') for r in records}
    except Exception:
        values = set()
    if domain.verification_token not in values:
        return error_response("Verification token not found in DNS TXT records", 400)
    domain.is_verified = True
    domain.ssl_status = "provisioning"
    domain.site.custom_domain = domain.domain
    db.session.commit()
    domain.ssl_status = "active"
    db.session.commit()
    return success_response(DomainSchema().dump(domain))


@domains_bp.get("/site/<uuid:site_id>")
@jwt_required()
def list_site_domains(site_id):
    site = Site.query.get(site_id)
    user = get_current_user()
    if not site:
        return error_response("Site not found", 404)
    if user.role.value != "admin" and str(site.user_id) != str(user.id):
        return error_response("Forbidden", 403)
    domains = Domain.query.filter_by(site_id=site_id).order_by(Domain.created_at.desc()).all()
    return success_response(DomainSchema(many=True).dump(domains))


@domains_bp.delete("/<uuid:domain_id>")
@jwt_required()
def delete_domain(domain_id):
    domain = Domain.query.get(domain_id)
    user = get_current_user()
    if not domain:
        return error_response("Domain not found", 404)
    site = Site.query.get(domain.site_id)
    if not site:
        return error_response("Site not found", 404)
    if user.role.value != "admin" and str(site.user_id) != str(user.id):
        return error_response("Forbidden", 403)
    if domain.type == DomainType.custom and site.custom_domain == domain.domain:
        site.custom_domain = None
    if domain.type == DomainType.subdomain and site.subdomain and domain.domain.startswith(f"{site.subdomain}."):
        site.subdomain = None
    db.session.delete(domain)
    db.session.commit()
    return success_response({"id": str(domain_id)})
