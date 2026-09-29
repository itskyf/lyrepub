"""Sentence fragments preserve authored text and inline semantics."""

from dataclasses import replace
from urllib.parse import unquote
from xml.etree import ElementTree as ET

import pytest
from defusedxml import ElementTree

from lyrepub.epub_text import Block, materialize_sentence_targets, parse_blocks

_XHTML = "http://www.w3.org/1999/xhtml"
_PREFIX = "lyrepub-sentence-"


def _document(body: str) -> str:
    return (
        f'<html xmlns="{_XHTML}" xml:lang="vi"><head><title>Test</title></head>'
        f"<body>{body}</body></html>"
    )


def _targets(
    block: Block, sentences: list[str]
) -> list[tuple[Block, int, int, int, str]]:
    targets = []
    cursor = 0
    for index, text in enumerate(sentences):
        start = block.text.index(text, cursor)
        cursor = start + len(text)
        targets.append((block, index, start, cursor, text))
    return targets


def _semantics(xhtml: str | bytes) -> list[tuple[str, tuple]]:
    """Compare each authored character and break with its semantic ancestry."""
    result = []

    def visit(element: ET.Element, ancestry: tuple) -> None:
        generated = element.get("id", "").startswith(_PREFIX)
        attributes = tuple(
            sorted(
                (key, value)
                for key, value in element.attrib.items()
                if not (key == "id" and generated)
            )
        )
        context = ancestry
        if not (element.tag == f"{{{_XHTML}}}span" and generated and not attributes):
            context = (*ancestry, (element.tag, attributes))
        if element.tag == f"{{{_XHTML}}}br":
            result.append(("<br/>", context))
        result.extend((character, context) for character in element.text or "")
        for child in element:
            visit(child, context)
            result.extend((character, context) for character in child.tail or "")

    visit(ElementTree.fromstring(xhtml), ())
    return result


def _assert_targets(
    content: bytes, hrefs: list[str], targets: list[tuple[Block, int, int, int, str]]
) -> None:
    root = ElementTree.fromstring(content)
    ids = [element.get("id") for element in root.iter() if element.get("id")]
    assert len(ids) == len(set(ids))
    by_id = {element.get("id"): element for element in root.iter()}
    blocks = parse_blocks(content, 2, "Text/ch.xhtml", linear=True)
    for href, (source, _, _, _, text) in zip(hrefs, targets, strict=True):
        fragment = unquote(href.split("#")[1])
        assert fragment in by_id
        resolved = [block for block in blocks if block.element_id == fragment]
        assert [(block.text, block.lang) for block in resolved] == [(text, source.lang)]


def test_inline_whitespace_breaks_language_and_headings() -> None:
    xhtml = _document(
        '<h2 id="chapter" role="doc-subtitle">Chương một.</h2>'
        '<p> \nÔng <em class="voice" title="Giọng">Nguyễn đến. Câu</em> \t'
        " tiếp có<br/>ngắt dòng.\u00a0Cuối.  </p>"
        '<section xml:lang="en"><h3>English heading.</h3><p>English.</p></section>'
        '<p lang="fr">Bonjour.</p>'
    )
    blocks = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)
    sentences = [
        ["Chương một."],
        ["Ông Nguyễn đến.", "Câu tiếp có ngắt dòng.", "Cuối."],
        ["English heading."],
        ["English."],
        ["Bonjour."],
    ]
    targets = [
        target
        for block, texts in zip(blocks, sentences, strict=True)
        for target in _targets(block, texts)
    ]
    content, hrefs = materialize_sentence_targets(xhtml, targets)
    assert _semantics(content) == _semantics(xhtml)
    assert " ".join(
        block.text for block in parse_blocks(content, 2, "Text/ch.xhtml", linear=True)
    ) == " ".join(block.text for block in blocks)
    _assert_targets(content, hrefs, targets)
    assert hrefs[0] == "Text/ch.xhtml#chapter"
    root = ElementTree.fromstring(content)
    assert root.find(f".//{{{_XHTML}}}h2").get("id") == "chapter"
    assert root.find(f".//{{{_XHTML}}}h3").get("id") == "lyrepub-sentence-2-2-0"
    assert len(root.findall(f".//{{{_XHTML}}}br")) == 1
    assert materialize_sentence_targets(xhtml, targets) == (content, hrefs)
    reversed_content, reversed_hrefs = materialize_sentence_targets(
        xhtml, targets[::-1]
    )
    assert reversed_content == content
    assert reversed_hrefs == hrefs[::-1]


def test_exact_inline_element_and_authored_owner_id() -> None:
    xhtml = _document(
        '<p id="paragraph">First. <em title="emphasis">Second.</em> Third.</p>'
    )
    block = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)[0]
    targets = _targets(block, ["First.", "Second.", "Third."])
    content, hrefs = materialize_sentence_targets(xhtml, targets)
    root = ElementTree.fromstring(content)
    assert root.find(f".//{{{_XHTML}}}p").get("id") == "paragraph"
    emphasis = root.find(f".//{{{_XHTML}}}em")
    assert emphasis.attrib == {"title": "emphasis", "id": "lyrepub-sentence-2-0-1"}
    assert len(emphasis) == 0
    assert _semantics(content) == _semantics(xhtml)
    _assert_targets(content, hrefs, targets)


def test_original_locations_survive_nested_owner_runs() -> None:
    xhtml = _document(
        '<section>Before.<p id="nested">Nested.</p>After.</section>'
        '<p>Xin <span xml:lang="fr" id="french">bonjour</span> nhé.</p>'
    )
    blocks = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)
    assert [block.run_index for block in blocks[:3]] == [0, 0, 1]
    targets = [target for block in blocks for target in _targets(block, [block.text])]
    content, hrefs = materialize_sentence_targets(xhtml, targets)
    assert _semantics(content) == _semantics(xhtml)
    _assert_targets(content, hrefs, targets)
    assert hrefs[1] == "Text/ch.xhtml#nested"
    assert hrefs[4] == "Text/ch.xhtml#french"


def test_unicode_is_not_normalized() -> None:
    xhtml = '<?xml version="1.0" encoding="UTF-16"?>' + _document("<p>Á. Á.</p>")
    source = xhtml.encode("utf-16")
    block = parse_blocks(source, 2, "Text/ch.xhtml", linear=True)[0]
    targets = _targets(block, ["Á.", "Á."])
    content, hrefs = materialize_sentence_targets(source, targets)
    assert _semantics(content) == _semantics(source)
    _assert_targets(content, hrefs, targets)


@pytest.mark.parametrize(
    ("index", "start", "end", "text"),
    [
        (-1, 0, 4, "One."),
        (0, -1, 4, "One."),
        (0, 0, 0, ""),
        (0, 0, 10, "One. Two."),
        (0, 0, 4, "Drift"),
        (0, 0.0, 4, "One."),
        (0, 4, 5, " "),
    ],
)
def test_invalid_ranges_fail(index: int, start: int, end: int, text: str) -> None:
    xhtml = _document("<p>One. Two.</p>")
    block = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)[0]
    with pytest.raises(ValueError, match="invalid sentence range"):
        materialize_sentence_targets(xhtml, [(block, index, start, end, text)])


@pytest.mark.parametrize(
    "change",
    [
        {"text": "Changed."},
        {"element_path": (1, 99)},
        {"run_index": 1},
        {"href": "other.xhtml"},
        {"spine_index": 3},
        {"lang": "en"},
    ],
)
def test_drift_and_unresolvable_locations_fail(change: dict) -> None:
    xhtml = _document("<p>One.</p><p>Two.</p>")
    first, second = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)
    with pytest.raises(ValueError, match="unresolvable block location or source drift"):
        materialize_sentence_targets(
            xhtml,
            [(first, 0, 0, 4, "One."), (replace(second, **change), 0, 0, 4, "Two.")],
        )


def test_overlap_duplicate_identity_and_ids_fail() -> None:
    xhtml = _document("<p>One. Two.</p>")
    block = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)[0]
    with pytest.raises(ValueError, match="overlapping sentence ranges"):
        materialize_sentence_targets(
            xhtml, [(block, 0, 0, 4, "One."), (block, 1, 0, 9, "One. Two.")]
        )
    with pytest.raises(ValueError, match="duplicate sentence identity"):
        materialize_sentence_targets(
            xhtml, [(block, 0, 0, 4, "One."), (block, 0, 5, 9, "Two.")]
        )
    collision = _document('<p>One.</p><p id="lyrepub-sentence-2-0-0">Other.</p>')
    block = parse_blocks(collision, 2, "Text/ch.xhtml", linear=True)[0]
    with pytest.raises(ValueError, match="XHTML ID collision"):
        materialize_sentence_targets(collision, [(block, 0, 0, 4, "One.")])
    duplicates = _document('<p id="same">One.</p><p id="same">Other.</p>')
    block = parse_blocks(duplicates, 2, "Text/ch.xhtml", linear=True)[0]
    with pytest.raises(ValueError, match="duplicate XHTML IDs"):
        materialize_sentence_targets(duplicates, [(block, 0, 0, 4, "One.")])


def test_malformed_xhtml_and_empty_targets_fail() -> None:
    xhtml = _document("<p>One.</p>")
    block = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)[0]
    with pytest.raises(ValueError, match="invalid XHTML"):
        materialize_sentence_targets("<broken", [(block, 0, 0, 4, "One.")])
    with pytest.raises(ValueError, match="at least one sentence target"):
        materialize_sentence_targets(xhtml, [])
