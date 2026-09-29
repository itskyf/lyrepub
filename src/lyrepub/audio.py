"""Shared local audio-tool operations for publication scripts."""

import os
import tempfile
from decimal import Decimal
from pathlib import Path


def run_tool(command: list[str]) -> tuple[str, str]:
    """Run a local tool and report its captured error output on failure."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        actions = [
            (os.POSIX_SPAWN_DUP2, stdout.fileno(), 1),
            (os.POSIX_SPAWN_DUP2, stderr.fileno(), 2),
        ]
        pid = os.posix_spawnp(command[0], command, os.environ, file_actions=actions)
        _, status = os.waitpid(pid, 0)
        stdout.seek(0)
        stderr.seek(0)
        out, err = stdout.read().decode(), stderr.read().decode()
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
        message = f"{command[0]} failed: {err[-1000:]}"
        raise RuntimeError(message)
    return out, err


def ogg_duration(path: Path) -> Decimal:
    """Return the measured duration rounded to publication millisecond precision."""
    stdout, _ = run_tool(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    duration = Decimal(stdout.strip()).quantize(Decimal("0.001"))
    if duration <= 0:
        message = f"invalid packaged audio duration: {path}"
        raise ValueError(message)
    return duration


def encode_opus(source: Path, output: Path) -> Decimal:
    """Encode audio as Opus and return its measured duration."""
    run_tool(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-c:a",
            "libopus",
            "-b:a",
            "96k",
            str(output),
        ]
    )
    return ogg_duration(output)
