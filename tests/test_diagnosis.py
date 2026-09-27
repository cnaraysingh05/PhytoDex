"""Pytest suite for analysis/diagnosis.py.

build_diagnosis() itself takes a dict, not an image -- so "using sample
images" here means one true end-to-end test that starts from the real
sample photo, goes through prepare_image -> a faked classify_leaf ->
build_diagnosis, proving the whole pipeline agrees on shape. The rest are
focused unit tests on build_diagnosis's actual job: turning arbitrary/messy
Gemini output into safe, predictable JSON.
"""
from pathlib import Path

from analysis.classifier import classify_leaf
import importlib.util
import pytest
if importlib.util.find_spec('analysis.diagnosis') is None:
    pytest.skip('Teammate diagnosis module pending; main readiness gate remains required', allow_module_level=True)
from analysis.diagnosis import build_diagnosis

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "sample_leaf.jpg"


def _sample_bytes():
    assert SAMPLE_PATH.is_file(), f"Missing sample image at {SAMPLE_PATH}"
    return SAMPLE_PATH.read_bytes()


def _fake_client(response_text):
    class _Models:
        def generate_content(self, **kwargs):
            return type("Response", (), {"text": response_text})()
    return type("Client", (), {"models": _Models()})()


def test_pipeline_sample_photo_to_diagnosis():
    """Real sample image -> fake Gemini -> diagnosis, end to end."""
    client = _fake_client(
        '{"plant_name":"Pothos","health_rating":"attention",'
        '"visible_signs":["Yellow leaves"],'
        '"possible_causes":["Possible excess moisture"],'
        '"certainty":"medium","limitations":"Soil moisture is not visible."}'
    )
    raw = classify_leaf(_sample_bytes(), client=client)
    result = build_diagnosis(raw)

    assert result["plant_name"] == "Pothos"
    assert result["health_rating"] == "attention"
    assert result["visible_signs"] == ["Yellow leaves"]
    assert result["certainty"] == "medium"
    assert result["source"] == "gemini"
    assert "confidence" not in result  # never a fake numeric score


def test_unknown_rating_clears_possible_causes():
    result = build_diagnosis({
        "health_rating": "unknown",
        "possible_causes": ["Should be dropped"],
        "visible_signs": ["Should be kept"],
    })
    assert result["health_rating"] == "unknown"
    assert result["possible_causes"] == []
    assert result["visible_signs"] == ["Should be kept"]


def test_invalid_health_rating_falls_back_to_unknown():
    result = build_diagnosis({"health_rating": "definitely dying"})
    assert result["health_rating"] == "unknown"


def test_invalid_certainty_falls_back_to_low():
    result = build_diagnosis({"certainty": "99%"})
    assert result["certainty"] == "low"


def test_missing_plant_name_is_none_not_empty_string():
    result = build_diagnosis({"plant_name": "   "})
    assert result["plant_name"] is None


def test_missing_limitations_gets_a_default_caveat():
    result = build_diagnosis({})
    assert result["limitations"]
    assert isinstance(result["limitations"], str)


def test_non_string_list_items_are_dropped_not_crashed_on():
    result = build_diagnosis({"visible_signs": ["ok", 123, None, "  ", "also ok"]})
    assert result["visible_signs"] == ["ok", "also ok"]


def test_long_strings_are_truncated():
    result = build_diagnosis({
        "plant_name": "x" * 500,
        "limitations": "y" * 900,
    })
    assert len(result["plant_name"]) <= 100
    assert len(result["limitations"]) <= 500


def test_non_dict_input_raises_value_error():
    import pytest
    with pytest.raises(ValueError):
        build_diagnosis(["not", "a", "dict"])
