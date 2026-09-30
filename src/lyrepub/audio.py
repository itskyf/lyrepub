"""Shared local audio-tool operations for publication scripts."""

import subprocess
from decimal import Decimal
from pathlib import Path
from shutil import which


def ogg_duration(path: Path) -> Decimal:
    """Return the measured duration rounded to publication millisecond precision."""
    ffprobe = which("ffprobe")
    if ffprobe is None:
        message = "ffprobe is required for audio duration validation"
        raise FileNotFoundError(message)
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    duration = Decimal(result.stdout.strip()).quantize(Decimal("0.001"))
    if duration <= 0:
        message = f"invalid packaged audio duration: {path}"
        raise ValueError(message)
    return duration


def encode_opus(source: Path, output: Path) -> Decimal:
    """Encode audio as Opus and return its measured duration."""
    ffmpeg = which("ffmpeg")
    if ffmpeg is None:
        message = "ffmpeg is required for Opus packaging"
        raise FileNotFoundError(message)
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-c:a",
            "libopus",
            str(output),
        ],
        check=True,
    )
    return ogg_duration(output)
