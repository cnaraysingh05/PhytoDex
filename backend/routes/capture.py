"""
POST /api/capture -- accepts an uploaded plant photo and stores it.

*** NOT in the original framework contract (Section 7/8). ***
This is a stretch addition (framework Section 13: USB camera / vision ID).
Scope, by explicit decision: this endpoint does ONLY capture + storage.
It does NOT run identification -- that is Person 4's (AI/Integration)
job, consuming the image_url/capture_id this returns.

Before merging to main:
  - Tell Person 3 (frontend) the request/response shape below so they can
    build the upload UI.
  - Tell Person 4 (AI) that images arrive as stored files with a
    capture_id + image_url, not as inline base64 in the assistant request.
    If they'd rather receive base64 directly in POST /api/assistant, that's
    a contract change -- agree on it before either side builds against it.

Request:  multipart/form-data, field name "image" (jpg/jpeg/png)
Response: 201 {"capture_id": int, "image_url": str, "status": "stored"}
"""
import os
import uuid

from flask import Blueprint, current_app, jsonify, request

from backend.models.db import get_db

capture_bp = Blueprint("capture", __name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
UPLOAD_SUBDIR = os.path.join("static", "uploads", "captures")


@capture_bp.route("/api/capture", methods=["POST"])
def capture_image():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided (expected form field 'image')"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"}), 400

    upload_dir = os.path.join(current_app.root_path, UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    file.save(os.path.join(upload_dir, filename))
    image_url = f"/static/uploads/captures/{filename}"

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO captures (filename, image_url, status) VALUES (?, ?, 'stored')",
        (filename, image_url),
    )
    conn.commit()
    capture_id = cur.lastrowid
    conn.close()

    return (
        jsonify({"capture_id": capture_id, "image_url": image_url, "status": "stored"}),
        201,
    )
