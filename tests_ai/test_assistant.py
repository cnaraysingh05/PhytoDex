import os
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from backend.services.assistant import Guidance, get_plant_guidance, offline_guidance
from run_ai import create_app


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'AI_MODE': 'offline'}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = create_app({'ASSISTANT_LOGGING': False, 'USE_PHOTO_BRIDGE': True}).test_client()

    def test_offline_is_explicit_and_does_not_invent_a_diagnosis(self):
        response = self.client.post('/api/assistant', json={'species': 'Pothos', 'message': 'soil is not wet'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['source'], 'fallback')
        self.assertIn('not a tailored diagnosis', data['uncertainty_note'])

    def test_invalid_requests(self):
        for body in [None, [], {}, {'message': 3}, {'message': ' '}, {'message': 'x' * 3001},
                     {'message': 'help', 'species': []}]:
            with self.subTest(body=str(body)[:60]):
                response = self.client.post('/api/assistant', json=body, content_type='application/json')
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post('/api/assistant', data='help').status_code, 415)

    def test_large_request(self):
        response = self.client.post('/api/assistant', json={'message': 'x' * 20000})
        self.assertEqual(response.status_code, 413)

    def test_live_contract(self):
        os.environ.update(AI_MODE='gemini', GEMINI_API_KEY='fake', GEMINI_MODEL='test-model')
        fields = {k: v for k, v in offline_guidance().items() if k in Guidance.model_fields}
        with patch('backend.services.assistant._generate', return_value=Guidance(**fields)) as call:
            result = get_plant_guidance('Pothos', 'Help')
            self.assertEqual(result['source'], 'gemini')
            call.assert_called_once_with('Pothos', 'Help', 'test-model', 'fake')

    def test_provider_error_does_not_leak_secret(self):
        os.environ.update(AI_MODE='gemini', GEMINI_API_KEY='fake-secret', GEMINI_MODEL='test-model')
        with patch('backend.services.assistant._generate', side_effect=RuntimeError('fake-secret')):
            result = get_plant_guidance(None, 'Help')
            self.assertEqual(result['fallback_reason'], 'provider_unavailable')
            self.assertNotIn('fake-secret', str(result))

    def test_wrong_types_and_extra_keys_rejected(self):
        fields = {k: v for k, v in offline_guidance().items() if k in Guidance.model_fields}
        for key, value in [('urgency', 'urgent'), ('likely_causes', 'root rot'),
                           ('what_to_check', ['']), ('extra', 'oops')]:
            with self.subTest(key=key), self.assertRaises(ValidationError):
                Guidance(**dict(fields, **{key: value}))

    def test_photo_is_unavailable_without_diagnosis_module(self):
        from io import BytesIO
        with patch('backend.routes.photo_bridge.diagnosis_builder', return_value=None):
            response = self.client.post('/api/identify', data={'image': (BytesIO(b'x'), 'x.jpg')})
        self.assertEqual(response.status_code, 503)

    def test_invalid_capture_id(self):
        for value in [True, '../secret', -1]:
            self.assertEqual(self.client.post('/api/identify', json={'capture_id': value}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
