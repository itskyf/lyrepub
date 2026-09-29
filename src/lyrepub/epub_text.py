"""Extraction of traceable text blocks from EPUB publications."""

import re
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

from defusedxml import ElementTree
from fast_ebook import epub

_XHTML_NS = "http://www.w3.org/1999/xhtml"
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_EPUB_TYPE = "{http://www.idpf.org/2007/ops}type"
_SVG_NS = "{http://www.w3.org/2000/svg}"
_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "dd",
        "details",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "summary",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
)
_SKIP_TAGS = frozenset(f"{{{_XHTML_NS}}}{tag}" for tag in ("script", "style"))


@dataclass(frozen=True, slots=True)
class Block:
    """Readable text and its deterministic location in an EPUB spine document.

    ``element_id`` is authored XHTML; ``element_path`` and ``run_index``
    locate text without claiming that an EPUB fragment ID exists.
    """

    text: str
    spine_index: int
    href: str
    block_index: int
    linear: bool
    element_path: tuple[int, ...]
    run_index: int
    element_id: str | None
    tag: str
    lang: str | None
    epub_type: str | None
    role: str | None


def _parse_xhtml(xhtml: str | bytes, href: str) -> ET.Element:
    try:
        root = ElementTree.fromstring(xhtml)
    except ET.ParseError as exc:
        msg = f"invalid XHTML in {href}: {exc}"
        raise ValueError(msg) from exc

    children = list(root)
    if (
        root.tag != f"{{{_XHTML_NS}}}html"
        or [child.tag for child in children]
        != [f"{{{_XHTML_NS}}}head", f"{{{_XHTML_NS}}}body"]
        or any(
            text and text.strip() for text in (root.text, *(c.tail for c in children))
        )
    ):
        msg = f"invalid XHTML document structure in {href}"
        raise ValueError(msg)

    return root


def _located_blocks(
    root: ET.Element, spine_index: int, href: str, *, linear: bool
) -> list[tuple[Block, list[tuple[ET.Element, str, str]]]]:
    blocks: list[tuple[Block, list[tuple[ET.Element, str, str]]]] = []
    owners: list[tuple[ET.Element, tuple[int, ...], str | None]] = []
    parts: list[tuple[ET.Element, str, str]] = []
    run_counts: dict[tuple[int, ...], int] = {}

    def flush() -> None:
        text = " ".join("".join(part[2] for part in parts).split())
        source_parts = parts.copy()
        parts.clear()
        if not text:
            return
        element, path, lang = owners[-1]
        run_index = run_counts.get(path, 0)
        run_counts[path] = run_index + 1
        blocks.append(
            (
                Block(
                    text=text,
                    spine_index=spine_index,
                    href=href,
                    block_index=len(blocks),
                    linear=linear,
                    element_path=path,
                    run_index=run_index,
                    element_id=element.get("id"),
                    tag=element.tag.rpartition("}")[2],
                    lang=lang,
                    epub_type=element.get(_EPUB_TYPE),
                    role=element.get("role"),
                ),
                source_parts,
            )
        )

    def visit(
        element: ET.Element, path: tuple[int, ...], inherited_lang: str | None
    ) -> None:
        if element.tag in _SKIP_TAGS or element.tag.startswith(_SVG_NS):
            return
        lang = element.get(_XML_LANG)
        if lang is None:
            lang = element.get("lang")
        if lang is None:
            lang = inherited_lang
        tag = element.tag.rpartition("}")[2]
        owns_text = (
            not owners
            or (element.tag.startswith(f"{{{_XHTML_NS}}}") and tag in _BLOCK_TAGS)
            or element.get("id") is not None
            or element.get(_EPUB_TYPE) is not None
            or element.get("role") is not None
            or lang != inherited_lang
        )
        if owns_text:
            if owners:
                flush()
            owners.append((element, path, lang))
        if element.tag == f"{{{_XHTML_NS}}}br":
            parts.append((element, "br", " "))
        if element.text:
            parts.append((element, "text", element.text))
        for index, child in enumerate(element):
            visit(child, (*path, index), lang)
            if child.tail:
                parts.append((child, "tail", child.tail))
        if owns_text:
            flush()
            owners.pop()

    html_lang = root.get(_XML_LANG)
    if html_lang is None:
        html_lang = root.get("lang")
    visit(root[1], (1,), html_lang)
    return blocks


def parse_blocks(
    xhtml: str | bytes, spine_index: int, href: str, *, linear: bool
) -> list[Block]:
    """Parse one XHTML spine document into source-located readable blocks.

    Raises ValueError for malformed XML or missing XHTML document structure.
    """
    return [
        block
        for block, _ in _located_blocks(
            _parse_xhtml(xhtml, href), spine_index, href, linear=linear
        )
    ]


def _document_positions(
    root: ET.Element,
) -> tuple[str, dict[ET.Element, tuple[int, int]], dict[tuple[ET.Element, str], int]]:
    parts: list[str] = []
    bounds: dict[ET.Element, tuple[int, int]] = {}
    offsets: dict[tuple[ET.Element, str], int] = {}
    cursor = 0

    def append(element: ET.Element, slot: str, text: str) -> None:
        nonlocal cursor
        offsets[element, slot] = cursor
        parts.append(text)
        cursor += len(text)

    def visit(element: ET.Element) -> None:
        start = cursor
        if element.tag == f"{{{_XHTML_NS}}}br":
            append(element, "br", " ")
        append(element, "text", element.text or "")
        for child in element:
            visit(child)
            append(child, "tail", child.tail or "")
        bounds[element] = (start, cursor)

    visit(root)
    return "".join(parts), bounds, offsets


def _normalized_positions(
    parts: list[tuple[ET.Element, str, str]],
    offsets: dict[tuple[ET.Element, str], int],
) -> list[tuple[int, int]]:
    raw = "".join(part[2] for part in parts)
    origins = [
        position
        for element, slot, text in parts
        for position in range(
            offsets[element, slot], offsets[element, slot] + len(text)
        )
    ]
    positions: list[tuple[int, int]] = []
    for word in re.finditer(r"\S+", raw):
        if positions:
            positions.append((positions[-1][1], origins[word.start()]))
        positions.extend((origins[i], origins[i] + 1) for i in range(*word.span()))
    return positions


def _append_text(element: ET.Element, text: str) -> None:
    if len(element):
        element[-1].tail = (element[-1].tail or "") + text
    else:
        element.text = (element.text or "") + text


def _split_content(
    element: ET.Element,
    cut: int,
    bounds: dict[ET.Element, tuple[int, int]],
    offsets: dict[tuple[ET.Element, str], int],
) -> ET.Element:
    """Keep content before a source boundary; return the remaining content."""
    original_start, original_end = bounds[element]
    right = ET.Element(element.tag, element.attrib)
    bounds[right] = (cut, original_end)
    bounds[element] = (original_start, cut)
    offsets[right, "text"] = max(cut, offsets[element, "text"])
    offsets[right, "tail"] = offsets.get((element, "tail"), original_end)
    text = element.text or ""
    index = max(0, cut - offsets[element, "text"])
    element.text, right.text = text[:index], text[index:]
    children = list(element)
    element[:] = []
    for child in children:
        tail = child.tail or ""
        child.tail = None
        start, end = bounds[child]
        if end <= cut:
            element.append(child)
        elif start >= cut:
            right.append(child)
        else:
            if child.get("id") is not None:
                msg = "sentence boundary would duplicate an authored ID"
                raise ValueError(msg)
            remainder = _split_content(child, cut, bounds, offsets)
            element.append(child)
            right.append(remainder)
        index = max(0, cut - offsets[child, "tail"])
        _append_text(element, tail[:index])
        _append_text(right, tail[index:])
    return right


def _wrap_sentence(
    container: ET.Element,
    interval: tuple[int, int],
    element_id: str,
    bounds: dict[ET.Element, tuple[int, int]],
    offsets: dict[tuple[ET.Element, str], int],
) -> None:
    start, end = interval
    original_bounds = bounds[container]
    suffix = _split_content(container, end, bounds, offsets)
    sentence = _split_content(container, start, bounds, offsets)
    span = ET.Element(f"{{{_XHTML_NS}}}span", {"id": element_id})
    span.text = sentence.text
    span.extend(sentence)
    container.append(span)
    _append_text(container, suffix.text or "")
    container.extend(suffix)
    bounds[container] = original_bounds
    bounds[span] = (start, end)
    offsets[span, "text"] = start
    offsets[span, "tail"] = end


def _validate_sentence(
    block: Block, index: int, start: int, end: int, text: str
) -> None:
    if (
        any(type(value) is not int for value in (index, start, end))
        or index < 0
        or not 0 <= start < end <= len(block.text)
        or block.text[start:end] != text
        or not text.strip()
        or text != text.strip()
    ):
        msg = "invalid sentence range or source text drift"
        raise ValueError(msg)


def _sentence_container(
    root: ET.Element,
    path: tuple[int, ...],
    interval: tuple[int, int],
    raw: str,
    bounds: dict[ET.Element, tuple[int, int]],
) -> tuple[ET.Element, bool]:
    owner = root
    for child_index in path:
        owner = owner[child_index]
    start, end = interval
    container = owner
    for element in owner.iter():
        left, right = bounds[element]
        if left <= start < end <= right:
            content = raw[left:right]
            if (
                left + len(content) - len(content.lstrip()) == start
                and right - len(content) + len(content.rstrip()) == end
            ):
                return element, True
            container = element
    return container, False


def materialize_sentence_targets(
    xhtml: str | bytes, targets: list[tuple[Block, int, int, int, str]]
) -> tuple[bytes, list[str]]:
    """Address frozen sentence ranges without replacing authored XHTML text.

    Each target contains a matched Block, sentence index, normalized start/end
    offsets (end exclusive), and exact sentence text. Returned fragment hrefs
    follow input order. All targets must refer to the same original document.
    Invalid locations, source drift, overlapping ranges, and ID collisions raise
    ValueError. Inputs are not mutated and no sentence segmentation is performed.
    """
    if not targets:
        msg = "at least one sentence target is required"
        raise ValueError(msg)
    first = targets[0][0]
    root = _parse_xhtml(xhtml, first.href)
    located = _located_blocks(root, first.spine_index, first.href, linear=first.linear)
    current = dict(located)
    ids = [
        element.get("id") for element in root.iter() if element.get("id") is not None
    ]
    if len(ids) != len(set(ids)):
        msg = "duplicate XHTML IDs"
        raise ValueError(msg)
    used_ids = set(ids)
    raw, bounds, offsets = _document_positions(root)
    identities: set[tuple[int, int]] = set()
    ranges: list[tuple[int, int]] = []
    edits: list[tuple[int, int, ET.Element, str, bool]] = []
    hrefs: list[str] = []
    for block, index, start, end, text in targets:
        if block not in current:
            msg = f"unresolvable block location or source drift: {block.href!r}"
            raise ValueError(msg)
        _validate_sentence(block, index, start, end, text)
        identity = (block.block_index, index)
        if identity in identities:
            msg = "duplicate sentence identity"
            raise ValueError(msg)
        identities.add(identity)
        positions = _normalized_positions(current[block], offsets)
        source_start, source_end = positions[start][0], positions[end - 1][1]
        ranges.append((source_start, source_end))
        element, exact = _sentence_container(
            root, block.element_path, (source_start, source_end), raw, bounds
        )
        element_id = element.get("id") if exact else None
        if element_id is None:
            element_id = (
                f"lyrepub-sentence-{block.spine_index}-{block.block_index}-{index}"
            )
            if element_id in used_ids:
                msg = f"XHTML ID collision: {element_id!r}"
                raise ValueError(msg)
            used_ids.add(element_id)
        hrefs.append(f"{block.href}#{quote(element_id, safe='')}")
        edits.append((source_start, source_end, element, element_id, exact))
    ordered_ranges = sorted(ranges)
    if any(left[1] > right[0] for left, right in pairwise(ordered_ranges)):
        msg = "overlapping sentence ranges"
        raise ValueError(msg)
    # Later edits keep the original coordinates of the remaining prefixes usable.
    for start, end, element, element_id, exact in sorted(
        edits, key=lambda row: row[0], reverse=True
    ):
        if exact:
            element.set("id", element_id)
        else:
            _wrap_sentence(element, (start, end), element_id, bounds, offsets)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), hrefs


def extract_blocks(epub_path: Path) -> list[Block]:
    """Read all XHTML spine documents in EPUB reading order.

    XML encoding follows its declaration or BOM; text is never
    Unicode-normalized. Missing spine references and non-XHTML spine items
    raise ValueError.
    """
    book = epub.read_epub(epub_path, options={"ignore_ncx": True, "ignore_nav": True})
    blocks: list[Block] = []
    for spine_index, (idref, linear) in enumerate(book.get_spine()):
        item = book.get_item_with_id(idref)
        if item is None:
            msg = f"spine idref {idref!r} not in manifest of {epub_path}"
            raise ValueError(msg)
        if item.get_media_type() != "application/xhtml+xml":
            msg = f"spine idref {idref!r} is not XHTML in {epub_path}"
            raise ValueError(msg)
        content = item.get_content()
        if not content:
            msg = f"spine idref {idref!r} has empty or missing content in {epub_path}"
            raise ValueError(msg)
        blocks.extend(
            parse_blocks(content, spine_index, item.get_name(), linear=linear)
        )
    return blocks
