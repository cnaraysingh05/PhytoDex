"""
GET /api/health -- frontend connectivity check.
Contract (framework Section 7): {"status": "ok"}
"""
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
