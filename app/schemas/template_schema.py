from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class TemplateWriteSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=150))
    category = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    thumbnail_url = fields.Url(allow_none=True)
    preview_url = fields.Url(allow_none=True)
    # Backward-compatible home page sections (SectionDef[]).
    sections_config = fields.List(fields.Dict(), required=False, load_default=list)
    # Multi-page template document. Expected shape:
    # { "home": { "sections": [...] }, "about": { "sections": [...] }, ... }
    pages = fields.Dict(required=False, load_default=dict)
    global_styles = fields.Dict(required=True)
    is_featured = fields.Bool(load_default=False)

    @validates_schema
    def validate_layout(self, data, **kwargs):
        pages = data.get("pages") or {}
        sections = data.get("sections_config") or []
        if not pages and not sections:
            raise ValidationError("Provide either pages or sections_config", field_name="pages")


class TemplateOutputSchema(TemplateWriteSchema):
    id = fields.UUID(dump_only=True)
    slug = fields.Str()
    is_active = fields.Bool()
    usage_count = fields.Int()
    created_at = fields.DateTime()


class TemplateListQuerySchema(Schema):
    category = fields.Str(load_default=None)
    search = fields.Str(load_default=None)
    featured = fields.Bool(load_default=None)
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=10, validate=validate.Range(min=1, max=100))
