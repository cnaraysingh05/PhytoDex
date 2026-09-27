"""Photo analysis route and My Garden scan history, with a fake Gemini.

conftest.py already gives every test a temporary database and capture folder,
offline AI mode, and blocked network access.
Run from the repo root:  python -m pytest tests/test_my_garden.py -v
"""
import io
import sqlite3
from unittest.mock import patch

import pytest
from PIL import Image

import backend.models.db as db_module
from analysis.classifier import AnalysisError, ConfigurationError
from analysis.diagnosis import build_diagnosis
from app import create_app
from backend.models.db import get_db, init_db


def gemini(name, rating, signs, certainty="medium"):
    """A fake raw Gemini answer in the shape classify_leaf returns."""
    return {"plant_name": name, "health_rating": rating, "visible_signs": signs,
            "possible_causes": ["Possible watering issue"], "certainty": certainty,
            "limitations": "Soil is not visible."}


class FakeGemini:
    def __init__(self):
        self.answers, self.calls = [], 0

    def __call__(self, image_bytes):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture()
def fake_gemini():
    fake = FakeGemini()
    with patch("backend.routes.analysis.classify_leaf", fake):
        yield fake


@pytest.fixture()
def client(tmp_path):
    app = create_app({"TESTING": True, "CAPTURE_DIR": str(tmp_path / "captures")})
    init_db()
    conn = get_db()
    conn.executemany("INSERT INTO plants (common_name, scientific_name) VALUES (?, ?)",
                     [("Pothos", "Epipremnum aureum"), ("Monstera", "Monstera deliciosa")])
    conn.commit()
    conn.close()
    return app.test_client()


def photo_file(fmt="JPEG"):
    data = io.BytesIO()
    Image.new("RGB", (64, 64), "green").save(data, fmt)
    data.seek(0)
    return data


def upload(client):
    resp = client.post("/api/capture", data={"image": (photo_file(), "leaf.jpg")})
    assert resp.status_code == 201
    return resp.json["capture_id"]


def scan_and_save(client, fake, answer, nickname, plant_id=1):
    """First scan -> user confirms species -> team POST /api/garden -> attach scan."""
    fake.answers.append(answer)
    capture_id = upload(client)
    assert client.post("/api/analysis", json={"capture_id": capture_id}).status_code == 200
    created = client.post("/api/garden", json={"plant_id": plant_id, "nickname": nickname})
    assert created.status_code == 201
    attached = client.post(f"/api/garden/{created.json['id']}/scans", json={"capture_id": capture_id})
    assert attached.status_code == 201, attached.json
    return attached.json["plant"]


def rescan(client, fake, garden_id, answer):
    fake.answers.append(answer)
    return client.post(f"/api/garden/{garden_id}/scans", json={"capture_id": upload(client)})


def count(table):
    conn = get_db()
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def test_analysis_accepts_upload_or_capture_id_and_alias(client, fake_gemini):
    fake_gemini.answers += [gemini("Pothos", "healthy", []), gemini("Pothos", "attention", ["Yellow leaf"])]
    direct = client.post("/api/analysis", data={"image": (photo_file("PNG"), "leaf.png")})
    assert direct.status_code == 200 and direct.json["source"] == "gemini"
    assert count("photo_assessments") == 0  # a direct upload has nothing to attach to
    capture_id = upload(client)
    saved = client.post("/api/identify", json={"capture_id": capture_id})
    assert saved.status_code == 200 and saved.json["capture_id"] == capture_id
    assert count("photo_assessments") == 1


def test_analysis_never_maps_plant_name_to_a_plant_id(client, fake_gemini):
    fake_gemini.answers.append(gemini("Pothos", "healthy", []))
    body = client.post("/api/analysis", json={"capture_id": upload(client)}).json
    assert body["plant_name"] == "Pothos"
    assert "plant_id" not in body and "library_match" not in body
    assert count("garden") == 0


def test_analysis_error_codes_follow_the_contract(client, fake_gemini):
    bad = client.post("/api/analysis", data={"image": (io.BytesIO(b"not a photo"), "leaf.jpg")})
    assert bad.status_code == 400
    assert client.post("/api/analysis", json={"capture_id": 999}).status_code == 404
    assert client.post("/api/analysis", json={"capture_id": "1"}).status_code == 400
    fake_gemini.answers += [ConfigurationError("no key"), AnalysisError("secret detail")]
    assert client.post("/api/analysis", data={"image": (photo_file(), "a.jpg")}).status_code == 503
    failed = client.post("/api/analysis", data={"image": (photo_file(), "a.jpg")})
    assert failed.status_code == 502 and "secret detail" not in failed.text
    fake_gemini.answers.append(RuntimeError("unexpected provider bug"))
    crashed = client.post("/api/analysis", data={"image": (photo_file(), "a.jpg")})
    assert crashed.status_code == 502 and "unexpected provider bug" not in crashed.text
    assert fake_gemini.calls == 3  # the bad photo never reached Gemini


def test_garden_list_is_unchanged_and_summaries_come_from_this_feature(client, fake_gemini):
    assert client.get("/api/garden").json == []
    assert client.get("/api/garden/scan-summaries").json == {}
    desk = scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Desk Pothos")
    entry = client.get("/api/garden").json[0]
    assert set(entry) == {"id", "plant_id", "nickname", "date_added", "notes", "last_watered",
                          "created_at", "common_name", "scientific_name", "image_url"}
    summary = client.get("/api/garden/scan-summaries").json[str(desk["id"])]
    assert summary["scan_count"] == 1 and summary["latest_scan"]["health_rating"] == "healthy"


def test_first_save_reuses_the_stored_assessment(client, fake_gemini):
    scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Desk Pothos")
    assert fake_gemini.calls == 1


def test_two_plants_of_same_species_are_saved_separately(client, fake_gemini):
    desk = scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Desk Pothos")
    shelf = scan_and_save(client, fake_gemini, gemini("Pothos", "attention", ["Yellow leaf"]), "Shelf Pothos")
    assert desk["id"] != shelf["id"] and desk["plant_id"] == shelf["plant_id"] == 1
    assert {p["nickname"] for p in client.get("/api/garden").json} == {"Desk Pothos", "Shelf Pothos"}


def test_rescans_attach_to_selected_plant_and_keep_old_scans(client, fake_gemini):
    desk = scan_and_save(client, fake_gemini, gemini("Pothos", "concerning", ["Brown tips"]), "Desk Pothos")
    shelf = scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Shelf Pothos")
    assert rescan(client, fake_gemini, desk["id"], gemini("Pothos", "attention", ["Yellow leaf"])).status_code == 201
    latest = rescan(client, fake_gemini, desk["id"], gemini("Pothos", "healthy", []))
    assert latest.status_code == 201 and latest.json["scan"]["health_rating"] == "healthy"

    detail = client.get(f"/api/garden/{desk['id']}").json
    assert [s["health_rating"] for s in detail["scans"]] == ["healthy", "attention", "concerning"]
    assert detail["scans"][-1]["capture_id"] == desk["scans"][0]["capture_id"]
    assert detail["scans"][-1]["visible_signs"] == ["Brown tips"]  # first scan untouched
    assert detail["comparison"]["previous"]["health_rating"] == "attention"
    assert detail["comparison"]["current"]["health_rating"] == "healthy"
    assert "%" not in str(detail["comparison"])
    assert client.get(f"/api/garden/{shelf['id']}").json["scan_count"] == 1
    assert count("garden") == 2  # rescans never create plants


def test_repeated_rescan_request_does_not_duplicate(client, fake_gemini):
    desk = scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Desk Pothos")
    fake_gemini.answers.append(gemini("Pothos", "attention", []))
    capture_id = upload(client)
    url = f"/api/garden/{desk['id']}/scans"
    assert client.post(url, json={"capture_id": capture_id}).status_code == 201
    assert client.post(url, json={"capture_id": capture_id}).status_code == 200
    assert fake_gemini.calls == 2
    assert client.get(f"/api/garden/{desk['id']}").json["scan_count"] == 2


def test_a_photo_cannot_belong_to_two_plants(client, fake_gemini):
    desk = scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Desk Pothos")
    shelf = scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Shelf Pothos")
    desk_capture = desk["scans"][0]["capture_id"]
    resp = client.post(f"/api/garden/{shelf['id']}/scans", json={"capture_id": desk_capture})
    assert resp.status_code == 409 and resp.json["garden_id"] == desk["id"]


def test_analysis_never_overwrites_a_saved_scan(client, fake_gemini):
    desk = scan_and_save(client, fake_gemini, gemini("Pothos", "concerning", ["Brown tips"]), "Desk Pothos")
    fake_gemini.answers.append(gemini("Pothos", "healthy", []))
    body = client.post("/api/analysis", json={"capture_id": desk["scans"][0]["capture_id"]}).json
    assert body["health_rating"] == "concerning" and fake_gemini.calls == 1


def test_failed_rescan_attaches_nothing_and_can_retry(client, fake_gemini):
    desk = scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Desk Pothos")
    capture_id = upload(client)
    url = f"/api/garden/{desk['id']}/scans"
    fake_gemini.answers += [ConfigurationError("no key"), AnalysisError("down"), gemini("Pothos", "attention", [])]
    assert client.post(url, json={"capture_id": capture_id}).status_code == 503
    assert client.post(url, json={"capture_id": capture_id}).status_code == 502
    assert client.get(f"/api/garden/{desk['id']}").json["scan_count"] == 1
    assert client.post(url, json={"capture_id": capture_id}).status_code == 201
    assert client.get(f"/api/garden/{desk['id']}").json["scan_count"] == 2


def test_scan_route_validation(client, fake_gemini):
    desk = scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Desk Pothos")
    assert client.post(f"/api/garden/{desk['id']}/scans", json={"capture_id": True}).status_code == 400
    assert client.post(f"/api/garden/{desk['id']}/scans", data={"image": (photo_file(), "a.jpg")}).status_code == 400
    assert client.post(f"/api/garden/{desk['id']}/scans", json={"capture_id": 999}).status_code == 404
    assert client.post("/api/garden/999/scans", json={"capture_id": 1}).status_code == 404
    assert client.get("/api/garden/999").status_code == 404


def test_team_delete_still_works_and_keeps_photos(client, fake_gemini):
    desk = scan_and_save(client, fake_gemini, gemini("Pothos", "healthy", []), "Desk Pothos")
    assert client.delete(f"/api/garden/{desk['id']}").status_code == 200
    assert client.get("/api/garden").json == []
    assert count("captures") == 1 and count("photo_assessments") == 1  # unlinked, not lost


def test_init_db_adds_history_table_to_an_existing_team_database(tmp_path, monkeypatch):
    path = tmp_path / "existing.db"
    team_schema = db_module.SCHEMA_PATH.read_text().split("-- My Garden scan history")[0]
    conn = sqlite3.connect(path)
    conn.executescript(team_schema)
    conn.execute("INSERT INTO plants (common_name) VALUES ('Pothos')")
    conn.execute("INSERT INTO garden (plant_id, nickname) VALUES (1, 'Old friend')")
    conn.commit()
    conn.close()
    monkeypatch.setenv("PHYTODEX_DB_PATH", str(path))
    init_db()
    init_db()
    conn = get_db()
    try:
        assert conn.execute("SELECT nickname FROM garden").fetchone()[0] == "Old friend"
        assert conn.execute("SELECT COUNT(*) FROM photo_assessments").fetchone()[0] == 0
    finally:
        conn.close()


def test_diagnosis_normalizes_without_inventing_results():
    result = build_diagnosis({"health_rating": " Attention ", "certainty": "HIGH",
                              "visible_signs": ["Yellow leaf", 5, ""]})
    assert result["health_rating"] == "attention" and result["certainty"] == "high"
    assert result["visible_signs"] == ["Yellow leaf"]
    assert result["next_steps"][0].startswith("General check:")  # labeled as generic
    assert not any(isinstance(value, float) for value in result.values())
