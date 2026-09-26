"""Pytest suite for analysis/classifier.py.

Uses the real sample photo from data/samples/ (not an in-memory synthetic
image) so these tests exercise the same file format/size path a real
capture would take. No network call and no GEMINI_API_KEY needed -- Gemini
itself is replaced with a fake client, per the pattern already used in
tests/test_gemini.py.

Some overlap with tests/test_gemini.py is intentional: that file covers the
full request/response shape and route-level integration (owned by the AI
teammate); this file is classifier.py's dedicated, CI-facing unit coverage.
Consolidate later if the team wants a single file -- not done here to avoid
editing a file another teammate owns.
"""
from pathlib import Path

import pytest

from analysis.classifier import (
    AnalysisError,
    ConfigurationError,
    classify_leaf,
)

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "sample_leaf.jpg"


def _sample_bytes():
    assert SAMPLE_PATH.is_file(), f"Missing sample image at {SAMPLE_PATH}"
    return SAMPLE_PATH.read_bytes()


class _FakeModels:
    """Stands in for client.models -- records what it was called with."""

    def __init__(self, response_text='{"health_rating":"attention","plant_name":"Pothos"}'):
        self.response_text = response_text
        self.last_call = None

    def generate_content(self, **kwargs):
        self.last_call = kwargs
        return type("Response", (), {"text": self.response_text})()


def _fake_client(response_text=None):
    models = _FakeModels() if response_text is None else _FakeModels(response_text)
    return type("Client", (), {"models": models})()


def test_classify_leaf_returns_parsed_json_from_sample_photo():
    client = _fake_client()
    result = classify_leaf(_sample_bytes(), client=client)
    assert result["health_rating"] == "attention"
    assert result["plant_name"] == "Pothos"


def test_classify_leaf_sends_prepared_jpeg_not_raw_bytes():
    # The sample fixture is already a JPEG, but classify_leaf must still run
    # it through prepare_image (resize/normalize) before sending -- this
    # guards against someone bypassing preprocessing by accident.
    client = _fake_client()
    classify_leaf(_sample_bytes(), client=client)
    sent_parts = client.models.last_call["contents"]
    assert len(sent_parts) == 2  # [PROMPT, image part]
    image_part = sent_parts[1]
    assert image_part.inline_data.mime_type == "image/jpeg"
    # Prepared bytes are re-encoded JPEG, so they won't equal the raw file bytes.
    assert image_part.inline_data.data != _sample_bytes()


def test_classify_leaf_request_uses_json_response_mode():
    client = _fake_client()
    classify_leaf(_sample_bytes(), client=client)
    assert client.models.last_call["config"]["response_mime_type"] == "application/json"


def test_classify_leaf_raises_on_malformed_gemini_json():
    client = _fake_client(response_text="not valid json")
    with pytest.raises(AnalysisError):
        classify_leaf(_sample_bytes(), client=client)


def test_classify_leaf_raises_on_empty_gemini_response():
    client = _fake_client(response_text="")
    with pytest.raises(AnalysisError):
        classify_leaf(_sample_bytes(), client=client)


def test_classify_leaf_rejects_bad_photo_before_calling_gemini():
    client = _fake_client()
    with pytest.raises(AnalysisError):
        classify_leaf(b"not a photo", client=client)
    # Gemini should never be called for an unreadable file.
    assert client.models.last_call is None


def test_classify_leaf_raises_configuration_error_without_key_or_client(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        classify_leaf(_sample_bytes())
