"""
Smoke tests for the routes Person 2 (Backend) owns.
Run from repo root with the venv active:  pytest tests/test_backend.py -v
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import backend.models.db as db_module
from app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the app at a throwaway DB so tests never touch phytodex.db
    test_db = tmp_path / "test_phytodex.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(test_db))

    db_module.init_db()
    conn = db_module.get_db()
    conn.execute(
        """INSERT INTO plants
           (common_name, scientific_name, category, water, light, soil,
            temperature, difficulty, summary, image_url)
           VALUES ('Pothos', 'Epipremnum aureum', 'Vine', 'Medium', 'Bright indirect',
                   'Potting mix', '65-85F', 'Easy', 'Easy trailing vine', '')"""
    )
    conn.commit()
    conn.close()

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_list_plants(client):
    resp = client.get("/api/plants")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["common_name"] == "Pothos"


def test_search_plants(client):
    resp = client.get("/api/plants?q=poth")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1

    resp = client.get("/api/plants?q=zzz-no-match")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_plant_detail_and_404(client):
    resp = client.get("/api/plants/1")
    assert resp.status_code == 200
    assert resp.get_json()["scientific_name"] == "Epipremnum aureum"

    resp = client.get("/api/plants/999")
    assert resp.status_code == 404


def test_garden_crud_flow(client):
    resp = client.post("/api/garden", json={"plant_id": 1, "nickname": "Sunny"})
    assert resp.status_code == 201
    entry_id = resp.get_json()["id"]

    resp = client.get("/api/garden")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1

    resp = client.delete(f"/api/garden/{entry_id}")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "deleted"

    resp = client.get("/api/garden")
    assert resp.get_json() == []


def test_garden_missing_plant_id(client):
    resp = client.post("/api/garden", json={})
    assert resp.status_code == 400


def test_capture_upload(client):
    fake_image = (io.BytesIO(b"fake image bytes"), "leaf.jpg")
    resp = client.post(
        "/api/capture",
        data={"image": fake_image},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "stored"
    assert body["image_url"].startswith("/static/uploads/captures/")


def test_capture_rejects_bad_extension(client):
    fake_file = (io.BytesIO(b"not an image"), "notes.txt")
    resp = client.post(
        "/api/capture",
        data={"image": fake_file},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
