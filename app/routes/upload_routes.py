"""Legacy file upload endpoint. Kept for backwards compatibility — new code
should call ``/api/media/upload`` directly. Internally this delegates to the
same shared helper and records a ``MediaAsset`` row, so images uploaded from
older flows still appear in the user's media library.
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.middleware.auth import get_current_user
from app.models import MediaAsset
from app.utils.responses import error_response, success_response
from app.utils.uploads import UploadError, save_uploaded_image


upload_bp = Blueprint("uploads", __name__, url_prefix="/api")


@upload_bp.post("/upload")
@jwt_required()
def upload_file():
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

    return success_response({
        "id": str(asset.id),
        "url": info["absolute_url"],
        "path": info["rel_path"],
        "filename": info["filename"],
        "size": info["size"],
    })
