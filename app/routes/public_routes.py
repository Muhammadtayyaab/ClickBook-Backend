import hashlib

from flask import Blueprint, current_app, request

from app.extensions import db
from app.models import PageView, Site
from app.models.site import SiteStatus
from app.utils.responses import error_response, success_response

public_bp = Blueprint("public", __name__, url_prefix="/api/public")


def _hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    salt = current_app.config.get("SECRET_KEY", "")
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


def _record_view(site: Site, page_slug: str | None) -> None:
    """Insert a PageView event and bump the cached counter.

    Failures are swallowed because rendering must not break on analytics writes.
    """
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip and "," in ip:
            ip = ip.split(",", 1)[0].strip()
        event = PageView(
            site_id=site.id,
            page_slug=page_slug,
            ip_hash=_hash_ip(ip),
            user_agent=(request.headers.get("User-Agent") or "")[:500] or None,
            referrer=(request.headers.get("Referer") or "")[:500] or None,
        )
        db.session.add(event)
        site.page_views = (site.page_views or 0) + 1
        db.session.commit()
    except Exception:
        db.session.rollback()


def _serialize_pages(site: Site) -> list[dict]:
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "order": p.order,
            "is_homepage": p.is_homepage,
            "sections": p.sections or [],
        }
        for p in sorted(site.pages, key=lambda x: x.order)
    ]


def _resolve_page(site: Site, slug: str | None):
    if slug:
        match = next((p for p in site.pages if p.slug == slug), None)
        if match:
            return match
    home = next((p for p in site.pages if p.is_homepage), None)
    if home:
        return home
    if site.pages:
        return sorted(site.pages, key=lambda p: p.order)[0]
    return None


@public_bp.get("/resolve-host")
def resolve_host():
    """Public lookup used by host-based routing. Given a hostname, returns the
    site UUID if a verified custom domain matches. Used by the SPA root to
    redirect a request hitting `mysite.com` to the hosted-site renderer, and by
    the Flask `before_request` host middleware.
    """
    host = (request.args.get("host") or "").lower().strip()
    if host and ":" in host:
        host = host.split(":", 1)[0]
    if not host:
        return error_response("Missing host", 400)
    site = Site.query.filter(
        db.func.lower(Site.custom_domain) == host,
        Site.status == SiteStatus.published,
    ).first()
    if not site:
        return error_response("No site mapped to this host", 404)
    return success_response({"site_id": str(site.id), "name": site.name})


@public_bp.get("/sites/<uuid:site_id>")
def public_site(site_id):
    """Unauthenticated endpoint used by the hosted renderer at /site/:id.

    Returns metadata, the homepage's sections (back-compat), and the full list
    of pages so the multi-page navbar can render and switch without refetches.
    The optional `?page=<slug>` query selects a specific page's sections for
    the `sections` field, while still returning every page for the navbar.
    """
    site = Site.query.get(site_id)
    if not site or site.status != SiteStatus.published:
        return error_response("Site not found", 404)

    requested = request.args.get("page")
    target = _resolve_page(site, requested)

    _record_view(site, target.slug if target else None)

    return success_response({
        "id": str(site.id),
        "name": site.name,
        "meta_title": site.meta_title or site.name,
        "meta_description": site.meta_description,
        "favicon_url": site.favicon_url,
        "global_styles": site.global_styles or {},
        "sections": (target.sections if target else []),
        "current_page": target.slug if target else None,
        "pages": _serialize_pages(site),
        "page_views": site.page_views,
    })


@public_bp.get("/sites/<uuid:site_id>/pages/<page_slug>")
def public_site_page(site_id, page_slug):
    """Return a single page by slug for an in-place navbar swap on the client."""
    site = Site.query.get(site_id)
    if not site or site.status != SiteStatus.published:
        return error_response("Site not found", 404)
    target = _resolve_page(site, page_slug)
    if not target:
        return error_response("Page not found", 404)
    _record_view(site, target.slug)
    return success_response({
        "id": str(target.id),
        "name": target.name,
        "slug": target.slug,
        "is_homepage": target.is_homepage,
        "sections": target.sections or [],
    })
