from flask import jsonify


def success_response(data=None, **meta):
    payload = {"success": True, "data": data}
    payload.update(meta)
    return jsonify(payload)


def error_response(message, status_code=400, errors=None):
    payload = {"success": False, "message": message}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), status_code
