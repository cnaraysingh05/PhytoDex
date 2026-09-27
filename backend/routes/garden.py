"""
GET    /api/garden       -- saved plants -> array of saved plant records
POST   /api/garden       -- save a plant -> created garden entry
DELETE /api/garden/<id>  -- remove saved plant -> success response

Contract: framework Section 7 & 8. Owner: Person 2 (Backend) -- feature/backend
"""
from flask import Blueprint, jsonify, request

from backend.models.db import get_db

garden_bp = Blueprint("garden", __name__)


@garden_bp.route("/api/garden", methods=["GET"])
def list_garden():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT
            garden.id, garden.plant_id, garden.nickname, garden.date_added,
            garden.notes, garden.last_watered, garden.created_at,
            plants.common_name, plants.scientific_name, plants.image_url
        FROM garden
        LEFT JOIN plants ON garden.plant_id = plants.id
        ORDER BY garden.created_at DESC
        """
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@garden_bp.route("/api/garden", methods=["POST"])
def add_to_garden():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Provide a JSON object"), 400
    plant_id = data.get("plant_id")
    if plant_id is not None and (type(plant_id) is not int or plant_id < 1):
        return jsonify(error="plant_id must be a positive integer or null"), 400
    nickname = data.get("nickname")
    if nickname is not None and (not isinstance(nickname, str) or len(nickname.strip()) > 60):
        return jsonify(error="Nickname must be text of at most 60 characters"), 400
    nickname = nickname.strip() if isinstance(nickname, str) else None
    if plant_id is None and not nickname:
        return jsonify(error="Give this unidentified plant a nickname"), 400

    conn = get_db()
    if plant_id is not None:
        plant = conn.execute("SELECT id FROM plants WHERE id = ?", (plant_id,)).fetchone()
        if plant is None:
            conn.close()
            return jsonify({"error": f"No plant with id {plant_id}"}), 404

    cur = conn.execute(
        """
        INSERT INTO garden (plant_id, nickname, notes, last_watered)
        VALUES (?, ?, ?, ?)
        """,
        (plant_id, nickname, data.get("notes"), data.get("last_watered")),
    )
    conn.commit()
    new_id = cur.lastrowid

    row = conn.execute("SELECT * FROM garden WHERE id = ?", (new_id,)).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@garden_bp.route("/api/garden/<int:entry_id>", methods=["DELETE"])
def remove_from_garden(entry_id):
    conn = get_db()
    row = conn.execute("SELECT id FROM garden WHERE id = ?", (entry_id,)).fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "Garden entry not found"}), 404

    conn.execute("DELETE FROM garden WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "deleted", "id": entry_id})
