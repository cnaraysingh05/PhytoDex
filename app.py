"""
PhytoDex Flask entrypoint.

Owner: Person 2 (Backend / Database / API) -- feature/backend

This file only wires up blueprints -- route logic lives in backend/routes/.
Person 1 (system telemetry) and Person 4 (AI assistant) each own their own
route module and register their own blueprint. app.py loads those
defensively (try/except ImportError) so merging main never breaks just
because one branch hasn't landed yet, and so nobody has to edit this file
but the backend owner.
"""
import os

from dotenv import load_dotenv
from flask import Flask

from backend.routes.health import health_bp
from backend.routes.plants import plants_bp
from backend.routes.garden import garden_bp
from backend.routes.capture import capture_bp

load_dotenv()


def create_app():
    app = Flask(__name__)

    app.register_blueprint(health_bp)
    app.register_blueprint(plants_bp)
    app.register_blueprint(garden_bp)
    app.register_blueprint(capture_bp)

    # --- Teammate-owned blueprints -------------------------------------
    # Person 1 (Pi/Hardware) -- GET /api/system
    try:
        from backend.routes.system import system_bp
        app.register_blueprint(system_bp)
    except ImportError:
        pass

    # Person 4 (AI/Integration) -- POST /api/assistant
    try:
        from backend.routes.assistant import assistant_bp
        app.register_blueprint(assistant_bp)
    except ImportError:
        pass

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
