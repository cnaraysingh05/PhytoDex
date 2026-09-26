"""Optional new contract: identify an uploaded image OR a stored capture_id."""
import logging
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request

identify_bp = Blueprint('identify', __name__)
logger = logging.getLogger(__name__)


@identify_bp.post('/api/identify')
def identify():
    request.max_content_length = 8 * 1024 * 1024
    source = None
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get('capture_id')) is not int or data['capture_id'] < 1:
            return jsonify(error='Provide a positive integer capture_id'), 400
        try:
            from backend.models.db import get_db
        except ImportError:
            return jsonify(error='Capture lookup requires the team backend; use a file upload here'), 503
        conn = get_db()
        try:
            row = conn.execute('SELECT filename FROM captures WHERE id = ?', (data['capture_id'],)).fetchone()
        finally:
            conn.close()
        if row is None:
            return jsonify(error='Capture not found'), 404
        folder = (Path(current_app.root_path) / 'static/uploads/captures').resolve()
        source = (folder / row['filename']).resolve()
        if not source.is_relative_to(folder) or not source.is_file():
            return jsonify(error='Capture file unavailable'), 404
    else:
        uploaded = request.files.get('image')
        if uploaded is None or not uploaded.filename:
            return jsonify(error='Provide multipart field image, or JSON capture_id'), 400
        source = uploaded.stream
    try:
        from backend.services.vision import get_model
        model = get_model()
    except (ImportError, OSError, ValueError, KeyError, RuntimeError) as exc:
        logger.warning('Vision unavailable (%s)', type(exc).__name__)
        return jsonify(error='Vision model unavailable. Install runtime and deploy a trained model bundle.'), 503
    try:
        return jsonify(model.identify(source))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except RuntimeError:
        return jsonify(error='Image inference failed'), 503
