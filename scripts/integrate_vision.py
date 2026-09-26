"""Opt-in registration for the inspected Flask scaffold; refuses unknown layouts."""
import ast
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'app.py'
if not path.exists():
    raise SystemExit('Team app.py is not present yet. Use run_ai.py for standalone testing.')
original = path.read_text()
if 'register_blueprint(identify_bp)' in original:
    raise SystemExit('Vision is already registered; no changes made.')
marker = '    return app\n'
if original.count(marker) != 1 or 'def create_app():' not in original:
    raise SystemExit('App layout differs from inspected scaffold; ask the backend owner to register identify_bp.')
updated = original.replace(marker,
    '    # Optional PhytoDex photo classification\n'
    '    from backend.routes.identify import identify_bp\n'
    '    app.register_blueprint(identify_bp)\n\n' + marker)
ast.parse(updated)
path.write_text(updated)
print('Registered /api/identify in app.py. Review this change with the backend owner.')
