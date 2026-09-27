"""Photo API wiring only. analysis/diagnosis.py remains teammate-owned."""
import importlib
import logging
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request
from analysis.classifier import AnalysisError, ConfigurationError, classify_leaf
from backend.models.db import get_db

analysis_bp = Blueprint('analysis', __name__)
logger = logging.getLogger(__name__)


def diagnosis_builder():
    try:
        return importlib.import_module('analysis.diagnosis').build_diagnosis
    except ModuleNotFoundError as exc:
        if exc.name == 'analysis.diagnosis':
            return None
        raise


def read_photo():
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get('capture_id')) is not int or data['capture_id'] < 1:
            return None, (jsonify(error='Provide a positive integer capture_id'), 400)
        conn = get_db()
        try:
            row = conn.execute('SELECT filename FROM captures WHERE id=?', (data['capture_id'],)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None, (jsonify(error='Capture not found'), 404)
        folder = Path(current_app.config['CAPTURE_DIR']).resolve()
        path = (folder / row['filename']).resolve()
        if not path.is_relative_to(folder) or not path.is_file():
            return None, (jsonify(error='Capture file unavailable'), 404)
        with path.open('rb') as f:
            return f.read(10 * 1024 * 1024 + 1), None
    upload = request.files.get('image')
    if upload is None or not upload.filename:
        return None, (jsonify(error='Provide multipart image or JSON capture_id'), 400)
    return upload.stream.read(10 * 1024 * 1024 + 1), None


@analysis_bp.post('/api/analysis')
@analysis_bp.post('/api/identify')
def analyze_photo():
    request.max_content_length = 10 * 1024 * 1024
    image_bytes, error = read_photo()
    if error:
        return error
    build = diagnosis_builder()
    if build is None:
        return jsonify(error='Photo diagnosis module is not integrated yet',
                       code='diagnosis_not_ready', source='unavailable'), 503
    # Bad photos should be 400 even when the cloud provider is unavailable.
    from analysis.preprocess import prepare_image
    try:
        prepare_image(image_bytes)
    except AnalysisError as exc:
        return jsonify(error=str(exc)), 400
    try:
        raw = classify_leaf(image_bytes)
        result = build(raw)
        if not isinstance(result, dict):
            raise ValueError('Diagnosis must return a JSON object')
        result['source'] = 'gemini'
        return jsonify(result)
    except ConfigurationError as exc:
        return jsonify(error=str(exc), source='unavailable'), 503
    except (AnalysisError, ValueError, TypeError) as exc:
        logger.warning('Photo analysis failed (%s)', type(exc).__name__)
        return jsonify(error='Photo analysis unavailable; try again later', source='unavailable'), 502
