"""Tests for analysis/preprocess.py using a real file on disk from
data/samples/, per the framework spec. No network or API key needed --
these only exercise image transforms.
"""
from pathlib import Path
import io

from PIL import Image
import pytest

from analysis.preprocess import (
    AnalysisError,
    center_crop_square,
    load_image,
    prepare_image,
)

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "sample_leaf.jpg"


def _sample_bytes():
    assert SAMPLE_PATH.is_file(), (
        f"Missing sample image at {SAMPLE_PATH}. "
        "Add a JPEG/PNG leaf photo there (real or placeholder) before running this test."
    )
    return SAMPLE_PATH.read_bytes()


def test_prepare_image_resizes_and_normalizes_sample():
    jpeg_bytes, mime = prepare_image(_sample_bytes())
    assert mime == "image/jpeg"
    with Image.open(io.BytesIO(jpeg_bytes)) as prepared:
        assert prepared.format == "JPEG"
        assert prepared.mode == "RGB"
        assert max(prepared.size) <= 1600


def test_prepare_image_default_does_not_crop():
    # Default behavior must match the original inline classifier.py logic:
    # resize only, keep native aspect ratio. This guards against a future
    # edit accidentally turning cropping on by default.
    with Image.open(io.BytesIO(_sample_bytes())) as original:
        original_ratio = original.size[0] / original.size[1]

    jpeg_bytes, _ = prepare_image(_sample_bytes())
    with Image.open(io.BytesIO(jpeg_bytes)) as prepared:
        prepared_ratio = prepared.size[0] / prepared.size[1]

    assert prepared_ratio == pytest.approx(original_ratio, rel=0.01)


def test_prepare_image_crop_to_square_opt_in():
    jpeg_bytes, _ = prepare_image(_sample_bytes(), crop_to_square=True)
    with Image.open(io.BytesIO(jpeg_bytes)) as prepared:
        width, height = prepared.size
        assert width == height


def test_center_crop_square_uses_shorter_side():
    image = load_image(_sample_bytes())
    cropped = center_crop_square(image)
    width, height = cropped.size
    assert width == height == min(image.size)


def test_prepare_image_rejects_unreadable_bytes():
    with pytest.raises(AnalysisError):
        prepare_image(b"this is not an image")


def test_prepare_image_rejects_oversized_input():
    with pytest.raises(AnalysisError):
        prepare_image(b"x" * (10 * 1024 * 1024 + 1))
