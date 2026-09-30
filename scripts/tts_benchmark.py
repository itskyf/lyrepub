#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#   "defusedxml>=0.7.1,<0.8", "fast-ebook>=0.2.0,<0.3", "numpy", "soundfile",
#   "vieneu==3.8.3", "sea-g2p==0.10.0", "wtpsplit==2.2.2",
#   "transformers[torch]==5.17.0", "zapros[pyreqwest]==0.19.0",
# ]
# ///
"""Exercise the retained TTS benchmark through the Compose server.

The source location is a runtime input; the model is configured by Compose.
Outputs live in gitignored data/.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from shutil import which

from lyrepub.epub_text import extract_blocks
from lyrepub.segmentation import segment_sentences
from lyrepub.tts_text import normalize_slash_enumeration
from scripts import tts_synthesis
from scripts.tts_synthesis import MANUAL_NORMALIZATIONS

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
LOGGER = logging.getLogger(__name__)


def key(spine_index: int, block_index: int) -> str:
    return f"s{spine_index}-b{block_index}"


def load_records(output: Path) -> list[dict]:
    return json.loads((output / "cases.json").read_text(encoding="utf-8"))


def save_records(output: Path, records: list[dict]) -> None:
    (output / "cases.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def prepare(output: Path, source: Path) -> None:
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


def compare(output: Path, frozen: Path) -> None:
    """Compare frozen sentence inputs, timings and decoded Opus audio."""
    ffmpeg = which("ffmpeg")
    if ffmpeg is None:
        message = "ffmpeg is required for benchmark PCM comparison"
        raise FileNotFoundError(message)
    records = {record["key"]: record for record in load_records(output)}
    comparisons = []
    for baseline in load_records(frozen):
        record = records[baseline["key"]]
        for old, new in zip(baseline["sentences"], record["sentences"], strict=True):
            fields = (
                "source_start",
                "source_end",
                "source_text",
                "tts_input",
                "gaps",
                "clip_begin",
                "clip_end",
            )
            differences = [field for field in fields if old[field] != new[field]]
            old_chunks = [(c["normalized_text"], c["phonemes"]) for c in old["chunks"]]
            new_chunks = [(c["normalized_text"], c["phonemes"]) for c in new["chunks"]]
            if old_chunks != new_chunks:
                differences.append("frontend_chunks")
            hashes = []
            for directory, sentence in ((frozen, old), (output, new)):
                with tempfile.NamedTemporaryFile(suffix=".pcm") as pcm:
                    subprocess.run(
                        [
                            ffmpeg,
                            "-v",
                            "error",
                            "-y",
                            "-i",
                            str(directory / sentence["packaged_audio"]),
                            "-f",
                            "f32le",
                            pcm.name,
                        ],
                        check=True,
                    )
                    hashes.append(
                        hashlib.sha256(Path(pcm.name).read_bytes()).hexdigest()
                    )
            comparisons.append(
                {
                    "key": record["key"],
                    "sentence": new["index"],
                    "differences": differences,
                    "frozen_pcm_sha256": hashes[0],
                    "server_pcm_sha256": hashes[1],
                    "identical_pcm": hashes[0] == hashes[1],
                }
            )
    (output / "benchmark-comparison.json").write_text(
        json.dumps(comparisons, indent=2) + "\n"
    )
    LOGGER.warning(
        "%s sentences; %s field mismatches; %s PCM differences",
        len(comparisons),
        sum(bool(c["differences"]) for c in comparisons),
        sum(not c["identical_pcm"] for c in comparisons),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare", "synthesize", "compare"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/silver/issue-17/tts-benchmark")
    )
    parser.add_argument(
        "--work", type=Path, default=Path("data/work/issue-17/tts-benchmark")
    )
    parser.add_argument("--source-epub", type=Path)
    parser.add_argument("--frozen", type=Path, default=Path("data/silver/issue-14"))
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()
    if args.step == "compare":
        compare(args.output, args.frozen)
        return
    if args.step == "prepare" and args.source_epub is None:
        parser.error("--source-epub is required")
    if args.step == "prepare":
        prepare(args.output, args.source_epub)
    elif args.step == "synthesize":
        if args.concurrency <= 0:
            parser.error("synthesize requires positive --concurrency")
        records = load_records(args.output)
        for record in records:
            source = record["source"]["text"]
            record["sentences"] = tts_synthesis.prepare_sentences(
                source,
                normalize_slash_enumeration(source),
                segment_sentences(source),
                record.get("manual_normalization"),
            )
            record["seed"] = (
                14
                + record["source"]["spine_index"] * 1000
                + record["source"]["block_index"]
            )
            record["status"] = "preprocessed"
        save_records(args.output, records)
        asyncio.run(
            tts_synthesis.synthesize_records(
                args.output,
                args.work,
                records,
                args.concurrency,
                filename="cases.json",
            )
        )


if __name__ == "__main__":
    main()
