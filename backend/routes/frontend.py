"""Serve the tablet screens for photo scans and My Garden.

Every screen of the app uses the same HTML page (templates/index.html); the
JavaScript in static/js/ then draws the right screen for the address. Listing
each screen's address here is what makes refreshing or bookmarking a page work.
API routes stay under /api/ and are not affected.
"""
import os

from flask import Blueprint, current_app, render_template

frontend_bp = Blueprint("frontend", __name__)

PAGE_ROUTES = (
    "/",
    "/scan",
    "/scan/<int:capture_id>",
    "/garden",
    "/garden/<int:garden_id>",
    "/garden/<int:garden_id>/rescan",
    "/plantdex",
    "/plantdex/<int:plant_id>",
    "/ask",
    "/system",
)


def _asset_version():
    """Change the asset URLs whenever a CSS/JS file changes so the tablet
    doesn't keep showing an old cached copy after an update."""
    static_dir = os.path.join(current_app.root_path, "static")
    newest = 0
    for folder in ("css", "js"):
        path = os.path.join(static_dir, folder)
        if os.path.isdir(path):
            for name in os.listdir(path):
                newest = max(newest, int(os.path.getmtime(os.path.join(path, name))))
    return str(newest)


def app_page(**_route_values):
    return render_template("index.html", asset_version=_asset_version())


for rule in PAGE_ROUTES:
    frontend_bp.add_url_rule(rule, "app_page", app_page)
