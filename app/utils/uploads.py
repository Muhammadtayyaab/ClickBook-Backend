"""Shared file upload primitives. Both /api/upload and /api/media/upload use
``save_uploaded_image`` so the storage layout, validation, and naming scheme
stay consistent.
"""
import os
import secrets
import uuid

from flask import current_app, url_for
from werkzeug.utils import secure_filename


ALLOWED_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "avif"}
MAX_BYTES = 8 * 1024 * 1024  # 8 MB


class UploadError(Exception):
    """Raised when an uploaded file fails validation. ``status`` is the HTTP
    status the route should respond with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _ext_ok(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTS


def uploads_dir() -> str:
    folder = os.path.join(current_app.static_folder or "static", "uploads")
    os.makedirs(folder, exist_ok=True)
    return folder


def save_uploaded_image(file) -> dict:
    """Validate and persist an image upload. Returns a dict with the absolute
    URL, relative path, stored filename, original filename, mime, and size.
    """
    if not file or not file.filename:
        raise UploadError("No file selected", 400)
    if not _ext_ok(file.filename):
        raise UploadError("Unsupported file type", 400)

    # Flask streams the upload, so we seek to learn the size.
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > MAX_BYTES:
        raise UploadError("File too large (max 8 MB)", 413)

    original_name = file.filename
    base = secure_filename(original_name) or "upload"
    _, _, ext = base.rpartition(".")
    safe_ext = (ext or "bin").lower()
    final_name = f"{uuid.uuid4().hex}_{secrets.token_hex(3)}.{safe_ext}"
    folder = uploads_dir()
    file.save(os.path.join(folder, final_name))

    rel_path = f"/static/uploads/{final_name}"
    try:
        absolute = url_for("static", filename=f"uploads/{final_name}", _external=True)
    except Exception:
        absolute = rel_path

    return {
        "absolute_url": absolute,
        "rel_path": rel_path,
        "filename": final_name,
        "original_name": original_name,
        "mime": (file.mimetype or "").lower() or f"image/{safe_ext}",
        "size": size,
    }


def remove_upload(filename: str) -> None:
    """Best-effort delete of an uploaded file from disk. Silently ignores
    missing files so deleting a DB row stays idempotent."""
    folder = uploads_dir()
    path = os.path.join(folder, filename)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError:
        # Permission or other transient errors — skip rather than blow up the API.
        pass
