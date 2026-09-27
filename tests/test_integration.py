import io
import json
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from PIL import Image
from app import create_app
from backend.models.db import get_db, init_db
from database.seed import seed


@pytest.fixture
def client(tmp_path):
    app = create_app({'TESTING': True, 'USE_PHOTO_BRIDGE': True, 'CAPTURE_DIR': str(tmp_path / 'photos')})
    init_db()
    return app.test_client()


def photo():
    data = io.BytesIO()
    Image.new('RGB', (40, 20), 'green').save(data, 'PNG')
    data.seek(0)
    return data


def test_seed_preserves_saved_garden_and_ids(client):
    seed()
    conn = get_db()
    before = [tuple(r) for r in conn.execute('SELECT id, scientific_name FROM plants ORDER BY id')]
    plant_id = before[0][0]
    conn.execute('INSERT INTO garden(plant_id,nickname) VALUES(?,?)', (plant_id, 'Keep me'))
    conn.commit()
    conn.close()
    seed()
    init_db()
    conn = get_db()
    try:
        assert before == [tuple(r) for r in conn.execute('SELECT id, scientific_name FROM plants ORDER BY id')]
        assert conn.execute('SELECT nickname FROM garden').fetchone()[0] == 'Keep me'
    finally:
        conn.close()


def test_assistant_logged_in_same_database(client):
    response = client.post('/api/assistant', json={'species': 'Pothos', 'message': 'Yellow leaves'})
    assert response.status_code == 200
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM assistant_logs').fetchone()
        assert row['species'] == 'Pothos'
        assert row['source'] == 'fallback'
        assert json.loads(row['response_json']) == response.json
    finally:
        conn.close()


def test_logging_failure_does_not_break_assistant(client):
    with patch('backend.routes.assistant.log_assistant_query', side_effect=RuntimeError('fake secret')):
        response = client.post('/api/assistant', json={'message': 'Help'})
    assert response.status_code == 200
    assert 'fake secret' not in response.text


def test_system_reports_host_and_database_without_cloud_call(client, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'DO_NOT_LEAK_THIS')
    monkeypatch.setenv('GEMINI_MODEL', 'test-model')
    monkeypatch.setenv('AI_MODE', 'gemini')
    with patch('backend.services.system_status.cpu_temperature', return_value=None), \
         patch('backend.services.system_status.uptime_seconds', return_value=300):
        response = client.get('/api/system')
    assert response.status_code == 200
    assert response.json['hostname'] == socket.gethostname()
    assert response.json['uptime_seconds'] == 300
    assert response.json['cpu_temperature_c'] is None
    assert response.json['database']['status'] == 'ok'
    assert response.json['gemini']['status'] == 'configured_not_checked'
    assert response.json['network']['internet_status'] == 'not_checked'
    assert 'DO_NOT_LEAK_THIS' not in response.text


def test_system_missing_database_does_not_create_one(tmp_path, monkeypatch):
    path = tmp_path / 'absent.db'
    monkeypatch.setenv('PHYTODEX_DB_PATH', str(path))
    response = create_app().test_client().get('/api/system')
    assert response.json['database']['status'] == 'not_initialized'
    assert not path.exists()


def test_missing_diagnosis_is_explicit_and_does_not_call_gemini(client):
    with patch('backend.routes.photo_bridge.diagnosis_builder', return_value=None), \
         patch('backend.routes.photo_bridge.classify_leaf') as classify:
        response = client.post('/api/analysis', data={'image': (photo(), 'leaf.png')})
    assert response.status_code == 503
    assert response.json['code'] == 'diagnosis_not_ready'
    classify.assert_not_called()


def test_photo_route_passes_observations_to_teammate_builder(client):
    raw = {'plant_name': 'tentative plant', 'health_rating': 'unknown'}
    def build(value):
        assert value == raw
        return dict(value, limitations='mocked contract test')
    with patch('backend.routes.photo_bridge.diagnosis_builder', return_value=build), \
         patch('backend.routes.photo_bridge.classify_leaf', return_value=raw):
        response = client.post('/api/analysis', data={'image': (photo(), 'leaf.png')})
    assert response.status_code == 200
    assert response.json['source'] == 'gemini'
    assert response.json['limitations'] == 'mocked contract test'


def test_capture_to_analysis_flow_and_alias(client):
    capture = client.post('/api/capture', data={'image': (photo(), 'leaf.png')})
    assert capture.status_code == 201
    with patch('backend.routes.photo_bridge.diagnosis_builder', return_value=lambda raw: raw), \
         patch('backend.routes.photo_bridge.classify_leaf', return_value={'plant_name': None}):
        response = client.post('/api/identify', json={'capture_id': capture.json['capture_id']})
    assert response.status_code == 200
    assert response.json['source'] == 'gemini'
    assert client.post('/api/analysis', json={'capture_id': 99999}).status_code == 404


def test_capture_path_cannot_escape_storage(client):
    conn = get_db()
    conn.execute("INSERT INTO captures(filename,image_url) VALUES('../../private.txt','/bad')")
    conn.commit()
    conn.close()
    assert client.post('/api/analysis', json={'capture_id': 1}).status_code == 404


def test_bad_photo_and_request_limits(client):
    with patch('backend.routes.photo_bridge.diagnosis_builder', return_value=lambda raw: raw):
        response = client.post('/api/analysis', data={'image': (io.BytesIO(b'bad'), 'leaf.jpg')})
    assert response.status_code == 400
    assert client.post('/api/assistant', json={'message': 'a' * 20000}).status_code == 413


def test_cloud_failure_is_sanitized(client):
    from analysis.classifier import AnalysisError
    with patch('backend.routes.photo_bridge.diagnosis_builder', return_value=lambda raw: raw), \
         patch('backend.routes.photo_bridge.classify_leaf', side_effect=AnalysisError('secret-key')):
        response = client.post('/api/analysis', data={'image': (photo(), 'leaf.png')})
    assert response.status_code == 502
    assert 'secret-key' not in response.text


def test_exif_orientation_is_applied_before_resize():
    from analysis.preprocess import prepare_image
    stream = io.BytesIO()
    im = Image.new('RGB', (40, 20), 'green')
    exif = Image.Exif()
    exif[274] = 6
    im.save(stream, format='JPEG', exif=exif)
    prepared, _ = prepare_image(stream.getvalue())
    with Image.open(io.BytesIO(prepared)) as result:
        assert result.size == (20, 40)


def test_unavailable_host_metrics_do_not_crash(client):
    from backend.services.system_status import uptime_seconds
    with patch('backend.services.system_status.Path.read_text', side_effect=PermissionError), \
         patch('backend.services.system_status.psutil.boot_time', side_effect=PermissionError):
        assert uptime_seconds() is None
    with patch('backend.services.system_status.network_interfaces', side_effect=PermissionError):
        response = client.get('/api/system')
    assert response.status_code == 200
    assert response.json['network']['status'] == 'unavailable'
