"""Generate Issue #14 TTS listening evidence with sentence synthesis timing.

Source and model locations are runtime inputs. Outputs live in gitignored data/.
"""

import argparse
import hashlib
import importlib
import json
import logging
import os
import re
import tempfile
from decimal import Decimal
from pathlib import Path

ISBN = "9786045633946"
CASES = (
    (10, 42),
    (5, 26),
    (15, 17),
    (12, 68),
    (12, 30),
    (18, 35),
    (2, 70),
    (5, 9),
    (17, 135),
)
PREFIXES = {
    (10, 42): "Quang Khải nắm tay Quốc Tuấn",
    (5, 26): "Chính việc cha dặn bị vỡ lở",
    (15, 17): "Cứ theo như Đỗ Vỹ tâu",
    (12, 68): "Thu thập tin tức xong, Đỗ Vỹ",
    (12, 30): "(Đây ám chỉ Marco Polo",
    (18, 35): "- Muôn tâu thượng hoàng",
    (2, 70): "(Văn Thù: là một trong 8 vị",
    (5, 9): "Phủ Chiêu Quốc không phải là phủ lớn nhất",
    (17, 135): 'Tiếng "Sát Thát!',
}
MANUAL_NORMALIZATIONS = {
    (17, 135): {"source_span": "S…át Th.. át!", "tts_text": "Sát Thát!"},
}
LOGGER = logging.getLogger(__name__)


def normalize_slash_enumeration(text: str) -> str:
    """Separate ordered slash-list markers; leave ambiguous slashes unchanged."""
    markers = list(
        re.finditer(r"(?:^|(?<=[(:;.\n]))[ \t]*(\d+)/[ \t]+(?=[^\W\d_])", text)
    )
    replacements = []
    run = []
    minimum_markers = 2
    for marker in markers:
        number = int(marker.group(1))
        if run and number != int(run[-1].group(1)) + 1:
            if len(run) >= minimum_markers:
                replacements.extend(run)
            run = []
        if run or number == 1:
            run.append(marker)
    if len(run) >= minimum_markers:
        replacements.extend(run)
    for marker in reversed(replacements):
        slash = marker.end(1)
        text = text[:slash] + "," + text[slash + 1 :]
    return text


def run_tool(command: list[str]) -> tuple[str, str]:
    """Run a local tool without a shell, capturing stdout and stderr."""
    with (
        tempfile.TemporaryFile() as stdout,
        tempfile.TemporaryFile() as stderr,
    ):
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


def key(spine_index: int, block_index: int) -> str:
    return f"s{spine_index}-b{block_index}"


def load_records(output: Path) -> list[dict]:
    return json.loads((output / "cases.json").read_text(encoding="utf-8"))


def save_records(output: Path, records: list[dict]) -> None:
    (output / "cases.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def prepare(output: Path, source: Path) -> None:
    extract_blocks = importlib.import_module("lyrepub.epub_text").extract_blocks

    if not source.is_file():
        raise FileNotFoundError(source)
    blocks = {(b.spine_index, b.block_index): b for b in extract_blocks(source)}
    expected = set(CASES)
    records = []
    for spine_index, block_index in sorted(expected):
        block = blocks[(spine_index, block_index)]
        if block.tag != "p" or block.run_index != 0:
            message = f"unexpected source target {key(spine_index, block_index)}"
            raise ValueError(message)
        expected_prefix = PREFIXES.get((spine_index, block_index))
        if expected_prefix and not block.text.startswith(expected_prefix):
            message = f"source text changed at {key(spine_index, block_index)}"
            raise ValueError(message)
        records.append(
            {
                "key": key(spine_index, block_index),
                "case": (spine_index, block_index) in CASES,
                "source": {
                    "isbn": ISBN,
                    "spine_index": spine_index,
                    "href": block.href,
                    "block_index": block_index,
                    "element_path": block.element_path,
                    "run_index": block.run_index,
                    "element_id": block.element_id,
                    "text": block.text,
                },
            }
        )
    for record in records:
        target = (record["source"]["spine_index"], record["source"]["block_index"])
        if target in MANUAL_NORMALIZATIONS:
            record["manual_normalization"] = MANUAL_NORMALIZATIONS[target]
    output.mkdir(parents=True, exist_ok=True)
    save_records(output, records)
    (output / "source.json").write_text(
        json.dumps(
            {
                "filename": source.name,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def ogg_duration(path: Path) -> Decimal:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare", "synthesize"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/issue-14-feasibility")
    )
    parser.add_argument("--source-epub", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--voice-dir", type=Path)
    parser.add_argument("--image")
    args = parser.parse_args()
    if args.step == "prepare" and args.source_epub is None:
        parser.error("--source-epub is required")
    if args.step == "prepare":
        prepare(args.output, args.source_epub)
    elif args.step == "synthesize":
        if any(v is None for v in (args.model, args.voice_dir, args.image)):
            parser.error("synthesize requires --model, --voice-dir, --image")
        synthesis = importlib.import_module("scripts.issue14_synthesis")
        synthesis.synthesize(
            args.output,
            args.model,
            args.voice_dir,
            args.image,
        )


if __name__ == "__main__":
    main()
