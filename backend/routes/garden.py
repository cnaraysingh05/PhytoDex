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
        JOIN plants ON garden.plant_id = plants.id
        ORDER BY garden.created_at DESC
        """
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@garden_bp.route("/api/garden", methods=["POST"])
def add_to_garden():
    data = request.get_json(silent=True) or {}
    plant_id = data.get("plant_id")

    if not plant_id:
        return jsonify({"error": "plant_id is required"}), 400

    conn = get_db()
    plant = conn.execute("SELECT id FROM plants WHERE id = ?", (plant_id,)).fetchone()
    if plant is None:
        conn.close()
        return jsonify({"error": f"No plant with id {plant_id}"}), 404

    cur = conn.execute(
        """
        INSERT INTO garden (plant_id, nickname, notes, last_watered)
        VALUES (?, ?, ?, ?)
        """,
        (plant_id, data.get("nickname"), data.get("notes"), data.get("last_watered")),
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
