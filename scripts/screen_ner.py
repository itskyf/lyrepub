#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "fast-ebook",
#     "huggingface_hub",
#     "lingua-language-detector",
#     "torch",
#     "transformers",
# ]
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
#
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# ///
"""NER adequacy check and corpus-wide candidate finding.

Screens the single NER candidate NlpHUST/ner-vietnamese-electra-base
through the Transformers token-classification pipeline (built-in
aggregation only) on the frozen entity-rich cases, then corpus-wide to
attach candidate named-entity counts and lingua-py language evidence to
every source block. Candidate-finding aid for Issue #11, not a NER
comparison or benchmark. uv builds an isolated environment from the
inline metadata, so no project dependency is touched:

    PYTHONPATH=src pixi run --environment dev uv run --script scripts/screen_ner.py

Reads data/silver/blocks.csv (from scripts/scan_sources.py) and writes
data/silver/blocks_enriched.csv plus data/silver/ner_report.txt; runtime
package versions and checkpoint revisions are logged in the report.
"""

import csv
import importlib.metadata
import logging
import platform
from collections import Counter
from pathlib import Path

import torch
from lingua import LanguageDetector, LanguageDetectorBuilder
from transformers import pipeline

from lyrepub.epub_text import extract_blocks
from lyrepub.inspection import ENTITY_RICH_CASES, resolve_case
from lyrepub.ner import NER_MODEL, NER_REVISION

REPO_ROOT = Path(__file__).resolve().parents[1]
ISBNS = ("9786045633946", "9786326186253")
ENTITY_GROUPS = ("PER", "LOC", "ORG", "MISC")
VIETNAMESE = "vi"

logger = logging.getLogger("screen")


def _epub_path(isbn: str) -> Path:
    candidates = list((REPO_ROOT / "data" / "bronze" / isbn).glob("*.epub"))
    if len(candidates) != 1:
        msg = f"expected exactly one EPUB for {isbn}, found {len(candidates)}"
        raise ValueError(msg)
    return candidates[0]


def log_header() -> None:
    logger.info("python %s", platform.python_version())
    packages = (
        "fast-ebook",
        "huggingface_hub",
        "lingua-language-detector",
        "torch",
        "transformers",
    )
    for package in packages:
        logger.info("%s==%s", package, importlib.metadata.version(package))
    logger.info("cuda available: %s", torch.cuda.is_available())
    logger.info("%s revision %s (enforced)", NER_MODEL, NER_REVISION)


def adequacy(ner: pipeline, blocks: dict[str, list]) -> None:
    """Judge the candidate on the frozen entity-rich cases."""
    logger.info("id2label: %s", list(ner.model.config.id2label.values()))
    for ordinal, case in enumerate(ENTITY_RICH_CASES, start=1):
        block = resolve_case(case, blocks[case.isbn])
        logger.info(
            "== case %d/%d %s s%d %s #%d — %s",
            ordinal,
            len(ENTITY_RICH_CASES),
            case.isbn,
            block.spine_index,
            block.href,
            block.block_index,
            case.note,
        )
        logger.info("TEXT: %s", block.text)
        # stride keeps long blocks whole across model-context chunks
        entities = ner(block.text, stride=64)
        logger.info(
            "%d entities (offsets into the collapsed block text)", len(entities)
        )
        for entity in sorted(entities, key=lambda e: e["start"]):
            logger.info(
                "  %d-%d %s %.3f %s",
                entity["start"],
                entity["end"],
                entity["entity_group"],
                entity["score"],
                entity["word"],
            )


def corpus_pass(ner: pipeline, detector: LanguageDetector) -> None:
    """Attach entity counts and language evidence to every source block."""
    blocks_csv = REPO_ROOT / "data/silver/blocks.csv"
    with blocks_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_key = {
        (row["isbn"], int(row["spine_index"]), int(row["block_index"])): row
        for row in rows
    }

    totals: dict[str, Counter[str]] = {}
    languages: dict[str, Counter[str]] = {}
    for isbn in ISBNS:
        blocks = extract_blocks(_epub_path(isbn))
        texts = [block.text for block in blocks]
        # Context limits are token-based: report blocks the pipeline will
        # actually chunk, from tokenizer lengths against the model limit.
        token_counts = [len(ids) for ids in ner.tokenizer(texts)["input_ids"]]
        over_context = sum(
            1 for count in token_counts if count > ner.tokenizer.model_max_length
        )
        logger.info(
            "%s: %d blocks, %d over the %d-token model context "
            "(chunked by the pipeline with stride)",
            isbn,
            len(texts),
            over_context,
            ner.tokenizer.model_max_length,
        )
        entity_counts: list[Counter[str]] = []
        for entities in ner(texts, batch_size=64, stride=64):
            counter: Counter[str] = Counter()
            for entity in entities:
                counter[entity["entity_group"]] += 1
            entity_counts.append(counter)

        totals[isbn] = Counter()
        languages[isbn] = Counter()
        for block, counter, text in zip(blocks, entity_counts, texts, strict=True):
            language = detector.detect_language_of(text)
            row = by_key[(isbn, block.spine_index, block.block_index)]
            for group in ENTITY_GROUPS:
                row[f"ner_{group.lower()}"] = str(counter.get(group, 0))
            row["lid_label"] = (
                language.iso_code_639_1.name.lower() if language else "und"
            )
            confidence = (
                detector.compute_language_confidence(text, language)
                if language
                else 0.0
            )
            row["lid_prob"] = f"{confidence:.3f}"
            totals[isbn].update(counter)
            languages[isbn][row["lid_label"]] += 1

    fieldnames = list(rows[0])
    with (REPO_ROOT / "data/silver/blocks_enriched.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    for isbn in ISBNS:
        logger.info("%s candidate detections by label: %s", isbn, dict(totals[isbn]))
        logger.info("%s languages: %s", isbn, dict(languages[isbn].most_common()))
        for row in rows:
            if row["isbn"] == isbn and row["lid_label"] != VIETNAMESE:
                logger.info(
                    "  non-Vietnamese: s%s %s #%s %s p=%s",
                    row["spine_index"],
                    row["href"],
                    row["block_index"],
                    row["lid_label"],
                    row["lid_prob"],
                )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(REPO_ROOT / "data/silver/ner_report.txt", mode="w"),
        ],
    )
    log_header()
    device = 0 if torch.cuda.is_available() else -1
    ner = pipeline(
        "token-classification",
        model=NER_MODEL,
        revision=NER_REVISION,
        aggregation_strategy="simple",
        device=device,
    )
    # The checkpoint ships no tokenizer model_max_length (unset sentinel),
    # so the pipeline would never truncate; use the model's own positional
    # limit for stride chunking of long blocks.
    ner.tokenizer.model_max_length = ner.model.config.max_position_embeddings
    blocks = {isbn: extract_blocks(_epub_path(isbn)) for isbn in ISBNS}
    adequacy(ner, blocks)
    detector = LanguageDetectorBuilder.from_all_languages().build()
    corpus_pass(ner, detector)


main()
