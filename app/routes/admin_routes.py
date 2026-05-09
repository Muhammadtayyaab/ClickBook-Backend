"""Admin routes.

All endpoints require a JWT whose user has role=admin. They implement:
 - Dashboard KPIs & timeseries
 - User CRUD + suspend/activate + CSV export
 - Template CRUD (soft delete)
 - Site list + delete
 - Payments overview, listing, filtering, CSV export
 - Audit log read endpoint
"""
import csv
import io
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, send_file
from flask_jwt_extended import jwt_required
from sqlalchemy import func, or_
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.middleware.auth import admin_required, get_current_user
from app.models import AuditLog, Payment, Site, Template, User
from app.models.payment import PaymentStatus
from app.models.user import UserPlan, UserRole
from app.schemas.template_schema import TemplateOutputSchema, TemplateWriteSchema
from app.schemas.user_schema import UserOutputSchema
from app.utils.helpers import slugify
from app.utils.responses import error_response, success_response

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _log(action: str, target_type: str | None = None, target_id: str | None = None, **meta) -> None:
    """Write an entry to the audit log. Never raises to avoid breaking requests."""
    try:
        actor = get_current_user()
        entry = AuditLog(
            actor_user_id=actor.id if actor else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            meta=meta or {},
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _apply_admin_plan_change(
    user: User,
    new_plan: UserPlan,
    billing_period: str | None = None,
) -> None:
    """Move the user to `new_plan` by manipulating grants, not by writing
    User.plan directly. Slots and effective_plan() are derived from
    completed Payment rows, so admin overrides have to be expressed the
    same way: cancel any active grants and (for paid plans) write a
    synthetic admin-issued Payment that grants the new tier for the
    requested period. Nothing here writes user.plan / plan_expires_at —
    sync_plan_snapshot() does that from the resulting grant set."""
    user.cancel_active_subscriptions()

    if new_plan != UserPlan.free:
        period = (billing_period or "").lower()
        if period not in {"monthly", "yearly"}:
            period = "monthly"
        admin_grant = Payment(
            user_id=user.id,
            amount=0,
            currency="usd",
            plan=new_plan.value,
            billing_period=period,
            status=PaymentStatus.completed,
            user_email_snapshot=user.email,
            user_name_snapshot=user.name,
        )
        db.session.add(admin_grant)

    db.session.flush()
    user.sync_plan_snapshot()


def _paginate(query, default_per=10):
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", default_per)), 1), 100)
    return query.paginate(page=page, per_page=per_page, error_out=False), page, per_page


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------

@admin_bp.get("/dashboard")
@jwt_required()
@admin_required
def dashboard():
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)

    total_revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter_by(status="completed").scalar() or 0

    monthly_revenue_amount = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.status == "completed",
        Payment.created_at >= thirty_days_ago,
    ).scalar() or 0

    prev_month_revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.status == "completed",
        Payment.created_at >= sixty_days_ago,
        Payment.created_at < thirty_days_ago,
    ).scalar() or 0

    active_subscriptions = User.query.filter(User.plan != UserPlan.free, User.is_active == True).count()

    # simple churn proxy: users who became inactive in the last 30 days / active at start
    churned = User.query.filter(User.is_active == False, User.created_at < thirty_days_ago).count()
    active_at_start = User.query.filter(User.created_at < thirty_days_ago).count() or 1
    churn_rate = round((churned / active_at_start) * 100, 2)

    signup_month = func.date_trunc("month", User.created_at).label("month")
    monthly_signups = (
        db.session.query(signup_month, func.count(User.id))
        .group_by(signup_month)
        .order_by(signup_month.desc())
        .limit(12)
        .all()
    )

    revenue_month = func.date_trunc("month", Payment.created_at).label("month")
    monthly_revenue = (
        db.session.query(revenue_month, func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == "completed")
        .group_by(revenue_month)
        .order_by(revenue_month.desc())
        .limit(12)
        .all()
    )

    return success_response({
        "total_users": User.query.count(),
        "total_templates": Template.query.filter_by(is_active=True).count(),
        "total_sites": Site.query.count(),
        "total_revenue": int(total_revenue),
        "monthly_revenue": int(monthly_revenue_amount),
        "prev_month_revenue": int(prev_month_revenue),
        "active_subscriptions": active_subscriptions,
        "churn_rate": churn_rate,
        "new_signups_30d": User.query.filter(User.created_at >= thirty_days_ago).count(),
        "signups_by_month": [
            {"month": m[0].isoformat(), "count": int(m[1])} for m in reversed(monthly_signups)
        ],
        "revenue_by_month": [
            {"month": m[0].isoformat(), "amount": int(m[1])} for m in reversed(monthly_revenue)
        ],
    })


@admin_bp.get("/activity")
@jwt_required()
@admin_required
def recent_activity():
    limit = min(int(request.args.get("limit", 20)), 100)
    logs = (
        AuditLog.query
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return success_response([
        {
            "id": str(log.id),
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "meta": log.meta or {},
            "actor": {
                "id": str(log.actor.id) if log.actor else None,
                "name": log.actor.name if log.actor else "system",
                "email": log.actor.email if log.actor else None,
            } if log.actor else None,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ])


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

@admin_bp.get("/users")
@jwt_required()
@admin_required
def list_users():
    q = User.query
    if search := request.args.get("search"):
        q = q.filter(or_(User.name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")))
    if plan := request.args.get("plan"):
        q = q.filter_by(plan=plan)
    if role := request.args.get("role"):
        q = q.filter_by(role=role)
    if (status := request.args.get("status")) in {"active", "suspended"}:
        q = q.filter(User.is_active == (status == "active"))

    sort = request.args.get("sort", "created_at")
    direction = request.args.get("order", "desc")
    column = getattr(User, sort, User.created_at)
    q = q.order_by(column.desc() if direction == "desc" else column.asc())

    p, page, per_page = _paginate(q)
    data = []
    for user in p.items:
        data.append({
            **UserOutputSchema().dump(user),
            "site_count": len(user.sites),
            "total_spend": sum(pay.amount for pay in user.payments if pay.status.value == "completed"),
        })
    return success_response(data, total=p.total, page=page, per_page=per_page, pages=p.pages)


@admin_bp.get("/users/<uuid:user_id>")
@jwt_required()
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    payload = UserOutputSchema().dump(user)
    payload["sites"] = [
        {"id": str(s.id), "name": s.name, "status": s.status.value} for s in user.sites
    ]
    payload["payments"] = [
        {"id": str(p.id), "amount": p.amount, "status": p.status.value, "created_at": p.created_at.isoformat()}
        for p in user.payments
    ]
    return success_response(payload)


@admin_bp.post("/users")
@jwt_required()
@admin_required
def create_user():
    data = request.get_json() or {}
    required = {"name", "email", "password"}
    missing = [f for f in required if not data.get(f)]
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}", 400)
    email = data["email"].strip().lower()
    if User.query.filter_by(email=email).first():
        return error_response("Email already in use", 409)
    role = data.get("role", "user")
    plan = data.get("plan", "free")
    if role not in [r.value for r in UserRole]:
        return error_response("Invalid role", 400)
    if plan not in [p.value for p in UserPlan]:
        return error_response("Invalid plan", 400)
    plan_enum = UserPlan(plan)
    user = User(
        name=data["name"].strip(),
        email=email,
        password_hash=generate_password_hash(data["password"]),
        role=UserRole(role),
        plan=UserPlan.free,
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(user)
    db.session.flush()
    if plan_enum != UserPlan.free:
        _apply_admin_plan_change(user, plan_enum, data.get("billing_period"))
    db.session.commit()
    _log("user.create", "user", user.id, email=user.email)
    return success_response(UserOutputSchema().dump(user))


@admin_bp.put("/users/<uuid:user_id>")
@jwt_required()
@admin_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json() or {}
    changed = {}

    requested_plan: UserPlan | None = None
    if "plan" in data:
        if data["plan"] not in [p.value for p in UserPlan]:
            return error_response("Invalid plan", 400)
        requested_plan = UserPlan(data["plan"])

    for field in ["name", "role", "is_active"]:
        if field in data:
            value = data[field]
            if field == "role":
                if value not in [r.value for r in UserRole]:
                    return error_response("Invalid role", 400)
                value = UserRole(value)
            setattr(user, field, value)
            changed[field] = data[field]

    if requested_plan is not None and requested_plan != user.effective_plan():
        _apply_admin_plan_change(user, requested_plan, data.get("billing_period"))
        changed["plan"] = requested_plan.value
        changed["plan_expires_at"] = (
            user.plan_expires_at.isoformat() if user.plan_expires_at else None
        )

    if "password" in data and data["password"]:
        user.password_hash = generate_password_hash(data["password"])
        changed["password"] = "***"
    db.session.commit()
    _log("user.update", "user", user.id, changed=changed)
    return success_response(UserOutputSchema().dump(user))


@admin_bp.post("/users/<uuid:user_id>/suspend")
@jwt_required()
@admin_required
def suspend_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = False
    user.tokens_invalid_after = datetime.now(timezone.utc)
    db.session.commit()
    _log("user.suspend", "user", user.id)
    return success_response(UserOutputSchema().dump(user))


@admin_bp.post("/users/<uuid:user_id>/activate")
@jwt_required()
@admin_required
def activate_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    _log("user.activate", "user", user.id)
    return success_response(UserOutputSchema().dump(user))


@admin_bp.delete("/users/<uuid:user_id>")
@jwt_required()
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    actor = get_current_user()
    if actor and str(actor.id) == str(user.id):
        return error_response("You cannot delete your own account", 400)
    email = user.email
    for pay in user.payments:
        pay.user_email_snapshot = user.email
        pay.user_name_snapshot = user.name
    db.session.flush()
    db.session.delete(user)
    db.session.commit()
    _log("user.delete", "user", user_id, email=email)
    return success_response({"message": "User deleted"})


@admin_bp.get("/users/export-csv")
@jwt_required()
@admin_required
def export_users_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "email", "role", "plan", "is_active", "created_at"])
    for u in User.query.order_by(User.created_at.desc()).all():
        writer.writerow([
            str(u.id), u.name, u.email, u.role.value, u.plan.value,
            "true" if u.is_active else "false", u.created_at.isoformat(),
        ])
    _log("user.export_csv")
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="users.csv",
    )


# ---------------------------------------------------------------------------
# templates
# ---------------------------------------------------------------------------

@admin_bp.get("/templates")
@jwt_required()
@admin_required
def admin_templates():
    q = Template.query
    if search := request.args.get("search"):
        q = q.filter(Template.name.ilike(f"%{search}%"))
    if category := request.args.get("category"):
        q = q.filter_by(category=category)
    return success_response(
        TemplateOutputSchema(many=True).dump(q.order_by(Template.created_at.desc()).all())
    )


@admin_bp.get("/templates/<uuid:template_id>")
@jwt_required()
@admin_required
def template_detail(template_id):
    t = Template.query.get_or_404(template_id)
    return success_response(TemplateOutputSchema().dump(t))


@admin_bp.post("/templates")
@jwt_required()
@admin_required
def create_template():
    payload = TemplateWriteSchema().load(request.get_json() or {})
    # If the caller sent a multi-page document, keep `sections_config` in sync
    # for backward-compatible consumers (home page seed).
    if payload.get("pages") and not payload.get("sections_config"):
        home = payload["pages"].get("home") if isinstance(payload["pages"], dict) else None
        if isinstance(home, dict) and isinstance(home.get("sections"), list):
            payload["sections_config"] = home["sections"]
    slug = slugify(payload["name"])
    if Template.query.filter_by(slug=slug).first():
        slug = f"{slug}-{int(datetime.now().timestamp())}"
    t = Template(**payload, slug=slug)
    db.session.add(t)
    db.session.commit()
    _log("template.create", "template", t.id, name=t.name)
    return success_response(TemplateOutputSchema().dump(t))


@admin_bp.put("/templates/<uuid:template_id>")
@jwt_required()
@admin_required
def update_template(template_id):
    t = Template.query.get_or_404(template_id)
    payload = request.get_json() or {}
    if "name" in payload and payload["name"]:
        payload["slug"] = slugify(payload["name"])
    if "pages" in payload and "sections_config" not in payload:
        home = payload["pages"].get("home") if isinstance(payload.get("pages"), dict) else None
        if isinstance(home, dict) and isinstance(home.get("sections"), list):
            payload["sections_config"] = home["sections"]
    for k, v in payload.items():
        if hasattr(t, k):
            setattr(t, k, v)
    db.session.commit()
    _log("template.update", "template", t.id, name=t.name)
    return success_response(TemplateOutputSchema().dump(t))


@admin_bp.delete("/templates/<uuid:template_id>")
@jwt_required()
@admin_required
def soft_delete_template(template_id):
    t = Template.query.get_or_404(template_id)
    t.is_active = False
    db.session.commit()
    _log("template.delete", "template", t.id, name=t.name)
    return success_response({"message": "Template deactivated"})


# ---------------------------------------------------------------------------
# sites
# ---------------------------------------------------------------------------

@admin_bp.get("/sites")
@jwt_required()
@admin_required
def all_sites():
    data = [{
        "id": str(s.id),
        "name": s.name,
        "owner_email": s.owner.email,
        "domain": s.custom_domain or s.subdomain,
        "status": s.status.value,
        "template_name": s.template.name if s.template else None,
    } for s in Site.query.all()]
    return success_response(data)


@admin_bp.delete("/sites/<uuid:site_id>")
@jwt_required()
@admin_required
def delete_site(site_id):
    s = Site.query.get_or_404(site_id)
    name = s.name
    db.session.delete(s)
    db.session.commit()
    _log("site.delete", "site", site_id, name=name)
    return success_response({"message": "Site deleted"})


# ---------------------------------------------------------------------------
# payments
# ---------------------------------------------------------------------------

@admin_bp.get("/payments")
@jwt_required()
@admin_required
def all_payments():
    q = Payment.query.outerjoin(User, User.id == Payment.user_id)
    if email := request.args.get("email"):
        term = f"%{email}%"
        q = q.filter(db.or_(User.email.ilike(term), Payment.user_email_snapshot.ilike(term)))
    if status := request.args.get("status"):
        q = q.filter(Payment.status == status)
    if date_from := request.args.get("date_from"):
        q = q.filter(Payment.created_at >= date_from)
    if date_to := request.args.get("date_to"):
        q = q.filter(Payment.created_at <= date_to)

    p, page, per_page = _paginate(q.order_by(Payment.created_at.desc()))
    data = [{
        "id": str(pay.id),
        "user_email": pay.user.email if pay.user else pay.user_email_snapshot,
        "user_name": pay.user.name if pay.user else pay.user_name_snapshot,
        "amount": pay.amount,
        "currency": pay.currency,
        "status": pay.status.value,
        "plan": pay.plan,
        "billing_period": pay.billing_period,
        "created_at": pay.created_at.isoformat(),
    } for pay in p.items]
    return success_response(data, total=p.total, page=page, per_page=per_page, pages=p.pages)


@admin_bp.get("/payments/export-csv")
@admin_bp.post("/payments/export-csv")
@jwt_required()
@admin_required
def export_payments_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_email", "amount", "status", "plan", "billing_period", "created_at"])
    for p in Payment.query.order_by(Payment.created_at.desc()).all():
        writer.writerow([
            str(p.id),
            p.user.email if p.user else p.user_email_snapshot,
            p.amount, p.status.value, p.plan,
            p.billing_period, p.created_at.isoformat(),
        ])
    _log("payment.export_csv")
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="payments.csv",
    )
