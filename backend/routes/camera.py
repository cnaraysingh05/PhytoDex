"""Raspberry Pi USB webcam endpoints.

GET  /api/camera/status
GET  /api/camera/preview
POST /api/camera/preview/stop
POST /api/camera/capture

The live preview does not create database rows or stored photos.
Only POST /api/camera/capture creates a permanent capture.
"""
import uuid
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    stream_with_context,
)

from backend.models.db import get_db
from backend.services.webcam import (
    CameraCaptureError,
    CameraPreviewError,
    CameraUnavailable,
    camera_status,
    capture_photo,
    preview_frames,
    stop_preview,
)


camera_bp = Blueprint("camera", __name__)


@camera_bp.get("/api/camera/status")
def camera_status_route():
    return jsonify(camera_status())


@camera_bp.get("/api/camera/preview")
def camera_preview_route():
    status = camera_status()

    if not status["preview_available"]:
        return jsonify(
            error="USB camera preview is unavailable",
            code="camera_preview_unavailable",
        ), 503

    try:
        stream = preview_frames()
    except (CameraUnavailable, CameraPreviewError) as exc:
        return jsonify(
            error=str(exc),
            code="camera_preview_unavailable",
        ), 503

    return Response(
        stream_with_context(stream),
        content_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@camera_bp.post("/api/camera/preview/stop")
def camera_preview_stop_route():
    was_running = stop_preview()

    return jsonify(
        status="stopped",
        was_running=was_running,
    )


@camera_bp.post("/api/camera/capture")
def camera_capture_route():
    # Always release a preview process before taking the full-resolution still.
    stop_preview()

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
            "INSERT INTO captures (filename, image_url, status) "
            "VALUES (?, ?, 'stored')",
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
