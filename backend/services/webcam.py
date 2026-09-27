"""USB webcam capture and live preview for the Raspberry Pi.

Still photos use fswebcam.
Live preview uses FFmpeg reading MJPEG from the V4L2 camera.

Only one preview process owns the camera at a time. Before a full-resolution
still capture, the preview process is explicitly stopped so fswebcam can take
exclusive control of the device.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path


DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_SKIP_FRAMES = 10

DEFAULT_PREVIEW_WIDTH = 640
DEFAULT_PREVIEW_HEIGHT = 360
DEFAULT_PREVIEW_FPS = 10

_PREVIEW_BOUNDARY = b"frame"
_preview_lock = threading.Lock()
_preview_process: subprocess.Popen | None = None


class CameraUnavailable(RuntimeError):
    """The configured camera or required capture program is unavailable."""


class CameraCaptureError(RuntimeError):
    """The camera exists, but taking a still image failed."""


class CameraPreviewError(RuntimeError):
    """The camera exists, but live preview could not be started."""


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
    fswebcam = shutil.which("fswebcam")
    ffmpeg = shutil.which("ffmpeg")

    return {
        "available": bool(fswebcam and device.exists()),
        "preview_available": bool(ffmpeg and device.exists()),
        "device": str(device),
        "fswebcam_available": bool(fswebcam),
        "ffmpeg_available": bool(ffmpeg),
        "device_available": device.exists(),
        "resolution": {
            "width": _positive_int(
                "PHYTODEX_CAMERA_WIDTH",
                DEFAULT_WIDTH,
                4096,
            ),
            "height": _positive_int(
                "PHYTODEX_CAMERA_HEIGHT",
                DEFAULT_HEIGHT,
                4096,
            ),
        },
        "preview_resolution": {
            "width": _positive_int(
                "PHYTODEX_CAMERA_PREVIEW_WIDTH",
                DEFAULT_PREVIEW_WIDTH,
                1920,
            ),
            "height": _positive_int(
                "PHYTODEX_CAMERA_PREVIEW_HEIGHT",
                DEFAULT_PREVIEW_HEIGHT,
                1080,
            ),
            "fps": _positive_int(
                "PHYTODEX_CAMERA_PREVIEW_FPS",
                DEFAULT_PREVIEW_FPS,
                30,
            ),
        },
    }


def _terminate_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def stop_preview() -> bool:
    """Stop the active preview and release the V4L2 camera device."""
    global _preview_process

    with _preview_lock:
        process = _preview_process
        _preview_process = None

    if process is None:
        return False

    _terminate_process(process)
    return True


def preview_frames():
    """Yield an HTTP multipart MJPEG stream from the USB camera."""
    global _preview_process

    program = shutil.which("ffmpeg")
    if not program:
        raise CameraUnavailable("ffmpeg is not installed on this deck")

    device = camera_device()
    if not device.exists():
        raise CameraUnavailable("The configured USB camera is not connected")

    width = _positive_int(
        "PHYTODEX_CAMERA_PREVIEW_WIDTH",
        DEFAULT_PREVIEW_WIDTH,
        1920,
    )
    height = _positive_int(
        "PHYTODEX_CAMERA_PREVIEW_HEIGHT",
        DEFAULT_PREVIEW_HEIGHT,
        1080,
    )
    fps = _positive_int(
        "PHYTODEX_CAMERA_PREVIEW_FPS",
        DEFAULT_PREVIEW_FPS,
        30,
    )

    # A second preview request replaces the previous preview cleanly.
    stop_preview()

    command = [
        program,
        "-hide_banner",
        "-loglevel", "error",
        "-f", "v4l2",
        "-input_format", "mjpeg",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-i", str(device),
        "-an",
        "-c:v", "copy",
        "-f", "mjpeg",
        "-flush_packets", "1",
        "pipe:1",
    ]

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
    except OSError as exc:
        raise CameraPreviewError(
            "USB camera preview could not start"
        ) from exc

    with _preview_lock:
        _preview_process = process

    buffer = b""

    try:
        if process.stdout is None:
            raise CameraPreviewError("USB camera preview produced no output")

        while True:
            chunk = process.stdout.read(16384)

            if not chunk:
                break

            buffer += chunk

            while True:
                start = buffer.find(b"\xff\xd8")
                if start < 0:
                    buffer = buffer[-1:]
                    break

                end = buffer.find(b"\xff\xd9", start + 2)
                if end < 0:
                    if start:
                        buffer = buffer[start:]
                    break

                frame = buffer[start:end + 2]
                buffer = buffer[end + 2:]

                yield (
                    b"--" + _PREVIEW_BOUNDARY + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n"
                    b"\r\n"
                    + frame
                    + b"\r\n"
                )
    finally:
        with _preview_lock:
            if _preview_process is process:
                _preview_process = None

        _terminate_process(process)

        if process.stdout is not None:
            process.stdout.close()


def capture_photo(output_path: Path) -> dict:
    # The still camera must own the device exclusively.
    stop_preview()

    program = shutil.which("fswebcam")
    if not program:
        raise CameraUnavailable("fswebcam is not installed on this deck")

    device = camera_device()
    if not device.exists():
        raise CameraUnavailable("The configured USB camera is not connected")

    width = _positive_int(
        "PHYTODEX_CAMERA_WIDTH",
        DEFAULT_WIDTH,
        4096,
    )
    height = _positive_int(
        "PHYTODEX_CAMERA_HEIGHT",
        DEFAULT_HEIGHT,
        4096,
    )
    skip = _positive_int(
        "PHYTODEX_CAMERA_SKIP_FRAMES",
        DEFAULT_SKIP_FRAMES,
        60,
    )

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
        raise CameraCaptureError(
            "USB camera did not return a usable photo"
        )

    if not output_path.is_file() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise CameraCaptureError(
            "USB camera did not create a photo"
        )

    return {
        "device": str(device),
        "width": width,
        "height": height,
    }
