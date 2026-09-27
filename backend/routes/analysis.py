"""Final photo analysis route (docs/CONTRACT.md, "Photo requests").

POST /api/analysis   (alias: POST /api/identify)
  multipart/form-data field "image"   -> assess that photo; nothing is stored
  JSON {"capture_id": int}             -> assess a photo saved by /api/capture;
                                          the assessment is kept for My Garden

Errors: 400 bad input or unreadable photo, 404 missing capture, 503 Gemini not
configured, 502 Gemini/output failure. There is no offline or made-up answer.
The response never maps plant_name to a PlantDex plant ID.
"""
import logging

from flask import Blueprint, jsonify, request

from analysis.classifier import AnalysisError, ConfigurationError, classify_leaf
from analysis.diagnosis import build_diagnosis
from analysis.preprocess import prepare_image
from backend.models.db import get_db
from backend.routes.photo_bridge import read_photo
from backend.services.scan_history import load_assessment, save_assessment

analysis_bp = Blueprint('analysis', __name__)
logger = logging.getLogger(__name__)
MAX_PHOTO_BYTES = 10 * 1024 * 1024


def assess_photo(image_bytes):
    """Run the photo pipeline. Returns (assessment, None) or (None, error response)."""
    # Bad photos are 400 even when the cloud provider is unavailable.
    try:
        prepare_image(image_bytes)
    except AnalysisError as exc:
        return None, (jsonify(error=str(exc)), 400)
    try:
        result = build_diagnosis(classify_leaf(image_bytes))
    except ConfigurationError as exc:
        return None, (jsonify(error=str(exc), source='unavailable'), 503)
    except Exception as exc:
        # Provider and output failures (the classifier wraps most as AnalysisError).
        # The message is generic so no provider detail or key can leak.
        logger.warning('Photo analysis failed (%s)', type(exc).__name__)
        return None, (jsonify(error='Photo analysis unavailable; try again later',
                              source='unavailable'), 502)
    result['source'] = 'gemini'
    return result, None


@analysis_bp.post('/api/analysis')
@analysis_bp.post('/api/identify')
def analyze_photo():
    request.max_content_length = MAX_PHOTO_BYTES
    image_bytes, error = read_photo()
    if error:
        return error
    capture_id = request.get_json(silent=True)['capture_id'] if request.is_json else None

    if capture_id is not None:
        conn = get_db()
        try:
            saved = load_assessment(conn, capture_id)
        finally:
            conn.close()
        if saved and saved['garden_id'] is not None:
            # Already part of a garden plant's history: return it, never replace it.
            return jsonify(dict(saved['assessment'], capture_id=capture_id))

    result, error = assess_photo(image_bytes)
    if error:
        return error
    if capture_id is None:
        return jsonify(result)

    conn = get_db()
    try:
        save_assessment(conn, capture_id, result)
    finally:
        conn.close()
    return jsonify(dict(result, capture_id=capture_id))
