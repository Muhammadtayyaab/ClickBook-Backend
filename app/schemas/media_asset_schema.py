from marshmallow import Schema, fields


class MediaAssetOutputSchema(Schema):
    id = fields.UUID(dump_only=True)
    file_name = fields.Str()
    original_name = fields.Str(allow_none=True)
    file_url = fields.Str()
    file_path = fields.Str()
    file_type = fields.Str()
    size = fields.Int()
    created_at = fields.DateTime()
