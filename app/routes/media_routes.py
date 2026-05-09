"""Centralized media library endpoints. Each upload is recorded as a
``MediaAsset`` row tied to the uploading user, so users can browse, reuse,
and delete their assets across the app.
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.middleware.auth import active_required, get_current_user
from app.models import MediaAsset, User
from app.schemas.media_asset_schema import MediaAssetOutputSchema
from app.utils.responses import error_response, success_response
from app.utils.uploads import UploadError, remove_upload, save_uploaded_image


media_bp = Blueprint("media", __name__, url_prefix="/api/media")


def _serialize(asset: MediaAsset) -> dict:
    return MediaAssetOutputSchema().dump(asset)


def _get_owned_asset(asset_id):
    user = get_current_user()
    if not user:
        return None, error_response("Authentication required", 401)
    asset = MediaAsset.query.get(asset_id)
    if not asset:
        return None, error_response("Media not found", 404)
    if user.role.value != "admin" and str(asset.user_id) != str(user.id):
        return None, error_response("Forbidden", 403)
    return asset, None


@media_bp.post("/upload")
@jwt_required()
@active_required
def upload_media():
    user = get_current_user()
    if not user:
        return error_response("Authentication required", 401)
    if "file" not in request.files:
        return error_response("No file provided", 400)

    try:
        info = save_uploaded_image(request.files["file"])
    except UploadError as exc:
        return error_response(exc.message, exc.status)

    asset = MediaAsset(
        user_id=user.id,
        file_name=info["filename"],
        original_name=info["original_name"],
        file_url=info["absolute_url"],
        file_path=info["rel_path"],
        file_type=info["mime"],
        size=info["size"],
    )
    db.session.add(asset)
    db.session.commit()
    return success_response(_serialize(asset))


@media_bp.get("")
@media_bp.get("/")
@jwt_required()
def list_media():
    user = get_current_user()
    if not user:
        return error_response("Authentication required", 401)

    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = min(max(int(request.args.get("per_page", 24)), 1), 100)
    except ValueError:
        return error_response("Invalid pagination", 400)

    query = MediaAsset.query
    show_all = request.args.get("all") == "1" and user.role.value == "admin"
    if not show_all:
        query = query.filter(MediaAsset.user_id == user.id)
    query = query.order_by(MediaAsset.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = MediaAssetOutputSchema(many=True).dump(pagination.items)

    # When admin asks for all assets, attach owner info so the admin UI can show
    # who uploaded what without N+1 lookups on the client.
    if show_all and pagination.items:
        owner_ids = {a.user_id for a in pagination.items}
        owners = {u.id: u for u in User.query.filter(User.id.in_(owner_ids)).all()}
        for item, asset in zip(items, pagination.items):
            owner = owners.get(asset.user_id)
            item["user_id"] = str(asset.user_id)
            item["user_name"] = owner.name if owner else None
            item["user_email"] = owner.email if owner else None

    return success_response({
        "items": items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
    })


@media_bp.get("/<asset_id>")
@jwt_required()
def get_media(asset_id):
    asset, err = _get_owned_asset(asset_id)
    if err:
        return err
    return success_response(_serialize(asset))


@media_bp.delete("/<asset_id>")
@jwt_required()
@active_required
def delete_media(asset_id):
    asset, err = _get_owned_asset(asset_id)
    if err:
        return err

    file_name = asset.file_name
    db.session.delete(asset)
    db.session.commit()
    remove_upload(file_name)
    return success_response({"deleted": str(asset_id)})
