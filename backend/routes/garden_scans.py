"""My Garden scan history routes. Garden create/list/delete stay in garden.py.

GET  /api/garden/scan-summaries  {"<garden_id>": {scan_count, latest_scan}} for
                                 plants with scans; combined with GET /api/garden
                                 by the frontend so garden.py stays unchanged
GET  /api/garden/<id>          one garden plant with its dated scan history
POST /api/garden/<id>/scans    {"capture_id": int} -- add that photo's scan to
                               THIS plant (the user chose the plant; no photo
                               matching). Reuses a stored assessment if the
                               photo was already analyzed, otherwise runs the
                               same pipeline as POST /api/analysis.

Saving a first scan as a new plant = POST /api/garden {plant_id, nickname}
(plant_id is a confirmed species or null for unidentified plants), then POST /api/garden/<id>/scans.
"""
from flask import Blueprint, jsonify, request

from backend.models.db import get_db
from backend.routes.analysis import assess_photo
from backend.routes.photo_bridge import read_photo
from backend.services.scan_history import (attach_scan, get_garden_plant, load_assessment,
                                           save_assessment, scan_summaries)

garden_scans_bp = Blueprint('garden_scans', __name__)


@garden_scans_bp.get('/api/garden/scan-summaries')
def list_scan_summaries():
    conn = get_db()
    try:
        summaries = scan_summaries(conn)
    finally:
        conn.close()
    return jsonify({str(garden_id): value for garden_id, value in summaries.items()})


@garden_scans_bp.get('/api/garden/<int:garden_id>')
def open_garden_plant(garden_id):
    conn = get_db()
    try:
        plant = get_garden_plant(conn, garden_id)
    finally:
        conn.close()
    if plant is None:
        return jsonify(error='Garden entry not found'), 404
    return jsonify(plant)


def _plant_and_scan(conn, garden_id, capture_id):
    plant = get_garden_plant(conn, garden_id)
    scan = next(s for s in plant['scans'] if s['capture_id'] == capture_id)
    return {'plant': plant, 'scan': scan}


@garden_scans_bp.post('/api/garden/<int:garden_id>/scans')
def add_scan(garden_id):
    data = request.get_json(silent=True) if request.is_json else None
    capture_id = data.get('capture_id') if isinstance(data, dict) else None
    if type(capture_id) is not int or capture_id < 1:
        return jsonify(error='Provide a positive integer capture_id'), 400

    conn = get_db()
    try:
        if conn.execute('SELECT 1 FROM garden WHERE id = ?', (garden_id,)).fetchone() is None:
            return jsonify(error='Garden entry not found'), 404
        saved = load_assessment(conn, capture_id)
        if saved and saved['garden_id'] == garden_id:
            return jsonify(_plant_and_scan(conn, garden_id, capture_id)), 200  # repeated request
        if saved and saved['garden_id'] is not None:
            return jsonify(error='This photo is already saved to a different plant',
                           garden_id=saved['garden_id']), 409
    finally:
        conn.close()

    if saved is None:
        # Not analyzed yet: same validation, errors and Gemini call as /api/analysis.
        image_bytes, error = read_photo()
        if error:
            return error
        result, error = assess_photo(image_bytes)
        if error:
            return error  # nothing is attached, so the same photo can be retried

    conn = get_db()
    try:
        if saved is None:
            save_assessment(conn, capture_id, result)
        if not attach_scan(conn, capture_id, garden_id):
            return jsonify(error='This photo is already saved to a plant'), 409
        return jsonify(_plant_and_scan(conn, garden_id, capture_id)), 201
    finally:
        conn.close()
