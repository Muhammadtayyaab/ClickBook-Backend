from marshmallow import Schema, fields, validate


class DomainSchema(Schema):
    id = fields.UUID(dump_only=True)
    site_id = fields.UUID(required=True)
    domain = fields.Str(required=True, validate=validate.Length(min=3, max=255))
    type = fields.Method("_dump_type")
    is_verified = fields.Bool()
    verification_token = fields.Str(allow_none=True)
    ssl_status = fields.Str()
    created_at = fields.DateTime(dump_only=True)

    def _dump_type(self, obj):
        t = getattr(obj, "type", None)
        return getattr(t, "value", t)


class SubdomainCheckSchema(Schema):
    subdomain = fields.Str(required=True, validate=validate.Length(min=3, max=100))


class ClaimSubdomainSchema(SubdomainCheckSchema):
    site_id = fields.UUID(required=True)


class CustomDomainSchema(Schema):
    site_id = fields.UUID(required=True)
    domain = fields.Str(required=True, validate=validate.Length(min=3, max=255))


class VerifyCustomDomainSchema(Schema):
    domain = fields.Str(required=True)
