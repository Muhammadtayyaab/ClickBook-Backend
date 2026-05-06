"""Analytics endpoints — summary, time-series, top pages.

All routes scope to a single site_id and enforce that the caller owns it
(or is admin). Counts come from the `page_views` events table; the cached
`Site.page_views` counter is only used as a sanity fallback.
"""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from app.extensions import db
from app.middleware.auth import get_current_user
from app.models import PageView, Site
from app.utils.responses import error_response, success_response

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


_RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _ensure_owner(site_id):
    """Resolve a site and confirm the current user can read its analytics."""
    user = get_current_user()
    if not user:
        return None, None, error_response("Authentication required", 401)
    site = Site.query.get(site_id)
    if not site:
        return user, None, error_response("Site not found", 404)
    if user.role.value != "admin" and str(site.user_id) != str(user.id):
        return user, site, error_response("Forbidden", 403)
    return user, site, None


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


@analytics_bp.get("/summary/<uuid:project_id>")
@jwt_required()
def summary(project_id):
    _, site, err = _ensure_owner(project_id)
    if err:
        return err

    now = datetime.now(timezone.utc)
    today_start = _start_of_day(now)
    week_start = today_start - timedelta(days=6)
    month_start = today_start - timedelta(days=29)

    base = db.session.query(func.count(PageView.id)).filter(PageView.site_id == site.id)

    total = base.scalar() or 0
    views_today = base.filter(PageView.ts >= today_start).scalar() or 0
    views_week = base.filter(PageView.ts >= week_start).scalar() or 0
    views_month = base.filter(PageView.ts >= month_start).scalar() or 0

    return success_response({
        "total_views": int(total),
        "views_today": int(views_today),
        "views_this_week": int(views_week),
        "views_this_month": int(views_month),
    })


@analytics_bp.get("/timeseries/<uuid:project_id>")
@jwt_required()
def timeseries(project_id):
    _, site, err = _ensure_owner(project_id)
    if err:
        return err

    range_key = request.args.get("range", "7d")
    days = _RANGE_DAYS.get(range_key)
    if days is None:
        return error_response("Invalid range. Use 7d, 30d, or 90d.", 400)

    today = _start_of_day(datetime.now(timezone.utc))
    start = today - timedelta(days=days - 1)

    # Group by date (UTC). cast to date so we get one row per day.
    day_col = func.date_trunc("day", PageView.ts).label("day")
    rows = (
        db.session.query(day_col, func.count(PageView.id))
        .filter(PageView.site_id == site.id, PageView.ts >= start)
        .group_by(day_col)
        .all()
    )
    counts = {row[0].date().isoformat(): int(row[1]) for row in rows}

    series = []
    for i in range(days):
        d = (start + timedelta(days=i)).date().isoformat()
        series.append({"date": d, "views": counts.get(d, 0)})

    return success_response(series)


@analytics_bp.get("/top-pages/<uuid:project_id>")
@jwt_required()
def top_pages(project_id):
    _, site, err = _ensure_owner(project_id)
    if err:
        return err

    range_key = request.args.get("range", "30d")
    days = _RANGE_DAYS.get(range_key)
    if days is None:
        return error_response("Invalid range. Use 7d, 30d, or 90d.", 400)

    start = _start_of_day(datetime.now(timezone.utc)) - timedelta(days=days - 1)
    limit = min(int(request.args.get("limit", 10) or 10), 50)

    rows = (
        db.session.query(PageView.page_slug, func.count(PageView.id))
        .filter(PageView.site_id == site.id, PageView.ts >= start)
        .group_by(PageView.page_slug)
        .order_by(func.count(PageView.id).desc())
        .limit(limit)
        .all()
    )
    return success_response([
        {"page_slug": slug or "(home)", "views": int(count)} for slug, count in rows
    ])