"""Matches the automatic import hook in Ty-Montgomery's app.py."""
from flask import Blueprint, current_app, jsonify, request
import logging
from backend.services.assistant_logs import log_assistant_query
from backend.services.assistant import get_plant_guidance

assistant_bp = Blueprint('assistant', __name__)


@assistant_bp.post('/api/assistant')
def assistant():
    request.max_content_length = 16 * 1024
    if not request.is_json:
        return jsonify(error='Content-Type must be application/json'), 415
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Body must be a JSON object'), 400
    try:
        result = get_plant_guidance(data.get('species'), data.get('message'))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if current_app.config.get('ASSISTANT_LOGGING', False):
        try:
            log_assistant_query(data.get('species'), data['message'], result, result['source'])
        except Exception as exc:
            logging.getLogger(__name__).warning('Assistant logging failed (%s)', type(exc).__name__)
    return jsonify(result)
