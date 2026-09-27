"""Resize, crop, and normalize a captured leaf photo before it goes to the
classifier (Gemini). Pure image transforms live here -- no network calls,
no API keys -- so this module can be tested with a plain file on disk and
no internet connection.

This was pulled out of analysis/classifier.py, where prepare_image()
originally lived inline. The default behavior of prepare_image() is
unchanged (same signature, same output for the same input) so this is a
pure refactor: analysis/classifier.py, backend/routes/analysis.py, and the
existing tests in tests/test_gemini.py all keep working without edits.
"""
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
import warnings

MAX_BYTES = 10 * 1024 * 1024
MAX_DIMENSION = 1600
JPEG_QUALITY = 85
SUPPORTED_FORMATS = {"JPEG", "PNG"}


class AnalysisError(Exception):
    """A photo could not be read or prepared for analysis."""


def load_image(image_bytes):
    """Validate size/format and return an opened, loaded Pillow Image.

    Raises AnalysisError for anything not a readable JPEG/PNG within the
    size limit -- callers don't need to know about Pillow's own exceptions.
    """
    if not image_bytes or len(image_bytes) > MAX_BYTES:
        raise AnalysisError("Image must be nonempty and at most 10 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(BytesIO(image_bytes))
        if image.width * image.height > 20_000_000:
            raise AnalysisError('Photo must be at most 20 million pixels')
        if image.format not in SUPPORTED_FORMATS:
            raise AnalysisError("Only JPEG and PNG photos are supported")
        image.load()
        return ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise AnalysisError("File is not a readable JPEG or PNG photo") from exc


def resize_image(image, max_dimension=MAX_DIMENSION):
    """Shrink in place to fit within max_dimension x max_dimension,
    preserving aspect ratio. Returns a new Image; does not mutate input.
    """
    resized = image.copy()
    resized.thumbnail((max_dimension, max_dimension))
    return resized


def center_crop_square(image):
    """Crop to a centered square using the shorter side.

    Opt-in -- not used by prepare_image() unless crop_to_square=True.
    Existing behavior (resize only, no crop) needed to stay unchanged for
    the current Gemini prompt, which reasons about the whole leaf/plant;
    cropping to square is here for a future classifier that expects
    square input, without changing today's default output.
    """
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def normalize_mode(image):
    """Convert to RGB (e.g. drop alpha/palette) so JPEG encoding never fails."""
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def encode_jpeg(image, quality=JPEG_QUALITY):
    """Encode a Pillow Image as JPEG bytes."""
    output = BytesIO()
    image.save(output, format="JPEG", quality=quality)
    return output.getvalue()


def prepare_image(image_bytes, crop_to_square=False):
    """Validate, optionally crop, resize, and normalize an image for the
    classifier. Returns (jpeg_bytes, mime_type).

    crop_to_square=False (default) matches the original inline behavior in
    classifier.py: resize only, keep the photo's native aspect ratio.
    """
    try:
        image = load_image(image_bytes)
        if crop_to_square:
            image = center_crop_square(image)
        image = resize_image(image)
        image = normalize_mode(image)
        return encode_jpeg(image), "image/jpeg"
    except AnalysisError:
        raise
    except (OSError, ValueError) as exc:
        raise AnalysisError("File is not a readable JPEG or PNG photo") from exc
