from marshmallow import Schema, fields, validate


class PageCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    slug = fields.Str(required=True, validate=validate.Length(min=1, max=100))


class PageUpdateSchema(PageCreateSchema):
    pass


class PageSectionsSchema(Schema):
    sections = fields.List(fields.Dict(), required=True)


class ReorderPagesSchema(Schema):
    page_ids = fields.List(fields.UUID(), required=True, validate=validate.Length(min=1))


class PageOutputSchema(Schema):
    id = fields.UUID()
    site_id = fields.UUID()
    name = fields.Str()
    slug = fields.Str()
    order = fields.Int()
    is_homepage = fields.Bool()
    sections = fields.List(fields.Dict())
    updated_at = fields.DateTime()
