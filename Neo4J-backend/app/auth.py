"""Authenticate every backend request and bind employee writes to one server-owned identity."""

import hmac
import os

from flask import g, jsonify, request


def authenticate():
    """Fail closed unless a configured employee or administrator bearer token matches."""
    if request.path == "/health":
        return None
    employee_token = os.getenv("WHOKNOWS_AUTH_TOKEN", "")
    admin_token = os.getenv("WHOKNOWS_ADMIN_TOKEN", "")
    if not employee_token and not admin_token:
        return jsonify({"error": "Configure local backend authentication first."}), 503
    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    g.is_admin = bool(admin_token and token and hmac.compare_digest(token, admin_token))
    if not g.is_admin and not (employee_token and token and hmac.compare_digest(token, employee_token)):
        return jsonify({"error": "Authentication required."}), 401
    g.user_id = os.getenv("WHOKNOWS_USER_ID", "emp_014")
    if request.path not in {"/analyze", "/experts", "/preferences"} and not g.is_admin:
        return jsonify({"error": "Administrator access required."}), 403
    return None
