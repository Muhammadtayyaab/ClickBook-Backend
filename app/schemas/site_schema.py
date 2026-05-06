from marshmallow import Schema, fields, validate


class SiteCreateSchema(Schema):
    template_id = fields.UUID(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=2, max=200))


class SiteRenameSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=200))


class SiteSectionsSchema(Schema):
    sections = fields.List(fields.Dict(), required=True)


class SiteStylesSchema(Schema):
    global_styles = fields.Dict(required=True)


class SiteMetaSchema(Schema):
    meta_title = fields.Str(validate=validate.Length(max=255), allow_none=True)
    meta_description = fields.Str(allow_none=True)
    favicon_url = fields.Url(allow_none=True)


class SiteOutputSchema(Schema):
    id = fields.UUID()
    user_id = fields.UUID()
    template_id = fields.UUID()
    name = fields.Str()
    subdomain = fields.Str(allow_none=True)
    custom_domain = fields.Str(allow_none=True)
    global_styles = fields.Dict()
    status = fields.Str()
    hosted_url = fields.Str(allow_none=True)
    favicon_url = fields.Str(allow_none=True)
    meta_title = fields.Str(allow_none=True)
    meta_description = fields.Str(allow_none=True)
    page_views = fields.Int()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
