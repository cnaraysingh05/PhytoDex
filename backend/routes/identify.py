"""Compatibility import: /api/identify is now an alias of Gemini /api/analysis.
Register analysis_bp once; do not register both names in the same app.
"""
from backend.routes.photo_bridge import analysis_bp as identify_bp
