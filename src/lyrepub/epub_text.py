"""Extraction of traceable text blocks from EPUB publications."""

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from fast_ebook import epub


@dataclass(frozen=True, slots=True)
class Block:
    """One extracted text block with its EPUB source location.

    Args:
        text: Block text, whitespace collapsed to single spaces.
        spine_index: Zero-based position of the document in spine order.
        href: Item file name inside the EPUB.
        block_index: Zero-based ordinal of the block within its document.
    """

    text: str
    spine_index: int
    href: str
    block_index: int


_BLOCK_TAGS = frozenset(
    {
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "blockquote",
        "div",
        "section",
        "figcaption",
    }
)
_SKIP_TAGS = frozenset({"head", "style", "script", "svg"})


class BlockExtractor(HTMLParser):
    """Accumulate text into Blocks in document order.

    Block elements delimit blocks, inline elements flatten, and
    head/style/script/svg subtrees are skipped. Text inside a container
    before a nested block element is dropped; prose lives in the block
    elements of these publications.
    """

    def __init__(self, spine_index: int, href: str) -> None:
        super().__init__(convert_charrefs=True)
        self._spine_index = spine_index
        self._href = href
        self._parts: list[str] | None = None
        self._skip_depth = 0
        self.blocks: list[Block] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_depth > 0:
            if tag in _SKIP_TAGS:
                self._skip_depth += 1
            return
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth > 0:
            if tag in _SKIP_TAGS:
                self._skip_depth -= 1
            return
        if tag in _BLOCK_TAGS and self._parts is not None:
            text = " ".join("".join(self._parts).split())
            if text:
                self.blocks.append(
                    Block(text, self._spine_index, self._href, len(self.blocks))
                )
            self._parts = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and self._parts is not None:
            self._parts.append(data)


def parse_blocks(xhtml: str, spine_index: int, href: str) -> list[Block]:
    """Parse one spine document's XHTML into blocks in document order."""
    extractor = BlockExtractor(spine_index, href)
    extractor.feed(xhtml)
    extractor.close()
    return extractor.blocks


def extract_blocks(epub_path: Path) -> list[Block]:
    """Read an EPUB and return all spine text blocks in reading order.

    Documents are strict UTF-8 and never Unicode-normalized.

    Raises:
        UnicodeDecodeError: If a spine document is not valid UTF-8.
        ValueError: If a spine idref is missing from the manifest.
    """
    book = epub.read_epub(epub_path, options={"ignore_ncx": True, "ignore_nav": True})
    blocks: list[Block] = []
    for spine_index, (idref, _linear) in enumerate(book.get_spine()):
        item = book.get_item_with_id(idref)
        if item is None:
            msg = f"spine idref {idref!r} not in manifest of {epub_path}"
            raise ValueError(msg)
        blocks.extend(
            parse_blocks(
                item.get_content().decode("utf-8"), spine_index, item.get_name()
            )
        )
    return blocks
