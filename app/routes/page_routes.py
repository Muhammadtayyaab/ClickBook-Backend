from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.middleware.auth import get_current_user
from app.models import Page, Site
from app.schemas.page_schema import PageCreateSchema, PageOutputSchema, PageSectionsSchema, PageUpdateSchema, ReorderPagesSchema
from app.utils.responses import error_response, success_response

pages_bp = Blueprint("pages", __name__)


def _authorize_site(site_id):
    site = Site.query.get(site_id)
    if not site:
        return None, error_response("Site not found", 404)
    user = get_current_user()
    if user.role.value != "admin" and str(site.user_id) != str(user.id):
        return None, error_response("Forbidden", 403)
    return site, None


@pages_bp.get("/api/sites/<uuid:site_id>/pages")
@jwt_required()
def list_pages(site_id):
    _, err = _authorize_site(site_id)
    if err:
        return err
    pages = Page.query.filter_by(site_id=site_id).order_by(Page.order.asc()).all()
    return success_response(PageOutputSchema(many=True).dump(pages))


@pages_bp.post("/api/sites/<uuid:site_id>/pages")
@jwt_required()
def create_page(site_id):
    _, err = _authorize_site(site_id)
    if err:
        return err
    payload = PageCreateSchema().load(request.get_json() or {})
    max_order = db.session.query(db.func.max(Page.order)).filter_by(site_id=site_id).scalar() or 0
    page = Page(site_id=site_id, name=payload["name"], slug=payload["slug"], order=max_order + 1, sections=[])
    db.session.add(page)
    db.session.commit()
    return success_response(PageOutputSchema().dump(page))


@pages_bp.put("/api/sites/<uuid:site_id>/pages/<uuid:page_id>")
@jwt_required()
def update_page(site_id, page_id):
    _, err = _authorize_site(site_id)
    if err:
        return err
    payload = PageUpdateSchema().load(request.get_json() or {})
    page = Page.query.filter_by(id=page_id, site_id=site_id).first()
    if not page:
        return error_response("Page not found", 404)
    page.name = payload["name"]
    page.slug = payload["slug"]
    db.session.commit()
    return success_response(PageOutputSchema().dump(page))


@pages_bp.put("/api/sites/<uuid:site_id>/pages/<uuid:page_id>/sections")
@jwt_required()
def update_sections(site_id, page_id):
    _, err = _authorize_site(site_id)
    if err:
        return err
    payload = PageSectionsSchema().load(request.get_json() or {})
    page = Page.query.filter_by(id=page_id, site_id=site_id).first()
    if not page:
        return error_response("Page not found", 404)
    page.sections = payload["sections"]
    db.session.commit()
    return success_response(PageOutputSchema().dump(page))


@pages_bp.delete("/api/sites/<uuid:site_id>/pages/<uuid:page_id>")
@jwt_required()
def delete_page(site_id, page_id):
    _, err = _authorize_site(site_id)
    if err:
        return err
    page = Page.query.filter_by(id=page_id, site_id=site_id).first()
    if not page:
        return error_response("Page not found", 404)
    all_pages = Page.query.filter_by(site_id=site_id).count()
    if page.is_homepage and all_pages == 1:
        return error_response("Cannot delete the only homepage", 400)
    db.session.delete(page)
    db.session.commit()
    return success_response({"message": "Page deleted"})


@pages_bp.put("/api/sites/<uuid:site_id>/pages/reorder")
@jwt_required()
def reorder_pages(site_id):
    _, err = _authorize_site(site_id)
    if err:
        return err
    payload = ReorderPagesSchema().load(request.get_json() or {})
    for idx, page_id in enumerate(payload["page_ids"]):
        page = Page.query.filter_by(site_id=site_id, id=page_id).first()
        if page:
            page.order = idx
    db.session.commit()
    return success_response({"message": "Pages reordered"})
