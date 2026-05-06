from flask import Blueprint, request
from sqlalchemy import or_

from app.extensions import db
from app.models import Template
from app.schemas.template_schema import TemplateListQuerySchema, TemplateOutputSchema
from app.utils.responses import error_response, success_response

templates_bp = Blueprint("templates", __name__, url_prefix="/api/templates")


@templates_bp.get("/")
def list_templates():
    args = TemplateListQuerySchema().load(request.args)
    query = Template.query.filter_by(is_active=True)
    if args.get("category"):
        query = query.filter_by(category=args["category"])
    if args.get("featured") is not None:
        query = query.filter_by(is_featured=args["featured"])
    if args.get("search"):
        query = query.filter(or_(Template.name.ilike(f"%{args['search']}%"), Template.slug.ilike(f"%{args['search']}%")))

    pagination = query.order_by(Template.created_at.desc()).paginate(page=args["page"], per_page=args["per_page"], error_out=False)
    return success_response(
        TemplateOutputSchema(many=True).dump(pagination.items),
        total=pagination.total,
        page=pagination.page,
        per_page=pagination.per_page,
        pages=pagination.pages,
    )


@templates_bp.get("/<uuid:template_id>")
def get_template(template_id):
    template = Template.query.get(template_id)
    if not template or not template.is_active:
        return error_response("Template not found", 404)
    return success_response(TemplateOutputSchema().dump(template))
