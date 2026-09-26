"""Independent smoke-test server; the team app stays owned by the backend owner."""
import argparse
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from backend.routes.assistant import assistant_bp


def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
    app.register_blueprint(assistant_bp)
    from backend.routes.identify import identify_bp
    app.register_blueprint(identify_bp)

    @app.get('/api/ai/health')
    def health():
        return jsonify(status='ok', service='phytodex-ai')

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error=exc.description), exc.code

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5001)
    args = parser.parse_args()
    from waitress import serve
    serve(create_app(), host=args.host, port=args.port, threads=4)
