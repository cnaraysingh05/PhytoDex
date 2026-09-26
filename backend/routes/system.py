from flask import Blueprint, jsonify
from backend.services.system_status import system_status
system_bp = Blueprint('system', __name__)


@system_bp.get('/api/system')
def system():
    return jsonify(system_status())
