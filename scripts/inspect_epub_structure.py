"""Inspect EPUB structure: metadata, manifest, spine, ToC, and coverage (Issue #11).

Per book: Dublin Core metadata, manifest inventory, spine reading order with
parser-reported linear status, navigation (NCX) entries, a ToC<->spine join
with coverage gaps, and per-spine-item text-block statistics from the shared
block extractor. Direct observations of source properties only.

fast_ebook 0.2.0 exposes the NCX as a manifest item but does not populate
book.toc from it, so the navMap is parsed from the item content with
defusedxml (S314-safe XML parsing).

Usage:
    pixi run --environment dev python scripts/inspect_epub_structure.py

Writes data/silver/epub_structure.txt; logs the same to stdout.
"""

from __future__ import annotations

import importlib.metadata
import logging
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import unquote

from defusedxml.ElementTree import fromstring
from fast_ebook import EpubItem, epub

from lyrepub.epub_text import extract_blocks

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

logger = logging.getLogger("structure")

REPO_ROOT = Path(__file__).resolve().parents[1]
ISBNS = ("9786045633946", "9786326186253")
_DC_FIELDS = ("title", "creator", "language", "identifier", "date", "publisher")
_XHTML = "application/xhtml+xml"
_NCX = "application/x-dtbncx+xml"
_NCX_NS = "{http://www.daisy.org/z3986/2005/ncx/}"


def _epub_path(isbn: str) -> Path:
    candidates = list((REPO_ROOT / "data" / "bronze" / isbn).glob("*.epub"))
    if len(candidates) != 1:
        msg = f"expected exactly one EPUB for {isbn}, found {len(candidates)}"
        raise ValueError(msg)
    return candidates[0]


def _navpoints(point: Element) -> list[tuple[str, str]]:
    """Return flat (title, href) pairs from a navPoint subtree, depth-first."""
    entries: list[tuple[str, str]] = []
    label = point.find(f"{_NCX_NS}navLabel/{_NCX_NS}text")
    content = point.find(f"{_NCX_NS}content")
    if label is not None and label.text and content is not None:
        entries.append((label.text, content.get("src", "")))
    for child in point.findall(f"{_NCX_NS}navPoint"):
        entries.extend(_navpoints(child))
    return entries


def _read_ncx_toc(items: list[EpubItem]) -> tuple[str, list[tuple[str, str]]]:
    """Return the NCX item's container path and its flat (title, href) pairs."""
    ncx_items = [item for item in items if item.get_media_type() == _NCX]
    if len(ncx_items) != 1:
        msg = f"expected exactly one NCX item, found {len(ncx_items)}"
        raise ValueError(msg)
    root = fromstring(ncx_items[0].get_content())
    nav_map = root.find(f"{_NCX_NS}navMap")
    if nav_map is None:
        msg = "NCX has no navMap"
        raise ValueError(msg)
    entries: list[tuple[str, str]] = []
    for point in nav_map.findall(f"{_NCX_NS}navPoint"):
        entries.extend(_navpoints(point))
    if not entries:
        msg = "NCX navMap has no navPoints"
        raise ValueError(msg)
    return ncx_items[0].get_name(), entries


def _metadata_lines(book: epub.EpubBook) -> list[str]:
    lines = ["-- metadata (DC) --"]
    lines.extend(
        f"{field}: {value}{f' {attrs}' if attrs else ''}"
        for field in _DC_FIELDS
        for value, attrs in book.get_metadata("DC", field)
    )
    return lines


def _manifest_lines(items: list[EpubItem]) -> list[str]:
    counts = Counter(item.get_media_type() for item in items)
    lines = ["-- manifest --"]
    lines.extend(
        f"{media_type}: {count}" for media_type, count in sorted(counts.items())
    )
    lines.extend(
        f"xhtml {item.get_id()} {item.get_name()}"
        for item in sorted(items, key=lambda i: i.get_name())
        if item.get_media_type() == _XHTML
    )
    return lines


def _spine_names(book: epub.EpubBook, epub_path: Path) -> dict[int, str]:
    """Map spine index to manifest item name, validating every idref."""
    names: dict[int, str] = {}
    for spine_index, (idref, _linear) in enumerate(book.get_spine()):
        item = book.get_item_with_id(idref)
        if item is None:
            msg = f"spine idref {idref!r} not in manifest of {epub_path}"
            raise ValueError(msg)
        names[spine_index] = item.get_name()
    return names


def _spine_lines(
    spine: list[tuple[str, bool]], spine_names: dict[int, str]
) -> list[str]:
    lines = ["-- spine (linear status as reported by the parser) --"]
    lines.extend(
        f"s{index} {idref} {spine_names[index]} linear={linear}"
        for index, (idref, linear) in enumerate(spine)
    )
    non_linear = sum(1 for _, linear in spine if not linear)
    lines.append(f"non-linear spine entries: {non_linear}")
    return lines


def _container_path(ncx_name: str, src: str) -> str:
    """Resolve an NCX content@src URI reference to a container-relative path.

    The reference is relative to the NCX item's location in the container;
    the fragment is dropped (document-level matching), percent escapes are
    decoded, and "." / ".." segments are normalized.
    """
    parts: list[str] = []
    for part in (
        *PurePosixPath(ncx_name).parent.parts,
        *PurePosixPath(unquote(src.partition("#")[0])).parts,
    ):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                msg = f"toc src {src!r} escapes the EPUB container root"
                raise ValueError(msg)
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def _join_lines(
    toc: list[tuple[str, str]], ncx_name: str, spine_names: dict[int, str]
) -> list[str]:
    matched: dict[int, str] = {}
    unmatched: list[str] = []
    for title, href in toc:
        target = _container_path(ncx_name, href)
        index = next((i for i, name in spine_names.items() if name == target), None)
        if index is None:
            unmatched.append(f'toc entry not in spine: "{title}" -> {href}')
        else:
            matched[index] = title
    lines = ["-- toc <-> spine join --"]
    lines.extend(f's{i} {spine_names[i]}: "{matched[i]}"' for i in sorted(matched))
    lines.extend(
        f"s{i} {spine_names[i]}: no toc entry"
        for i in sorted(set(spine_names) - set(matched))
    )
    lines.extend(unmatched)
    return lines


def _block_lines(epub_path: Path, spine_names: dict[int, str]) -> list[str]:
    blocks: Counter[int] = Counter()
    chars: Counter[int] = Counter()
    for block in extract_blocks(epub_path):
        blocks[block.spine_index] += 1
        chars[block.spine_index] += len(block.text)
    return [
        "-- per-spine-item text blocks --",
        *(
            f"s{i} {spine_names[i]} blocks={blocks[i]} chars={chars[i]}"
            for i in sorted(spine_names)
        ),
    ]


def inspect(isbn: str, epub_path: Path) -> list[str]:
    """Return the structural report lines for one book."""
    book = epub.read_epub(epub_path)
    items = book.get_items()
    spine = book.get_spine()
    spine_names = _spine_names(book, epub_path)
    ncx_name, toc = _read_ncx_toc(items)
    return [
        f"== {isbn}: {epub_path.name} ==",
        f"fast-ebook=={importlib.metadata.version('fast-ebook')}",
        *_metadata_lines(book),
        *_manifest_lines(items),
        *_spine_lines(spine, spine_names),
        "-- toc --",
        *(f'"{title}" -> {href}' for title, href in toc),
        *_join_lines(toc, ncx_name, spine_names),
        *_block_lines(epub_path, spine_names),
    ]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    silver = REPO_ROOT / "data" / "silver"
    silver.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for isbn in ISBNS:
        lines.extend(inspect(isbn, _epub_path(isbn)))
        lines.append("")
    report = silver / "epub_structure.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        logger.info("%s", line)


if __name__ == "__main__":
    main()
