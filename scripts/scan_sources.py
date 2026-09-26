"""Scan bronze EPUB sources for processing-relevant properties (Issue #11).

Per block: character length, digit/number/date forms, punctuation types
and density, adjacent repetition, sentence counts and lengths (SaT), and
a Unicode/source-quality inventory. Entity and language evidence comes
from scripts/screen_ner.py. Source observations, not difficulty scores.

Usage:
    pixi run --environment dev python scripts/scan_sources.py

Writes data/silver/blocks.csv and data/silver/scan_summary.txt; logs the
same summary to stdout.
"""

import csv
import logging
import re
import statistics
import unicodedata
from collections.abc import Iterator
from itertools import islice
from pathlib import Path

from lyrepub.epub_text import Block, extract_blocks
from lyrepub.segmentation import segment_sentences

logger = logging.getLogger("scan")

REPO_ROOT = Path(__file__).resolve().parents[1]
ISBNS = ("9786045633946", "9786326186253")
_MAX_LOC = 2

_DIGIT_RUN = re.compile(r"\d+")
_YEAR_LIKE = re.compile(r"\b1[0-9]\d{2}\b|\b20\d{2}\b")
_DATE_LIKE = re.compile(r"\b\d{1,2}[/\-.]\d{1,2}([/\-.]\d{2,4})?\b")
_REPEATED_WORD = re.compile(r"(\b\w+\b)(?:\s+\1\b)", re.IGNORECASE)
_PUNCT_COUNTS = (
    ("quote_curly_open", "\u201c"),
    ("quote_curly_close", "\u201d"),
    ("quote_straight", '"'),
    ("dash_em", "—"),
    ("ellipsis_char", "…"),
    ("question", "?"),
    ("exclamation", "!"),
    ("colon", ":"),
    ("semicolon", ";"),
    ("paren_open", "("),
)
# Symbols with a legitimate typographic role; other S-category characters
# are reported as unusual.
_EXPECTED_SYMBOLS = set("—…\u201c\u201d«»©°+±÷=<>≤≥§†‡•*$&#@") | {
    chr(0x2013),  # en dash
    chr(0x2018),  # left single quotation mark
    chr(0x2019),  # right single quotation mark
    chr(0x00D7),  # multiplication sign
}


def _epub_path(isbn: str) -> Path:
    candidates = list((REPO_ROOT / "data" / "bronze" / isbn).glob("*.epub"))
    if len(candidates) != 1:
        msg = f"expected exactly one EPUB for {isbn}, found {len(candidates)}"
        raise ValueError(msg)
    return candidates[0]


def _repeated_bigram(text: str) -> int:
    words = text.split()
    return sum(
        1
        for i in range(len(words) - 3)
        if words[i].lower() == words[i + 2].lower()
        and words[i + 1].lower() == words[i + 3].lower()
    )


def _quality_flags(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ch in set(text):
        category = unicodedata.category(ch)
        if category in ("Cc", "Cf", "Co", "Cs") or ch == "�":
            reason = f"unicode_{category}_{ord(ch):04X}"
        elif category.startswith("L") and "LATIN" not in unicodedata.name(ch, ""):
            reason = f"non_latin_letter_{unicodedata.name(ch, '?').split()[0]}"
        elif category in ("So", "Sk") and ch not in _EXPECTED_SYMBOLS:
            reason = f"unusual_symbol_{category}_{ord(ch):04X}"
        else:
            continue
        counts[reason] = counts.get(reason, 0) + text.count(ch)
    return counts


def _block_row(isbn: str, block: Block) -> dict[str, object]:
    text = block.text
    row: dict[str, object] = {
        "isbn": isbn,
        "spine_index": block.spine_index,
        "href": block.href,
        "block_index": block.block_index,
        "char_len": len(text),
        "digit_runs": len(_DIGIT_RUN.findall(text)),
        "year_like": len(_YEAR_LIKE.findall(text)),
        "date_like": len(_DATE_LIKE.findall(text)),
        "starts_with_dash": int(text.startswith(("- ", "— "))),
        "repeated_word": len(_REPEATED_WORD.findall(text)),
        "repeated_bigram": _repeated_bigram(text),
    }
    for name, char in _PUNCT_COUNTS:
        row[name] = text.count(char)
    return row


def _percentile(values: list[int], pct: int) -> float:
    """pct-th percentile by linear interpolation between order
    statistics (statistics.quantiles 'inclusive', the numpy-compatible
    convention)."""
    return statistics.quantiles(values, n=100, method="inclusive")[pct - 1]


def _examples(
    rows: list[dict[str, object]],
    key: str,
    texts: dict[tuple[str, int, int], str],
    limit: int = 3,
) -> Iterator[str]:
    ranked = sorted(rows, key=lambda r: -int(r[key]))
    top = islice((r for r in ranked if int(r[key]) > 0), limit)
    for row in top:
        loc = (str(row["isbn"]), int(row["spine_index"]), int(row["block_index"]))
        where = (
            f"{row['isbn']} s{row['spine_index']} {row['href']} #{row['block_index']}"
        )
        yield f"    {where} ({key}={row[key]}): {texts[loc][:100]}"


_COUNT_KEYS = tuple(
    name
    for name, _ in (
        *_PUNCT_COUNTS,
        ("digit_runs", ""),
        ("year_like", ""),
        ("date_like", ""),
        ("repeated_word", ""),
        ("repeated_bigram", ""),
    )
)


def summarize(
    isbn: str, rows: list[dict[str, object]], texts: dict[tuple[str, int, int], str]
) -> list[str]:
    lines = [f"== {isbn} =="]
    lengths = [int(r["char_len"]) for r in rows]
    stats = (
        f"blocks={len(rows)} char_len min={min(lengths)} "
        f"median={statistics.median(lengths):.0f} "
        f"p90={_percentile(lengths, 90):.0f} "
        f"p99={_percentile(lengths, 99):.0f} max={max(lengths)}"
    )
    lines.append(stats)
    total_chars = max(sum(lengths), 1)
    for name in _COUNT_KEYS:
        total = sum(int(r[name]) for r in rows)
        blocks_with = sum(1 for r in rows if int(r[name]) > 0)
        density = total / total_chars * 1000
        lines.append(
            f"{name}: total={total} blocks_with={blocks_with} per_1k={density:.2f}"
        )
        lines.extend(_examples(rows, name, texts))
    dashes = sum(int(r["starts_with_dash"]) for r in rows)
    lines.append(f"starts_with_dash (dialogue-style): {dashes} blocks")
    return lines


def quality_inventory(
    all_rows: list[dict[str, object]], texts: dict[tuple[str, int, int], str]
) -> list[str]:
    lines = ["== unicode/source-quality inventory (both books) =="]
    totals: dict[str, int] = {}
    locations: dict[str, list[str]] = {}
    for row in all_rows:
        loc = (str(row["isbn"]), int(row["spine_index"]), int(row["block_index"]))
        for reason, count in _quality_flags(texts[loc]).items():
            totals[reason] = totals.get(reason, 0) + count
            locations.setdefault(reason, []).append(
                f"{row['isbn']} s{row['spine_index']} #{row['block_index']}"
            )
    if not totals:
        lines.append(
            "no control/format/private-use/replacement characters, "
            "non-Latin letters, or unusual symbols found"
        )
    for reason, total in sorted(totals.items(), key=lambda kv: -kv[1]):
        found_at = locations[reason]
        where = ", ".join(found_at[:_MAX_LOC])
        more = (
            f" (+{len(found_at) - _MAX_LOC} more)" if len(found_at) > _MAX_LOC else ""
        )
        lines.append(f"{reason}: count={total} at {where}{more}")
    return lines


def sentence_stats(blocks: list[Block], rows: list[dict[str, object]]) -> list[str]:
    """Add per-block sentence counts and return length-distribution lines."""
    lengths: list[int] = []
    for row, block in zip(rows, blocks, strict=True):
        sentences = segment_sentences(block.text)
        row["sent_count"] = len(sentences)
        lengths.extend(len(sentence) for sentence in sentences)
    median = statistics.median(lengths)
    return [
        (
            f"sentence_len: count={len(lengths)} min={min(lengths)} "
            f"median={median:.0f} p90={_percentile(lengths, 90):.0f} "
            f"p99={_percentile(lengths, 99):.0f} max={max(lengths)}"
        )
    ]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    silver = REPO_ROOT / "data" / "silver"
    silver.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, object]] = []
    texts: dict[tuple[str, int, int], str] = {}
    summary: list[str] = []
    for isbn in ISBNS:
        blocks = extract_blocks(_epub_path(isbn))
        rows = [_block_row(isbn, b) for b in blocks]
        for b in blocks:
            texts[(isbn, b.spine_index, b.block_index)] = b.text
        all_rows.extend(rows)
        summary.extend(summarize(isbn, rows, texts))
        summary.extend(sentence_stats(blocks, rows))
    summary.extend(quality_inventory(all_rows, texts))

    fieldnames = list(all_rows[0])
    with (silver / "blocks.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    (silver / "scan_summary.txt").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )
    for line in summary:
        logger.info("%s", line)


if __name__ == "__main__":
    main()
