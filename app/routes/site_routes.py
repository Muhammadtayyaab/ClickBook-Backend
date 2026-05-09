import secrets
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.middleware.auth import _ensure_active, get_current_user
from app.models import Page, Payment, Site, Template
from app.models.payment import PaymentStatus
from app.models.site import SiteStatus
from app.models.user import UserPlan
from app.schemas.page_schema import PageOutputSchema
from app.schemas.site_schema import (
    SiteCreateSchema,
    SiteMetaSchema,
    SiteOutputSchema,
    SiteRenameSchema,
    SiteSectionsSchema,
    SiteStylesSchema,
)
from app.utils.helpers import slugify
from app.utils.responses import error_response, success_response

sites_bp = Blueprint("sites", __name__, url_prefix="/api/sites")


# Default page slugs every new site should ship with.
DEFAULT_PAGES = ["home", "about", "services", "contact"]


def _default_section(type_, name, data, padding_y=80, align="center"):
    """Build a section in the SectionDef shape consumed by the renderer."""
    return {
        "id": f"s_{type_}_{secrets.token_hex(3)}",
        "type": type_,
        "name": name,
        "visible": True,
        "data": data,
        "style": {"paddingY": padding_y, "align": align, "width": "boxed", "radius": 16},
    }


def _scaffold_about(site_name: str) -> list[dict]:
    return [
        _default_section("hero", "About Hero", {
            "eyebrow": "About",
            "headline": f"About {site_name}",
            "subheadline": "Get to know our story, our mission, and the team behind the work.",
            "ctaPrimary": "Our story", "ctaPrimaryUrl": "#",
            "ctaSecondary": "Meet the team", "ctaSecondaryUrl": "#",
            "bgImage": "",
        }),
        _default_section("about", "About", {
            "title": "Our story",
            "body": (
                "We started with a simple idea: make great products approachable for everyone. "
                "Today we work with teams of every size to ship faster, look sharper, and grow."
            ),
            "image": "",
        }, align="left"),
        _default_section("team", "Team", {
            "title": "Meet the team",
            "members": [
                {"name": "Alex Rivera", "role": "Founder & CEO", "image": ""},
                {"name": "Mia Chen", "role": "Head of Design", "image": ""},
                {"name": "Jonas Park", "role": "Engineering Lead", "image": ""},
            ],
        }),
        _default_section("cta", "About CTA", {
            "title": "Want to work with us?",
            "body": "We're always open to new collaborations.",
            "cta": "Get in touch", "ctaUrl": "/contact",
        }),
    ]


def _scaffold_services(site_name: str) -> list[dict]:
    return [
        _default_section("hero", "Services Hero", {
            "eyebrow": "Services",
            "headline": "What we do",
            "subheadline": f"Solutions {site_name} delivers for teams that want to move faster.",
            "ctaPrimary": "Get a quote", "ctaPrimaryUrl": "/contact",
            "ctaSecondary": "View pricing", "ctaSecondaryUrl": "#",
            "bgImage": "",
        }),
        _default_section("features", "Services", {
            "title": "Our services",
            "subtitle": "End-to-end services tailored to your needs.",
            "columns": 3,
            "items": [
                {"title": "Strategy", "body": "Plans that align goals to action.", "icon": "Sparkles"},
                {"title": "Design", "body": "Beautiful, conversion-focused design.", "icon": "Star"},
                {"title": "Engineering", "body": "Reliable, scalable software delivery.", "icon": "Zap"},
                {"title": "Support", "body": "Ongoing care and optimization.", "icon": "Shield"},
                {"title": "Analytics", "body": "Insights that drive growth.", "icon": "Globe"},
                {"title": "Consulting", "body": "Hands-on expert guidance.", "icon": "Heart"},
            ],
        }),
        _default_section("pricing", "Pricing", {
            "title": "Simple pricing",
            "subtitle": "Choose the package that fits your needs.",
            "plans": [
                {"name": "Starter", "price": "$499", "period": "/mo",
                 "features": ["Up to 5 hours", "Email support"], "cta": "Choose Starter", "highlight": False},
                {"name": "Growth", "price": "$1,499", "period": "/mo",
                 "features": ["Up to 20 hours", "Priority support", "Quarterly review"],
                 "cta": "Choose Growth", "highlight": True},
                {"name": "Scale", "price": "$3,499", "period": "/mo",
                 "features": ["Dedicated team", "24/7 support", "Roadmap planning"],
                 "cta": "Choose Scale", "highlight": False},
            ],
        }),
        _default_section("cta", "Services CTA", {
            "title": "Have a project in mind?",
            "body": "Tell us about it — we usually reply within a day.",
            "cta": "Start a project", "ctaUrl": "/contact",
        }),
    ]


def _scaffold_contact(site_name: str) -> list[dict]:
    return [
        _default_section("hero", "Contact Hero", {
            "eyebrow": "Contact",
            "headline": "Let's talk",
            "subheadline": f"Reach out to {site_name} — we'd love to hear from you.",
            "ctaPrimary": "Send a message", "ctaPrimaryUrl": "#contact-form",
            "ctaSecondary": "Email us", "ctaSecondaryUrl": "mailto:hello@example.com",
            "bgImage": "",
        }, padding_y=100),
        _default_section("contact", "Contact form", {
            "title": "Get in touch",
            "email": "hello@example.com",
            "showForm": True,
        }),
        _default_section("footer", "Footer", {
            "brand": site_name,
            "copyright": f"© 2026 {site_name}. All rights reserved.",
            "links": ["Home", "About", "Services", "Contact"],
        }),
    ]


def _build_default_pages(template: Template, site_name: str) -> list[Page]:
    """Create the four default pages for a freshly-created site.

    Home is seeded from the template's `sections_config`; the other three are
    generated from generic scaffolds so every site is publish-ready out of the
    box, regardless of which template the user picked.
    """
    tpl_pages = deepcopy(getattr(template, "pages", None) or {})

    def _tpl_sections(slug: str) -> list[dict] | None:
        p = tpl_pages.get(slug)
        if isinstance(p, dict) and isinstance(p.get("sections"), list):
            return p["sections"]
        return None

    home_sections = _tpl_sections("home") or deepcopy(template.sections_config or [])
    about_sections = _tpl_sections("about") or _scaffold_about(site_name)
    services_sections = _tpl_sections("services") or _scaffold_services(site_name)
    contact_sections = _tpl_sections("contact") or _scaffold_contact(site_name)

    return [
        Page(name="Home", slug="home", order=0, is_homepage=True, sections=home_sections),
        Page(name="About", slug="about", order=1, is_homepage=False, sections=about_sections),
        Page(name="Services", slug="services", order=2, is_homepage=False, sections=services_sections),
        Page(name="Contact", slug="contact", order=3, is_homepage=False, sections=contact_sections),
    ]


def _serialize_site_card(s: Site) -> dict:
    domain = s.custom_domain or s.subdomain
    return {
        "id": str(s.id),
        "name": s.name,
        "template_id": str(s.template_id),
        "template_name": s.template.name if s.template else None,
        "thumbnail": s.template.thumbnail_url if s.template else None,
        "status": s.status.value,
        "domain": domain,
        "hosted_url": s.hosted_url,
        "page_views": s.page_views,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _ensure_owner(site: Site):
    user = get_current_user()
    if not site:
        return user, error_response("Site not found", 404)
    if user.role.value != "admin" and str(site.user_id) != str(user.id):
        return user, error_response("Forbidden", 403)
    return user, None


def _ensure_owner_writable(site: Site):
    """Owner check + suspension gate. Used on write/publish paths so the
    suspension contract ('no publishing or domain changes') is enforced even
    if the suspended user somehow holds a still-valid token."""
    user, err = _ensure_owner(site)
    if err:
        return user, err
    if (resp := _ensure_active(user)) is not None:
        return user, resp
    return user, None


@sites_bp.post("/")
@jwt_required()
def create_site():
    payload = SiteCreateSchema().load(request.get_json() or {})
    user = get_current_user()
    if (resp := _ensure_active(user)) is not None:
        return resp
    template = Template.query.get(payload["template_id"])
    if not template or not template.is_active:
        return error_response("Template not found", 404)
    site = Site(
        user_id=user.id,
        template_id=template.id,
        name=payload["name"],
        global_styles=deepcopy(template.global_styles or {}),
    )
    db.session.add(site)
    db.session.flush()
    for page in _build_default_pages(template, site.name):
        page.site_id = site.id
        db.session.add(page)
    template.usage_count += 1
    db.session.commit()
    return success_response(_serialize_site_card(site))


@sites_bp.get("/stats")
@jwt_required()
def site_stats():
    user = get_current_user()
    base = Site.query.filter_by(user_id=user.id)
    total = base.count()
    drafts = base.filter_by(status=SiteStatus.draft).count()
    published = base.filter_by(status=SiteStatus.published).count()
    unpublished = base.filter_by(status=SiteStatus.unpublished).count()
    recent = base.order_by(Site.updated_at.desc()).limit(5).all()
    views = db.session.query(db.func.coalesce(db.func.sum(Site.page_views), 0)).filter(
        Site.user_id == user.id
    ).scalar() or 0
    return success_response({
        "total": total,
        "drafts": drafts,
        "published": published,
        "unpublished": unpublished,
        "total_views": int(views),
        "recent": [_serialize_site_card(s) for s in recent],
    })


@sites_bp.get("/my")
@jwt_required()
def my_sites():
    user = get_current_user()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 24))
    status = request.args.get("status")
    search = request.args.get("search")

    q = Site.query.filter_by(user_id=user.id)
    if status in {"draft", "published", "unpublished"}:
        q = q.filter(Site.status == SiteStatus(status))
    if search:
        q = q.filter(Site.name.ilike(f"%{search}%"))
    pagination = q.order_by(Site.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success_response(
        [_serialize_site_card(s) for s in pagination.items],
        total=pagination.total,
        page=page,
        per_page=per_page,
        pages=pagination.pages,
    )


@sites_bp.get("/<uuid:site_id>")
@jwt_required()
def get_site(site_id):
    site = Site.query.get(site_id)
    _, err = _ensure_owner(site)
    if err:
        return err
    # Backfill any missing default pages so legacy sites become multi-page
    # without requiring a manual migration.
    existing_slugs = {p.slug for p in site.pages}
    created = False
    for slug in DEFAULT_PAGES:
        if slug not in existing_slugs:
            _ensure_page(site, slug)
            created = True
    if created:
        db.session.commit()
    payload = SiteOutputSchema().dump(site)
    pages = sorted(site.pages, key=lambda p: p.order)
    payload["pages"] = PageOutputSchema(many=True).dump(pages)
    return success_response(payload)


@sites_bp.put("/<uuid:site_id>")
@jwt_required()
def rename_site(site_id):
    site = Site.query.get(site_id)
    _, err = _ensure_owner_writable(site)
    if err:
        return err
    payload = SiteRenameSchema().load(request.get_json() or {})
    site.name = payload["name"]
    db.session.commit()
    return success_response(_serialize_site_card(site))


@sites_bp.put("/<uuid:site_id>/global-styles")
@jwt_required()
def update_styles(site_id):
    site = Site.query.get(site_id)
    _, err = _ensure_owner_writable(site)
    if err:
        return err
    payload = SiteStylesSchema().load(request.get_json() or {})
    site.global_styles = payload["global_styles"]
    db.session.commit()
    return success_response(SiteOutputSchema().dump(site))


@sites_bp.put("/<uuid:site_id>/meta")
@jwt_required()
def update_meta(site_id):
    site = Site.query.get(site_id)
    _, err = _ensure_owner_writable(site)
    if err:
        return err
    payload = SiteMetaSchema().load(request.get_json() or {})
    for key, value in payload.items():
        setattr(site, key, value)
    db.session.commit()
    return success_response(SiteOutputSchema().dump(site))


@sites_bp.put("/<uuid:site_id>/pages/<page_slug>/sections")
@jwt_required()
def save_page_sections(site_id, page_slug):
    """Save the sections JSON for a page identified by slug.

    This is the editor's autosave target. If the page doesn't yet exist (e.g.
    a site created before multi-page support landed), we lazily scaffold it
    here so saves don't 404.
    """
    site = Site.query.get(site_id)
    _, err = _ensure_owner_writable(site)
    if err:
        return err
    if page_slug not in DEFAULT_PAGES:
        # Allow custom slugs too — but only ones the page actually has.
        target = next((p for p in site.pages if p.slug == page_slug), None)
        if not target:
            return error_response("Page not found", 404)
    else:
        target = next((p for p in site.pages if p.slug == page_slug), None)
        if not target:
            target = _ensure_page(site, page_slug)

    payload = SiteSectionsSchema().load(request.get_json() or {})
    target.sections = payload["sections"]
    # Touch site.updated_at so dashboard ordering reflects edits.
    site.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return success_response({
        "id": str(target.id),
        "site_id": str(site.id),
        "slug": target.slug,
        "sections": target.sections,
        "updated_at": target.updated_at.isoformat() if target.updated_at else None,
    })


def _ensure_page(site: Site, slug: str) -> Page:
    """Lazily create a default page on an existing site (legacy backfill)."""
    if slug == "home":
        sections = deepcopy(site.template.sections_config or []) if site.template else []
        page = Page(site_id=site.id, name="Home", slug="home", order=0, is_homepage=True, sections=sections)
    elif slug == "about":
        page = Page(site_id=site.id, name="About", slug="about", order=1, sections=_scaffold_about(site.name))
    elif slug == "services":
        page = Page(site_id=site.id, name="Services", slug="services", order=2, sections=_scaffold_services(site.name))
    elif slug == "contact":
        page = Page(site_id=site.id, name="Contact", slug="contact", order=3, sections=_scaffold_contact(site.name))
    else:
        page = Page(site_id=site.id, name=slug.title(), slug=slug, order=99, sections=[])
    db.session.add(page)
    db.session.flush()
    return page


def _has_paid_for_site(site: Site) -> bool:
    """A site can be published once any completed payment is linked to it
    (either directly via site_id, or via the template the site was created
    from — that's how template purchases bind to the new site)."""
    direct = (
        Payment.query.filter_by(site_id=site.id, status=PaymentStatus.completed).first()
        is not None
    )
    if direct:
        return True
    if site.template_id:
        return (
            Payment.query.filter_by(
                user_id=site.user_id,
                template_id=site.template_id,
                status=PaymentStatus.completed,
            ).first()
            is not None
        )
    return False


PLAN_PUBLISH_LIMITS = {
    UserPlan.free: 1,
    UserPlan.starter: 2,
    UserPlan.pro: 5,
    UserPlan.business: None,  # unlimited
}


def get_publish_slots(user) -> int | None:
    """Publish slots = sum of every still-active subscription grant. Each
    completed (non-template) payment grants its plan's slots for the paid
    period; an upgrade purchased while the previous plan is still running
    stacks on top, and each grant drops off when its own period ends.
    Returns None when any active grant is unlimited (business)."""
    if user is None:
        return PLAN_PUBLISH_LIMITS[UserPlan.free]

    payments = Payment.query.filter(
        Payment.user_id == user.id,
        Payment.status == PaymentStatus.completed,
        Payment.template_id.is_(None),
    ).all()

    now = datetime.now(timezone.utc)
    total = 0
    for p in payments:
        try:
            plan = UserPlan(p.plan)
        except ValueError:
            continue
        if plan == UserPlan.free:
            continue
        days = 365 if (p.billing_period or "").lower() == "yearly" else 30
        granted_at = p.created_at
        if granted_at.tzinfo is None:
            granted_at = granted_at.replace(tzinfo=timezone.utc)
        if granted_at + timedelta(days=days) <= now:
            continue
        slots = PLAN_PUBLISH_LIMITS.get(plan)
        if slots is None:
            return None
        total += slots

    return total if total > 0 else PLAN_PUBLISH_LIMITS[UserPlan.free]


@sites_bp.post("/<uuid:site_id>/publish")
@jwt_required()
def publish_site(site_id):
    site = Site.query.get(site_id)
    user, err = _ensure_owner_writable(site)
    if err:
        return err

    on_paid_plan = user.effective_plan() != UserPlan.free
    if not on_paid_plan and not _has_paid_for_site(site):
        return error_response("Payment required to publish this site", 402)

    if site.status != SiteStatus.published:
        limit = get_publish_slots(user)
        if limit is not None:
            used_slots = Site.query.filter(
                Site.user_id == user.id,
                Site.status == SiteStatus.published,
            ).count()
            if used_slots >= limit:
                return error_response(
                    f"You've used all {limit} of your publish slots. Unpublish a site or buy another plan to get more.",
                    403,
                )

    if not site.subdomain:
        base = slugify(site.name) or "site"
        for _ in range(3):
            candidate = f"{base}-{secrets.token_hex(3)}"
            if not Site.query.filter_by(subdomain=candidate).first():
                site.subdomain = candidate
                break

    site.status = SiteStatus.published
    site.hosted_url = f"/site/{site.id}"
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        site.subdomain = f"{slugify(site.name) or 'site'}-{secrets.token_hex(4)}"
        db.session.commit()
    return success_response(_serialize_site_card(site))


@sites_bp.post("/<uuid:site_id>/unpublish")
@jwt_required()
def unpublish_site(site_id):
    site = Site.query.get(site_id)
    _, err = _ensure_owner_writable(site)
    if err:
        return err
    site.status = SiteStatus.unpublished
    db.session.commit()
    return success_response(_serialize_site_card(site))


@sites_bp.post("/<uuid:site_id>/duplicate")
@jwt_required()
def duplicate_site(site_id):
    site = Site.query.get(site_id)
    user, err = _ensure_owner_writable(site)
    if err:
        return err

    clone = Site(
        user_id=user.id,
        template_id=site.template_id,
        name=f"{site.name} (Copy)",
        global_styles=deepcopy(site.global_styles or {}),
        meta_title=site.meta_title,
        meta_description=site.meta_description,
        favicon_url=site.favicon_url,
        status=SiteStatus.draft,
    )
    db.session.add(clone)
    db.session.flush()
    for p in site.pages:
        db.session.add(Page(
            site_id=clone.id,
            name=p.name,
            slug=p.slug,
            order=p.order,
            is_homepage=p.is_homepage,
            sections=deepcopy(p.sections or []),
        ))
    if site.template:
        site.template.usage_count += 1
    db.session.commit()
    return success_response(_serialize_site_card(clone))


@sites_bp.delete("/<uuid:site_id>")
@jwt_required()
def delete_site(site_id):
    site = Site.query.get(site_id)
    _, err = _ensure_owner_writable(site)
    if err:
        return err
    db.session.delete(site)
    db.session.commit()
    return success_response({"message": "Site deleted"})