"""Starts running automatically when both teammate-owned modules arrive."""
import importlib.util
import io
from unittest.mock import patch
import pytest
from PIL import Image

if any(importlib.util.find_spec(name) is None for name in ['analysis.diagnosis', 'backend.routes.analysis']):
    pytest.skip('Final teammate photo pipeline is pending; readiness gate protects main', allow_module_level=True)


def test_real_teammate_route_with_fake_provider():
    from app import create_app
    from backend.models.db import init_db
    init_db()
    image = io.BytesIO()
    Image.new('RGB', (40, 40), 'green').save(image, 'PNG')
    image.seek(0)
    raw = {'plant_name': None, 'visible_signs': [], 'possible_causes': [],
           'health_rating': 'unknown', 'certainty': 'low', 'limitations': 'Test fixture'}
    # Only the provider is faked: the final route and diagnosis builder are real.
    with patch('analysis.classifier._generate', return_value=raw):
        response = create_app({'TESTING': True}).test_client().post(
            '/api/analysis', data={'image': (image, 'leaf.png')})
    assert response.status_code == 200
    assert response.json['health_rating'] == 'unknown'
    assert response.json['source'] == 'gemini'
