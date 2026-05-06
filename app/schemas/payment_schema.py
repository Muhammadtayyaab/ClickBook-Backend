from marshmallow import Schema, ValidationError, fields, validate


class PaymentCreateSchema(Schema):
    site_id = fields.UUID(required=True)
    plan = fields.Str(required=True, validate=validate.OneOf(["starter", "pro", "business"]))
    billing_period = fields.Str(required=True, validate=validate.OneOf(["monthly", "yearly"]))


class TemplatePaymentCreateSchema(Schema):
    template_id = fields.UUID(required=True)
    project_name = fields.Str(load_default=None, allow_none=True)
    plan = fields.Str(required=True, validate=validate.OneOf(["starter", "pro", "business"]))
    billing_period = fields.Str(required=True, validate=validate.OneOf(["monthly", "yearly"]))

    def validate_project_name(self, data, **kwargs):
        name = (data.get("project_name") or "").strip()
        if name and len(name) > 200:
            raise ValidationError("Project name cannot exceed 200 characters", field_name="project_name")


class PaymentOutputSchema(Schema):
    id = fields.UUID()
    user_id = fields.UUID()
    site_id = fields.UUID(allow_none=True)
    template_id = fields.UUID(allow_none=True)
    stripe_session_id = fields.Str(allow_none=True)
    stripe_payment_intent_id = fields.Str(allow_none=True)
    amount = fields.Int()
    currency = fields.Str()
    # PaymentStatus is a (str, Enum) — in Python 3.12 str() returns the
    # "PaymentStatus.completed" repr, not the value. Force the value here so
    # the client sees "completed" / "pending" / "failed".
    status = fields.Method("_status")
    plan = fields.Str()
    billing_period = fields.Str()
    created_at = fields.DateTime()

    def _status(self, obj):
        s = getattr(obj, "status", None)
        return getattr(s, "value", s) if s is not None else None
