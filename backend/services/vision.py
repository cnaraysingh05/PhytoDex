"""Small local image classifier, loaded only when identification is requested."""
import hashlib
import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_instances = {}
_load_lock = threading.Lock()


class VisionModel:
    def __init__(self, directory):
        import numpy as np
        try:
            from ai_edge_litert.interpreter import Interpreter
        except ImportError:
            try:
                from tflite_runtime.interpreter import Interpreter
            except ImportError:
                import tensorflow as tf
                Interpreter = tf.lite.Interpreter
        self.np = np
        directory = Path(directory)
        self.meta = json.loads((directory / 'metadata.json').read_text())
        blob = (directory / 'model.tflite').read_bytes()
        if hashlib.sha256(blob).hexdigest() != self.meta['model_sha256']:
            raise ValueError('Model hash mismatch; copy model and metadata from the same run')
        if self.meta.get('smoke_only'):
            raise ValueError('Smoke-test weights cannot be used for identification')
        if self.meta.get('input_range') != [0, 255] or self.meta.get('normalization') != 'inside_model':
            raise ValueError('Unsupported preprocessing contract')
        self.runtime = Interpreter(model_content=blob, num_threads=2)
        self.runtime.allocate_tensors()
        self.input = self.runtime.get_input_details()[0]
        self.output = self.runtime.get_output_details()[0]
        size = self.meta['image_size']
        if list(self.input['shape']) != [1, size, size, 3] or self.input['dtype'] != np.float32:
            raise ValueError('Expected a float32 NHWC RGB model')
        if self.output['shape'][-1] != len(self.meta['labels']):
            raise ValueError('Output class count does not match labels')
        self.lock = threading.Lock()

    def identify(self, source):
        from PIL import Image, ImageOps, UnidentifiedImageError
        import warnings
        import time
        started = time.perf_counter()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(source) as image:
                    if image.format not in {'JPEG', 'PNG'} or image.width * image.height > 20_000_000:
                        raise ValueError('Use a JPEG/PNG with at most 20 million pixels')
                    size = self.meta['image_size']
                    image = ImageOps.exif_transpose(image).convert('RGB').resize(
                        (size, size), Image.Resampling.BILINEAR)
                    tensor = self.np.asarray(image, dtype=self.np.float32)[None]
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError('Invalid or oversized image') from exc
        with self.lock:
            self.runtime.set_tensor(self.input['index'], tensor)
            self.runtime.invoke()
            probabilities = self.runtime.get_tensor(self.output['index'])[0].copy()
        if not self.np.isfinite(probabilities).all():
            raise RuntimeError('Nonfinite model output')
        indices = probabilities.argsort()[::-1][:3]
        top = [{'label': self.meta['labels'][int(i)], 'score': float(probabilities[i])} for i in indices]
        accepted = top[0]['score'] >= self.meta['threshold']
        return {'status': 'candidate' if accepted else 'uncertain',
                'label': top[0]['label'] if accepted else None, 'candidates': top,
                'threshold': self.meta['threshold'], 'source': 'local_mobilenetv2',
                'latency_ms': round((time.perf_counter() - started) * 1000, 2),
                'uncertainty_note': 'Only trained categories are compared. Even a high score can be wrong '
                'for another plant or a non-plant image. Confirm the category manually.'}


def get_model():
    directory = Path(os.getenv('VISION_MODEL_DIR', 'models/flowers'))
    if not directory.is_absolute():
        directory = ROOT / directory
    with _load_lock:
        if str(directory) not in _instances:
            _instances[str(directory)] = VisionModel(directory)
        return _instances[str(directory)]
