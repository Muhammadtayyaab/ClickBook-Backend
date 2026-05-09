from functools import wraps
from flask_jwt_extended import get_jwt_identity
from app.models import Site, User
from app.utils.responses import error_response


def get_current_user():
    identity = get_jwt_identity()
    if not identity:
        return None
    return User.query.get(identity)


def _ensure_active(user):
    if not user.is_active:
        return error_response("Account suspended", 403)
    return None


def active_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return error_response("Authentication required", 401)
        if (resp := _ensure_active(user)) is not None:
            return resp
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return error_response("Authentication required", 401)
        if (resp := _ensure_active(user)) is not None:
            return resp
        if user.role.value != "admin":
            return error_response("Admin access required", 403)
        return fn(*args, **kwargs)

    return wrapper


def owner_or_admin_required(model, param_name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return error_response("Authentication required", 401)
            if (resp := _ensure_active(user)) is not None:
                return resp
            record = model.query.get(kwargs.get(param_name))
            if not record:
                return error_response("Resource not found", 404)

            owner_id = getattr(record, "user_id", None)
            if owner_id is None:
                site_id = getattr(record, "site_id", None)
                if site_id:
                    site = Site.query.get(site_id)
                    owner_id = site.user_id if site else None

            if user.role.value != "admin" and str(owner_id) != str(user.id):
                return error_response("Forbidden", 403)
            kwargs[f"{param_name}_obj"] = record
            return fn(*args, **kwargs)

        return wrapper

    return decorator
