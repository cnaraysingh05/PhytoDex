"""No real credentials, user DB writes, or paid HTTP requests in unit tests."""
import pytest


@pytest.fixture(autouse=True)
def isolate_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv('AI_MODE', 'offline')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    monkeypatch.setenv('PHYTODEX_DB_PATH', str(tmp_path / 'isolated.db'))
    monkeypatch.setenv('PHYTODEX_CAPTURE_DIR', str(tmp_path / 'captures'))
    def no_network(*args, **kwargs):
        raise AssertionError('Tests must fake the provider; real HTTP calls are disabled')
    import httpx
    import requests
    monkeypatch.setattr(httpx.Client, 'send', no_network)
    monkeypatch.setattr(requests.Session, 'request', no_network)
