#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "fast-ebook",
#     "lingua-language-detector",
# ]
# ///
"""Surface plausible code-switched/mixed-language blocks (Issue #11).

Runs lingua's mixed-language detection (detect_multiple_languages_of) over
every corpus block — block-level LID cannot exclude intra-block
code-switching, so no block is pre-filtered — and reports only blocks whose
spans include a non-Vietnamese language or more than one language. The
output is automated candidate evidence for focused manual inspection, not a
reference annotation or a corpus distribution. lingua's mixed-language mode
is experimental and less reliable on short phrases.

    PYTHONPATH=src pixi run --environment dev uv run --script \
        scripts/screen_language_mixing.py

Reads data/silver/blocks_enriched.csv (from scripts/screen_ner.py; block
level lid_label/lid_prob are recorded as context only) and writes
data/silver/language_mixing_report.txt; runtime package versions are logged
in the report.
"""

import csv
import importlib.metadata
import logging
import platform
from collections import Counter
from pathlib import Path

from lingua import DetectionResult, Language, LanguageDetector, LanguageDetectorBuilder

from lyrepub.epub_text import extract_blocks

logger = logging.getLogger("mixing")

REPO_ROOT = Path(__file__).resolve().parents[1]
ISBNS = ("9786045633946", "9786326186253")
_SPAN_TEXT_LIMIT = 100
_PROGRESS_EVERY = 250
_VIETNAMESE = "vi"


def _epub_path(isbn: str) -> Path:
    candidates = list((REPO_ROOT / "data" / "bronze" / isbn).glob("*.epub"))
    if len(candidates) != 1:
        msg = f"expected exactly one EPUB for {isbn}, found {len(candidates)}"
        raise ValueError(msg)
    return candidates[0]


def _iso(language: Language) -> str:
    return language.iso_code_639_1.name.lower()


def _flagged(spans: list[DetectionResult]) -> bool:
    """True when spans contain a non-Vietnamese language or more than one.

    Languages are compared by ISO code because lingua's PyO3 enum members
    do not satisfy identity comparison across accesses.
    """
    languages = {_iso(span.language) for span in spans}
    return len(languages) > 1 or _VIETNAMESE not in languages


def _span_line(text: str, span: DetectionResult) -> str:
    span_text = text[span.start_index : span.end_index][:_SPAN_TEXT_LIMIT]
    return (
        f"  {span.start_index}:{span.end_index} {_iso(span.language)} "
        f"({span.word_count} words): {span_text}"
    )


def _block_lines(text: str, spans: list[DetectionResult]) -> list[str]:
    return [f"TEXT: {text}", *(_span_line(text, span) for span in spans)]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    silver = REPO_ROOT / "data" / "silver"

    with (REPO_ROOT / "data/silver/blocks_enriched.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = {
            (row["isbn"], int(row["spine_index"]), int(row["block_index"])): row
            for row in csv.DictReader(handle)
        }

    detector: LanguageDetector = LanguageDetectorBuilder.from_all_languages().build()
    lingua_version = importlib.metadata.version("lingua-language-detector")
    report = [
        f"python {platform.python_version()}",
        f"fast-ebook=={importlib.metadata.version('fast-ebook')}",
        f"lingua-language-detector=={lingua_version}",
        "criterion: spans include a non-Vietnamese language or more than one language",
        "block-level lid_label/lid_prob shown as context only",
    ]

    flagged: Counter[str] = Counter()
    total: Counter[str] = Counter()
    for isbn in ISBNS:
        blocks = extract_blocks(_epub_path(isbn))
        for processed, block in enumerate(blocks, start=1):
            if processed % _PROGRESS_EVERY == 0:
                logger.info("%s: processed %d/%d", isbn, processed, len(blocks))
            total[isbn] += 1
            spans = detector.detect_multiple_languages_of(block.text)
            if not _flagged(spans):
                continue
            flagged[isbn] += 1
            row = rows[(isbn, block.spine_index, block.block_index)]
            report.append(
                f"== {isbn} s{block.spine_index} {block.href} #{block.block_index} "
                f"lid={row['lid_label']} p={row['lid_prob']} len={len(block.text)} =="
            )
            report.extend(_block_lines(block.text, spans))

    report.append("-- flagged blocks (blocks whose spans met the criterion) --")
    report.extend(f"{isbn}: {flagged[isbn]} of {total[isbn]}" for isbn in ISBNS)
    (silver / "language_mixing_report.txt").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    logger.info("wrote %s", silver / "language_mixing_report.txt")


if __name__ == "__main__":
    main()
