from copy import deepcopy

from app.extensions import db
from app.models import Page, Site, Template


def create_project_from_template(*, user_id, template_id, project_name: str | None = None) -> Site:
    template = Template.query.get(template_id)
    if not template or not template.is_active:
        raise ValueError("Template not found")

    name = (project_name or "").strip() or f"{template.name} Project"
    site = Site(
        user_id=user_id,
        template_id=template.id,
        name=name,
        global_styles=deepcopy(template.global_styles or {}),
    )
    db.session.add(site)
    db.session.flush()

    tpl_pages = deepcopy(getattr(template, "pages", None) or {})

    def _sections(slug: str):
        entry = tpl_pages.get(slug)
        if isinstance(entry, dict) and isinstance(entry.get("sections"), list):
            return deepcopy(entry["sections"])
        if slug == "home":
            return deepcopy(template.sections_config or [])
        return []

    for idx, (title, slug, is_homepage) in enumerate((
        ("Home", "home", True),
        ("About", "about", False),
        ("Services", "services", False),
        ("Contact", "contact", False),
    )):
        db.session.add(Page(
            site_id=site.id,
            name=title,
            slug=slug,
            order=idx,
            is_homepage=is_homepage,
            sections=_sections(slug),
        ))

    template.usage_count += 1
    db.session.flush()
    return site
