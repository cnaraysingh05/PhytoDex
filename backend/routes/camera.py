"""Raspberry Pi USB webcam endpoints.

GET  /api/camera/status
POST /api/camera/capture

A successful capture uses the same captures table and image URL contract as
POST /api/capture, so the existing /api/analysis pipeline can consume it.
"""
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from backend.models.db import get_db
from backend.services.webcam import (
    CameraCaptureError,
    CameraUnavailable,
    camera_status,
    capture_photo,
)


camera_bp = Blueprint("camera", __name__)


@camera_bp.get("/api/camera/status")
def camera_status_route():
    return jsonify(camera_status())


@camera_bp.post("/api/camera/capture")
def camera_capture_route():
    capture_dir = Path(current_app.config["CAPTURE_DIR"])
    capture_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.jpg"
    output_path = capture_dir / filename

    try:
        camera = capture_photo(output_path)
    except CameraUnavailable as exc:
        return jsonify(
            error=str(exc),
            code="camera_unavailable",
        ), 503
    except CameraCaptureError:
        return jsonify(
            error="USB camera capture failed. Check the camera connection and try again.",
            code="camera_capture_failed",
        ), 502

    image_url = f"/static/uploads/captures/{filename}"

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO captures (filename, image_url, status) VALUES (?, ?, 'stored')",
            (filename, image_url),
        )
        conn.commit()
        capture_id = cursor.lastrowid
    finally:
        conn.close()

    return jsonify(
        capture_id=capture_id,
        image_url=image_url,
        status="stored",
        camera=camera,
    ), 201
