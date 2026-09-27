"""Checks that Flask serves the tablet interface correctly. No Gemini key needed.

Run from the repo root:  python -m pytest tests/test_frontend.py -v
"""
import re
from pathlib import Path

import pytest
from werkzeug.exceptions import MethodNotAllowed, NotFound

from app import create_app
from backend.models.db import init_db

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_FILES = [ROOT / "templates" / "index.html", *sorted((ROOT / "static" / "js").glob("*.js")),
                  *sorted((ROOT / "static" / "css").glob("*.css"))]


@pytest.fixture()
def client():
    # conftest.py points the database and captures at temporary locations.
    app = create_app({"TESTING": True})
    init_db()
    with app.test_client() as test_client:
        yield test_client


@pytest.mark.parametrize("path", [
    "/",
    "/scan",
    "/scan/12",
    "/garden",
    "/garden/3",
    "/garden/3/rescan",
    "/plantdex",
    "/plantdex/1",
    "/ask",
    "/system",
])
def test_every_screen_address_serves_the_app(client, path):
    # Refreshing any screen asks Flask for that address directly.
    response = client.get(path)
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    page = response.get_data(as_text=True)
    assert "/static/js/app.js" in page and "/static/css/phytodex.css" in page


def test_unknown_addresses_are_still_404(client):
    assert client.get("/not-a-page").status_code == 404
    assert client.get("/garden/abc").status_code == 404
    response = client.get("/api/not-a-route")
    assert response.status_code == 404


def test_api_routes_still_return_json(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}
    assert client.get("/api/garden").get_json() == []
    assert client.get("/api/garden/1").status_code == 404
    assert client.get("/api/garden/1").is_json


@pytest.mark.parametrize("asset", ["js/app.js", "js/api.js", "js/photo.js", "js/ui.js",
                                   "css/phytodex.css", "manifest.webmanifest", "img/phytodex-icon.svg"])
def test_static_assets_are_served(client, asset):
    response = client.get(f"/static/{asset}")
    assert response.status_code == 200
    if asset.endswith(".js"):
        assert "javascript" in response.mimetype  # required for <script type="module">
    response.close()


def test_frontend_only_calls_routes_that_exist(client):
    source = (ROOT / "static" / "js" / "api.js").read_text()
    paths = set(re.findall(r"(/api(?:/(?:\$\{\w+\}|[a-z-]+))+)", source))
    assert {"/api/analysis", "/api/garden/${gardenId}/scans", "/api/garden/scan-summaries"} <= paths
    assert "/api/analyze" not in paths  # the old route no longer exists
    adapter = client.application.url_map.bind("localhost")
    for path in paths:
        concrete = re.sub(r"\$\{\w+\}", "1", path)
        try:
            adapter.match(concrete)
        except MethodNotAllowed:
            pass  # route exists; it just isn't a GET route
        except NotFound:
            pytest.fail(f"frontend calls {path}, which the backend doesn't define")


def test_no_api_key_or_direct_gemini_calls_in_frontend_files():
    for path in FRONTEND_FILES:
        text = path.read_text()
        assert "GEMINI_API_KEY" not in text, path
        assert "generativelanguage.googleapis.com" not in text, path
        assert not re.search(r"AIza[0-9A-Za-z_\-]{20,}", text), path  # Google API key pattern


def test_frontend_never_builds_html_from_server_text():
    # Gemini's words are shown with textContent. innerHTML is only used for
    # the fixed icon drawings written inside ui.js.
    for path in (ROOT / "static" / "js").glob("*.js"):
        uses = re.findall(r"\.innerHTML\s*=\s*([^;\n]+)", path.read_text())
        for use in uses:
            assert path.name == "ui.js" and use.strip() == 'ICONS[name] || ""', (path, use)


def test_frontend_does_not_invent_numeric_confidence():
    for path in (ROOT / "static" / "js").glob("*.js"):
        text = path.read_text()
        assert "confidence" not in text.lower(), path
        assert not re.search(r"\d+\s*%", text), path


def test_frontend_sends_only_a_user_chosen_plant_id():
    # Garden entries are created with the species the user picked from the list;
    # there is no automatic plant_name -> plant_id step in the browser code.
    app_js = (ROOT / "static" / "js" / "app.js").read_text()
    assert "createGardenPlant(species.value ? Number(species.value) : null, name)" in app_js
    assert "library_match" not in app_js


def test_plantdex_frontend_is_wired(client):
    page = client.get("/plantdex").get_data(as_text=True)
    assert 'href="/plantdex"' in page
    assert 'data-nav="plantdex"' in page

    app_js = (ROOT / "static" / "js" / "app.js").read_text()
    api_js = (ROOT / "static" / "js" / "api.js").read_text()

    assert "plantDexView" in app_js
    assert "plantDexPlantView" in app_js
    assert "/plantdex/${plant.id}" in app_js

    assert 'params.set("q", query.trim())' in api_js
    assert "request(`/api/plants/${plantId}`)" in api_js


def test_ask_phyto_frontend_is_wired(client):
    page = client.get("/ask").get_data(as_text=True)
    assert 'href="/ask"' in page
    assert 'data-nav="ask"' in page

    app_js = (ROOT / "static" / "js" / "app.js").read_text()
    api_js = (ROOT / "static" / "js" / "api.js").read_text()

    assert "askPhytoView" in app_js
    assert 'result.source === "gemini"' in app_js
    assert "Live Gemini guidance" in app_js
    assert "Offline fallback guidance" in app_js

    assert 'request("/api/assistant"' in api_js
    assert "species: species || null" in api_js


def test_ask_phyto_does_not_label_fallback_as_live_gemini():
    app_js = (ROOT / "static" / "js" / "app.js").read_text()

    assert 'const isLive = result.source === "gemini"' in app_js
    assert "Gemini did not provide this answer" in app_js


def test_system_frontend_is_wired(client):
    page = client.get("/system").get_data(as_text=True)
    assert 'href="/system"' in page
    assert 'data-nav="system"' in page

    app_js = (ROOT / "static" / "js" / "app.js").read_text()
    api_js = (ROOT / "static" / "js" / "api.js").read_text()

    assert "systemView" in app_js
    assert "formatUptime" in app_js
    assert 'request("/api/system"' in api_js

    assert "CPU temperature" in app_js
    assert "Hardware model" in app_js
    assert "Gemini configuration" in app_js


def test_system_frontend_does_not_fake_missing_metrics():
    app_js = (ROOT / "static" / "js" / "app.js").read_text()

    assert '"Unavailable"' in app_js
    assert 'status.cpu_temperature_c.toFixed(1)' in app_js
    assert 'status.hardware_model || "Unavailable"' in app_js


def test_deck_camera_frontend_is_wired():
    app_js = (ROOT / "static" / "js" / "app.js").read_text()
    api_js = (ROOT / "static" / "js" / "api.js").read_text()

    assert "deckCameraPanel" in app_js
    assert "Capture & analyze with deck camera" in app_js
    assert "api.cameraStatus()" in app_js
    assert "api.cameraCapture()" in app_js

    assert 'request("/api/camera/status"' in api_js
    assert 'request("/api/camera/capture"' in api_js
