"""Shared API app. Frontend screens remain with the frontend teammate."""
import os
import importlib
import importlib.util
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from backend.settings import ROOT


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=10 * 1024 * 1024,
                      CAPTURE_DIR=os.getenv('PHYTODEX_CAPTURE_DIR', str(ROOT / 'static/uploads/captures')),
                      ASSISTANT_LOGGING=True)
    if test_config:
        app.config.update(test_config)
    from backend.routes.health import health_bp
    from backend.routes.plants import plants_bp
    from backend.routes.garden import garden_bp
    from backend.routes.capture import capture_bp
    from backend.routes.assistant import assistant_bp
    for bp in [health_bp, plants_bp, garden_bp, capture_bp, assistant_bp]:
        app.register_blueprint(bp)
    # Each stage can be installed separately. An existing module with an import
    # bug is never silently swallowed; only an absent optional module is skipped.
    photo_module = 'backend.routes.analysis'
    if app.config.get('USE_PHOTO_BRIDGE') or importlib.util.find_spec(photo_module) is None:
        photo_module = 'backend.routes.photo_bridge'
    for module_name, bp_name in [('backend.routes.system', 'system_bp'),
                                 (photo_module, 'analysis_bp'),
                                 ('backend.routes.garden_scans', 'garden_scans_bp'),
                                 ('backend.routes.frontend', 'frontend_bp')]:
        if importlib.util.find_spec(module_name) is not None:
            app.register_blueprint(getattr(importlib.import_module(module_name), bp_name))

    @app.get('/api/ai/health')
    def ai_health():
        return jsonify(status='ok', service='phytodex-api')

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error=exc.description), exc.code

    return app


app = create_app()

if __name__ == '__main__':
    from waitress import serve
    serve(app, host=os.getenv('HOST', '127.0.0.1'), port=int(os.getenv('PORT', '5001')))
