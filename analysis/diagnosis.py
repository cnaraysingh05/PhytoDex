"""Turn Gemini output into predictable, honest JSON for the UI.

Every field always exists with the same type, whatever Gemini sends back, so
the frontend never has to guess. Nothing here invents a numeric confidence.
"""

HEALTH_RATINGS = {"healthy", "attention", "concerning", "unknown"}
CERTAINTY_LEVELS = {"low", "medium", "high"}

DEFAULT_LIMITATIONS = "A photo alone may not reveal the underlying cause."
# Used only when Gemini gives no next steps. Worded as general checks so they
# are never mistaken for advice about this specific photo.
GENERAL_CHECKS = ["General check: look at soil moisture, light exposure, and both sides "
                  "of the leaves; compare changes over several days."]
RETAKE_PHOTO = ["Try another clear photo in good light, including the whole plant "
                "and affected leaves."]


def _strings(value, limit=5):
    if not isinstance(value, list):
        return []
    return [item.strip()[:240] for item in value[:limit]
            if isinstance(item, str) and item.strip()]


def _choice(value, allowed, default):
    if not isinstance(value, str):
        return default
    value = value.strip().lower()  # " Healthy " used to become "unknown"
    return value if value in allowed else default


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def build_diagnosis(raw):
    """Gemini certainty is qualitative, never a percentage or measured confidence."""
    if not isinstance(raw, dict):
        raise ValueError("Expected a Gemini result object")
    rating = _choice(raw.get("health_rating"), HEALTH_RATINGS, "unknown")
    signs = _strings(raw.get("visible_signs"))
    causes = _strings(raw.get("possible_causes"))
    steps = _strings(raw.get("next_steps"))
    if rating == "unknown":
        causes = []
        steps = RETAKE_PHOTO
    elif not steps:
        steps = GENERAL_CHECKS
    return {
        "plant_name": _text(raw.get("plant_name"), 100),
        "scientific_name": _text(raw.get("scientific_name"), 100),
        "health_rating": rating,
        "visible_signs": signs,
        "possible_causes": causes,
        "certainty": _choice(raw.get("certainty"), CERTAINTY_LEVELS, "low"),
        "limitations": _text(raw.get("limitations"), 500) or DEFAULT_LIMITATIONS,
        "next_steps": list(steps),
        "source": "gemini",
    }
