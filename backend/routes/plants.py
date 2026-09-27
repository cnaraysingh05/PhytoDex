"""
GET /api/plants        -- list/search plants -> array of plant summaries
GET /api/plants/<id>   -- plant profile -> species + water/light/care fields

Contract: framework Section 7 & 8. Owner: Person 2 (Backend) -- feature/backend
"""
from flask import Blueprint, jsonify, request

from backend.models.db import get_db

plants_bp = Blueprint("plants", __name__)

# Fields returned in the list/search view. Keep this lean -- frontend cards
# don't need the full profile. Full detail is in get_plant() below.
SUMMARY_FIELDS = "id, common_name, scientific_name, category, difficulty, image_url"


@plants_bp.route("/api/plants", methods=["GET"])
def list_plants():
    """
    Query params (all optional):
      q         -- matched against common_name and scientific_name (LIKE, case-insensitive)
      category  -- exact match on category
    """
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    query = f"SELECT {SUMMARY_FIELDS} FROM plants WHERE 1=1"
    params = []

    if q:
        query += " AND (common_name LIKE ? COLLATE NOCASE OR scientific_name LIKE ? COLLATE NOCASE)"
        like = f"%{q}%"
        params += [like, like]

    if category:
        query += " AND category = ? COLLATE NOCASE"
        params.append(category)

    query += " ORDER BY common_name ASC"

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


@plants_bp.route("/api/plants/<int:plant_id>", methods=["GET"])
def get_plant(plant_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM plants WHERE id = ?", (plant_id,)).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Plant not found"}), 404

    return jsonify(dict(row))
