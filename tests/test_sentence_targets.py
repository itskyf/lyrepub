"""Sentence fragments preserve authored text and inline semantics."""

from dataclasses import replace
from urllib.parse import unquote
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest
from defusedxml import ElementTree

from lyrepub.epub_text import Block, materialize_sentence_targets, parse_blocks

_XHTML = "http://www.w3.org/1999/xhtml"
_PREFIX = "lyrepub-sentence-"


def _document() -> tuple[Element, Element]:
    root = Element("html", {"xmlns": _XHTML, "xml:lang": "vi"})
    SubElement(SubElement(root, "head"), "title").text = "Test"
    return root, SubElement(root, "body")


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


def _semantics(xhtml: bytes) -> list[tuple[str, tuple]]:
    """Compare each authored character and break with its semantic ancestry."""
    result = []

    def visit(element: Element, ancestry: tuple) -> None:
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
    blocks = parse_blocks(content, 2, "Text/ch.xhtml", linear=True)
    for href, (source, _, _, _, text) in zip(hrefs, targets, strict=True):
        fragment = unquote(href.split("#")[1])
        resolved = [block for block in blocks if block.element_id == fragment]
        assert [(block.text, block.lang) for block in resolved] == [(text, source.lang)]


def test_inline_whitespace_breaks_language_headings_and_order() -> None:
    document, body = _document()
    SubElement(
        body, "h2", {"id": "chapter", "role": "doc-subtitle"}
    ).text = "Chương một."
    paragraph = SubElement(body, "p")
    paragraph.text = " \nÔng "
    emphasis = SubElement(paragraph, "em", {"class": "voice", "title": "Giọng"})
    emphasis.text = "Nguyễn đến. Câu"
    emphasis.tail = " \t tiếp có"
    SubElement(paragraph, "br").tail = "ngắt dòng.\u00a0Cuối.  "
    section = SubElement(body, "section", {"xml:lang": "en"})
    SubElement(section, "h3").text = "English heading."
    SubElement(section, "p").text = "English."
    xhtml = tostring(document)
    blocks = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)
    sentences = [
        ["Chương một."],
        ["Ông Nguyễn đến.", "Câu tiếp có ngắt dòng.", "Cuối."],
        ["English heading."],
        ["English."],
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
    reversed_content, reversed_hrefs = materialize_sentence_targets(
        xhtml, targets[::-1]
    )
    assert reversed_content == content
    assert reversed_hrefs == hrefs[::-1]


def test_exact_inline_element_and_authored_owner_id() -> None:
    document, body = _document()
    paragraph = SubElement(body, "p", {"id": "paragraph"})
    paragraph.text = "First. "
    emphasis = SubElement(paragraph, "em", {"title": "emphasis"})
    emphasis.text, emphasis.tail = "Second.", " Third."
    xhtml = tostring(document)
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
    document, body = _document()
    section = SubElement(body, "section")
    section.text = "Before."
    nested = SubElement(section, "p", {"id": "nested"})
    nested.text, nested.tail = "Nested.", "After."
    paragraph = SubElement(body, "p")
    paragraph.text = "Xin "
    french = SubElement(paragraph, "span", {"xml:lang": "fr", "id": "french"})
    french.text, french.tail = "bonjour", " nhé."
    xhtml = tostring(document)
    blocks = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)
    assert [block.run_index for block in blocks[:3]] == [0, 0, 1]
    targets = [target for block in blocks for target in _targets(block, [block.text])]
    content, hrefs = materialize_sentence_targets(xhtml, targets)
    assert _semantics(content) == _semantics(xhtml)
    _assert_targets(content, hrefs, targets)
    assert hrefs[1] == "Text/ch.xhtml#nested"
    assert hrefs[4] == "Text/ch.xhtml#french"


def test_invalid_ranges_and_source_drift_fail() -> None:
    document, body = _document()
    SubElement(body, "p").text = "One. Two."
    xhtml = tostring(document)
    block = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)[0]
    with pytest.raises(ValueError, match="invalid sentence range"):
        materialize_sentence_targets(xhtml, [(block, 0, 0, 10, "One. Two.")])
    with pytest.raises(ValueError, match="source text drift"):
        materialize_sentence_targets(xhtml, [(block, 0, 0, 4, "Changed.")])
    body[0].text = "Changed."
    with pytest.raises(ValueError, match="source drift"):
        materialize_sentence_targets(tostring(document), [(block, 0, 0, 4, "One.")])
    for changed in (replace(block, element_path=(1, 99)), replace(block, run_index=1)):
        with pytest.raises(
            ValueError, match="unresolvable block location or source drift"
        ):
            materialize_sentence_targets(xhtml, [(changed, 0, 0, 4, "One.")])


def test_overlap_and_duplicate_identity_fail() -> None:
    document, body = _document()
    SubElement(body, "p").text = "One. Two."
    xhtml = tostring(document)
    block = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)[0]
    with pytest.raises(ValueError, match="overlapping sentence ranges"):
        materialize_sentence_targets(
            xhtml, [(block, 0, 0, 4, "One."), (block, 1, 0, 9, "One. Two.")]
        )
    with pytest.raises(ValueError, match="duplicate sentence identity"):
        materialize_sentence_targets(
            xhtml, [(block, 0, 0, 4, "One."), (block, 0, 5, 9, "Two.")]
        )


def test_authored_and_generated_id_collisions_fail() -> None:
    document, body = _document()
    first = SubElement(body, "p")
    first.text = "One."
    other = SubElement(body, "p", {"id": "lyrepub-sentence-2-0-0"})
    other.text = "Other."
    xhtml = tostring(document)
    block = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)[0]
    with pytest.raises(ValueError, match="XHTML ID collision"):
        materialize_sentence_targets(xhtml, [(block, 0, 0, 4, "One.")])
    first.set("id", "same")
    other.set("id", "same")
    xhtml = tostring(document)
    block = parse_blocks(xhtml, 2, "Text/ch.xhtml", linear=True)[0]
    with pytest.raises(ValueError, match="duplicate XHTML IDs"):
        materialize_sentence_targets(xhtml, [(block, 0, 0, 4, "One.")])
