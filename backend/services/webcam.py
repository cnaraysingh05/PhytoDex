"""USB webcam capture for the Raspberry Pi.

Uses fswebcam through subprocess with an argument list (never shell=True).
PHYTODEX_CAMERA_DEVICE can pin a stable /dev/v4l/by-id/... device.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_SKIP_FRAMES = 10


class CameraUnavailable(RuntimeError):
    """The configured camera or capture program is unavailable."""


class CameraCaptureError(RuntimeError):
    """The camera exists, but taking a still image failed."""


def _positive_int(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default

    if value < 1 or value > maximum:
        return default

    return value


def camera_device() -> Path:
    configured = os.getenv("PHYTODEX_CAMERA_DEVICE", "").strip()
    if configured:
        return Path(configured)

    by_id = Path("/dev/v4l/by-id")
    if by_id.is_dir():
        devices = sorted(by_id.glob("*-video-index0"))
        if devices:
            return devices[0]

    return Path("/dev/video0")


def camera_status() -> dict:
    device = camera_device()
    program = shutil.which("fswebcam")

    return {
        "available": bool(program and device.exists()),
        "device": str(device),
        "fswebcam_available": bool(program),
        "device_available": device.exists(),
        "resolution": {
            "width": _positive_int("PHYTODEX_CAMERA_WIDTH", DEFAULT_WIDTH, 4096),
            "height": _positive_int("PHYTODEX_CAMERA_HEIGHT", DEFAULT_HEIGHT, 4096),
        },
    }


def capture_photo(output_path: Path) -> dict:
    program = shutil.which("fswebcam")
    if not program:
        raise CameraUnavailable("fswebcam is not installed on this deck")

    device = camera_device()
    if not device.exists():
        raise CameraUnavailable("The configured USB camera is not connected")

    width = _positive_int("PHYTODEX_CAMERA_WIDTH", DEFAULT_WIDTH, 4096)
    height = _positive_int("PHYTODEX_CAMERA_HEIGHT", DEFAULT_HEIGHT, 4096)
    skip = _positive_int("PHYTODEX_CAMERA_SKIP_FRAMES", DEFAULT_SKIP_FRAMES, 60)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        program,
        "-d", str(device),
        "-r", f"{width}x{height}",
        "--skip", str(skip),
        "--no-banner",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output_path.unlink(missing_ok=True)
        raise CameraCaptureError("USB camera capture timed out") from exc
    except OSError as exc:
        output_path.unlink(missing_ok=True)
        raise CameraCaptureError("USB camera capture could not start") from exc

    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise CameraCaptureError("USB camera did not return a usable photo")

    if not output_path.is_file() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise CameraCaptureError("USB camera did not create a photo")

    return {
        "device": str(device),
        "width": width,
        "height": height,
    }
