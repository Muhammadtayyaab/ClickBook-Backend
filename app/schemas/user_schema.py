from marshmallow import Schema, fields, validate


class UserCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=150))
    email = fields.Email(required=True, validate=validate.Length(max=255))
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=8, max=128))


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)


class UserOutputSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str()
    email = fields.Email()
    # role/plan are SQLAlchemy ENUMs — serialise the enum's .value, otherwise
    # marshmallow dumps "UserRole.admin" which breaks frontend role checks.
    role = fields.Function(lambda obj: obj.role.value if obj.role else None)
    plan = fields.Function(lambda obj: obj.plan.value if obj.plan else None)
    plan_expires_at = fields.DateTime(allow_none=True)
    is_active = fields.Bool()
    avatar_url = fields.Str(allow_none=True)
    last_login_at = fields.DateTime(allow_none=True)
    email_notifications_enabled = fields.Bool()
    contact_email = fields.Email(allow_none=True)
    created_at = fields.DateTime()


class NotificationPrefsSchema(Schema):
    email_notifications_enabled = fields.Bool(required=False)
    contact_email = fields.Email(required=False, allow_none=True, validate=validate.Length(max=255))


class ContactFormSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=150))
    email = fields.Email(required=True, validate=validate.Length(max=255))
    message = fields.Str(required=True, validate=validate.Length(min=1, max=5000))


class UpdateProfileSchema(Schema):
    name = fields.Str(required=False, validate=validate.Length(min=2, max=150))
    email = fields.Email(required=False, validate=validate.Length(max=255))
    avatar_url = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))


class ChangePasswordSchema(Schema):
    current_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8, max=128))


class ForgotPasswordSchema(Schema):
    email = fields.Email(required=True)


class ResetPasswordSchema(Schema):
    token = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8, max=128))
