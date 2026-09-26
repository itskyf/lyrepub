"""Extraction of traceable text blocks from EPUB publications."""

from dataclasses import dataclass
from pathlib import Path
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


def parse_blocks(
    xhtml: str | bytes, spine_index: int, href: str, *, linear: bool
) -> list[Block]:
    """Parse one XHTML spine document into source-located readable blocks.

    Raises ValueError for malformed XML or missing XHTML document structure.
    """
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

    blocks: list[Block] = []
    owners: list[tuple[ET.Element, tuple[int, ...], str | None]] = []
    parts: list[str] = []
    run_counts: dict[tuple[int, ...], int] = {}

    def flush() -> None:
        text = " ".join("".join(parts).split())
        parts.clear()
        if not text:
            return
        element, path, lang = owners[-1]
        run_index = run_counts.get(path, 0)
        run_counts[path] = run_index + 1
        blocks.append(
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
            parts.append(" ")
        if element.text:
            parts.append(element.text)
        for index, child in enumerate(element):
            visit(child, (*path, index), lang)
            if child.tail:
                parts.append(child.tail)
        if owns_text:
            flush()
            owners.pop()

    html_lang = root.get(_XML_LANG)
    if html_lang is None:
        html_lang = root.get("lang")
    visit(children[1], (1,), html_lang)
    return blocks


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
