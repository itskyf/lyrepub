"""Shared local audio-tool operations for publication scripts."""

import subprocess
from decimal import Decimal
from functools import cache
from pathlib import Path
from shutil import which


@cache
def media_tool(name: str) -> str:
    """Resolve an external media tool from PATH once per process."""
    tool = which(name)
    if tool is None:
        message = f"{name} is required for audio packaging"
        raise FileNotFoundError(message)
    return tool


def ogg_duration(path: Path) -> Decimal:
    """Return the measured duration rounded to publication millisecond precision."""
    result = subprocess.run(
        [
            media_tool("ffprobe"),
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
    subprocess.run(
        [
            media_tool("ffmpeg"),
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
