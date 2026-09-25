"""Shared runner for the per-candidate segmentation screens."""

import importlib.metadata
import platform
import sys
from collections.abc import Callable
from pathlib import Path

from lyrepub.epub_text import extract_blocks
from lyrepub.inspection import SENTENCE_RISK_CASES, resolve_case

REPO_ROOT = Path(__file__).resolve().parents[1]
ISBNS = ("9786045633946", "9786326186253")


def _epub_path(isbn: str) -> Path:
    candidates = list((REPO_ROOT / "data" / "bronze" / isbn).glob("*.epub"))
    if len(candidates) != 1:
        msg = f"expected exactly one EPUB for {isbn}, found {len(candidates)}"
        raise ValueError(msg)
    return candidates[0]


def run_cases(
    candidate: str,
    segment: Callable[[str], list[str]],
    packages: tuple[str, ...],
    notes: tuple[str, ...] = (),
) -> None:
    """Run one segmenter on the frozen cases and write its report.

    Writes data/silver/segmentation_report_<candidate>.txt with an
    environment header, each case's source-located text, and numbered
    sentences. Lines go to the file and stdout directly because logging
    no-ops silently inside the underthesea environment.
    """
    report_path = REPO_ROOT / "data" / "silver" / f"segmentation_report_{candidate}.txt"
    with report_path.open("w", encoding="utf-8") as report:

        def emit(line: str) -> None:
            report.write(line + "\n")
            report.flush()
            sys.stdout.write(line + "\n")

        emit(f"python {platform.python_version()}")
        for package in packages:
            version = importlib.metadata.version(package)
            emit(f"{package}=={version}")
        for note in notes:
            emit(note)

        blocks = {isbn: extract_blocks(_epub_path(isbn)) for isbn in ISBNS}
        for ordinal, case in enumerate(SENTENCE_RISK_CASES, start=1):
            block = resolve_case(case, blocks[case.isbn])
            emit(
                f"== case {ordinal}/{len(SENTENCE_RISK_CASES)} "
                f"{case.isbn} s{block.spine_index} {block.href} #{block.block_index} "
                f"— {case.note}"
            )
            emit(f"TEXT: {block.text}")
            sentences = segment(block.text)
            emit(f"[{candidate}] {len(sentences)} sentences")
            for number, sentence in enumerate(sentences, start=1):
                emit(f"  {number}: {sentence}")
