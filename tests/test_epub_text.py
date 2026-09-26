"""Tests for EPUB text-block extraction."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from lyrepub.epub_text import extract_blocks, parse_blocks

_OPF_NS = "http://www.idpf.org/2007/opf"
"""OPF namespace URI; an identifier, not a link to resolve."""


def _container_xml() -> bytes:
    root = ET.Element(
        "container",
        {"version": "1.0", "xmlns": "urn:oasis:names:tc:opendocument:xmlns:container"},
    )
    rootfiles = ET.SubElement(root, "rootfiles")
    ET.SubElement(
        rootfiles,
        "rootfile",
        {
            "full-path": "OEBPS/content.opf",
            "media-type": "application/oebps-package+xml",
        },
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _content_opf(
    spine_ids: tuple[str, ...] = ("ch0", "ch2", "ch1"),
    media_types: dict[str, str] | None = None,
    non_linear_id: str | None = None,
) -> bytes:
    package = ET.Element(
        "package",
        {
            "version": "3.0",
            "unique-identifier": "uid",
            "xmlns": _OPF_NS,
        },
    )
    metadata = ET.SubElement(
        package, "metadata", {"xmlns:dc": "http://purl.org/dc/elements/1.1/"}
    )
    ET.SubElement(metadata, "dc:identifier", {"id": "uid"}).text = "test-epub"
    ET.SubElement(metadata, "dc:title").text = "Test"
    ET.SubElement(metadata, "dc:language").text = "vi"
    manifest = ET.SubElement(package, "manifest")
    for item_id in ("ch0", "ch1", "ch2"):
        ET.SubElement(
            manifest,
            "item",
            {
                "id": item_id,
                "href": f"{item_id}.xhtml",
                "media-type": (media_types or {}).get(item_id, "application/xhtml+xml"),
            },
        )
    spine = ET.SubElement(package, "spine")
    for idref in spine_ids:
        attrs = {"idref": idref}
        if idref == non_linear_id:
            attrs["linear"] = "no"
        ET.SubElement(spine, "itemref", attrs)
    return ET.tostring(package, encoding="utf-8", xml_declaration=True)


def _write_minimal_epub(
    path: Path, documents: dict[str, str | bytes], opf: bytes | None = None
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        archive.writestr("META-INF/container.xml", _container_xml())
        archive.writestr("OEBPS/content.opf", opf or _content_opf())
        for name, body in documents.items():
            archive.writestr(f"OEBPS/{name}", body)


def test_parse_blocks_inline_entities_and_skips() -> None:
    xhtml = (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Skip me</title></head>'
        "<body><section>"
        "<h2>Chương một &amp; những điều</h2>"
        "<p>Ông <em>Nguyễn</em> Huy Tưởng&#8230; đi <sup>1</sup> bộ.</p>"
        "<div><p>Đoạn bọc trong div.</p></div>"
        '<svg xmlns="http://www.w3.org/2000/svg"><title>Image label</title>'
        '<image href="pic.png"/></svg>'
        "<p>   Khoảng    trắng    nhiều. </p>"
        "</section></body></html>"
    )

    blocks = parse_blocks(xhtml, spine_index=3, href="Text/ch1.xhtml", linear=True)

    assert [b.text for b in blocks] == [
        "Chương một & những điều",
        "Ông Nguyễn Huy Tưởng… đi 1 bộ.",
        "Đoạn bọc trong div.",
        "Khoảng trắng nhiều.",
    ]
    assert [b.block_index for b in blocks] == [0, 1, 2, 3]
    assert all(b.spine_index == 3 and b.href == "Text/ch1.xhtml" for b in blocks)


def test_line_break_separates_readable_text() -> None:
    xhtml = (
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Test</title>'
        "</head><body><p>A<br/>B</p></body></html>"
    )

    assert [b.text for b in parse_blocks(xhtml, 0, "test.xhtml", linear=True)] == [
        "A B"
    ]


def test_nested_text_and_source_semantics() -> None:
    xhtml = (
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="vi">'
        "<head><title>Test</title></head><body>"
        '<section epub:type="chapter">Lời đầu '
        '<p id="source-id" role="doc-introduction">Một <em>đoạn</em>.</p>'
        'Lời giữa <div xml:lang="en"><p>English.</p></div> Lời cuối'
        '</section><p>Xin <span xml:lang="fr" id="french">bonjour</span> nhé.</p>'
        "</body></html>"
    )

    blocks = parse_blocks(xhtml, 2, "Text/test.xhtml", linear=True)

    assert [block.text for block in blocks] == [
        "Lời đầu",
        "Một đoạn.",
        "Lời giữa",
        "English.",
        "Lời cuối",
        "Xin",
        "bonjour",
        "nhé.",
    ]
    assert [(b.element_path, b.run_index) for b in blocks] == [
        ((1, 0), 0),
        ((1, 0, 0), 0),
        ((1, 0), 1),
        ((1, 0, 1, 0), 0),
        ((1, 0), 2),
        ((1, 1), 0),
        ((1, 1, 0), 0),
        ((1, 1), 1),
    ]
    assert [b.lang for b in blocks] == ["vi", "vi", "vi", "en", "vi", "vi", "fr", "vi"]
    assert blocks[0].epub_type == "chapter"
    assert (blocks[1].element_id, blocks[1].tag, blocks[1].role) == (
        "source-id",
        "p",
        "doc-introduction",
    )
    assert blocks[6].element_id == "french"
    assert blocks[2].element_id is None


def test_extract_blocks_preserves_spine_order(tmp_path: Path) -> None:
    documents = {
        "ch0.xhtml": (
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Cover</title>'
            '</head><body><img src="cover.jpg" alt="Cover"/></body></html>'
        ),
        "ch1.xhtml": (
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Last</title>'
            "</head><body><p>Ba</p></body></html>"
        ),
        "ch2.xhtml": (
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Middle</title>'
            "</head><body><p>Hai &amp; demi</p></body></html>"
        ),
    }
    epub_path = tmp_path / "minimal.epub"
    _write_minimal_epub(epub_path, documents, _content_opf(non_linear_id="ch2"))

    blocks = extract_blocks(epub_path)

    assert [(b.spine_index, b.href, b.text) for b in blocks] == [
        (1, "ch2.xhtml", "Hai & demi"),
        (2, "ch1.xhtml", "Ba"),
    ]
    assert [b.block_index for b in blocks] == [0, 0]
    assert [b.linear for b in blocks] == [False, True]
    assert [b.element_path for b in blocks] == [(1, 0), (1, 0)]


def test_extract_blocks_accepts_utf16_xhtml(tmp_path: Path) -> None:
    xhtml = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Test</title>'
        "</head><body><p>Tiếng Việt</p></body></html>"
    ).encode("utf-16")
    epub_path = tmp_path / "utf16.epub"
    _write_minimal_epub(epub_path, {"ch0.xhtml": xhtml}, _content_opf(("ch0",)))

    blocks = extract_blocks(epub_path)

    assert [(block.text, block.linear) for block in blocks] == [("Tiếng Việt", True)]


@pytest.mark.parametrize(
    "xhtml",
    [
        '<html xmlns="http://www.w3.org/1999/xhtml"><head/><body><p>Oops</body></html>',
        "<html><head/><body><p>No namespace</p></body></html>",
        '<html xmlns="http://www.w3.org/1999/xhtml"><head/><p>No body</p></html>',
    ],
)
def test_invalid_xhtml_fails(xhtml: str) -> None:
    with pytest.raises(ValueError, match="invalid XHTML"):
        parse_blocks(xhtml, 0, "bad.xhtml", linear=True)


def test_invalid_spine_reference_fails(tmp_path: Path) -> None:
    epub_path = tmp_path / "missing-idref.epub"
    _write_minimal_epub(epub_path, {}, _content_opf(("missing",)))
    with pytest.raises(ValueError, match="spine idref 'missing' not in manifest"):
        extract_blocks(epub_path)


def test_non_xhtml_spine_item_fails(tmp_path: Path) -> None:
    epub_path = tmp_path / "wrong-media-type.epub"
    _write_minimal_epub(
        epub_path,
        {"ch0.xhtml": "plain text"},
        _content_opf(("ch0",), {"ch0": "text/plain"}),
    )
    with pytest.raises(ValueError, match="spine idref 'ch0' is not XHTML"):
        extract_blocks(epub_path)


def test_missing_manifest_content_fails(tmp_path: Path) -> None:
    epub_path = tmp_path / "missing-content.epub"
    _write_minimal_epub(epub_path, {}, _content_opf(("ch0",)))
    with pytest.raises(
        ValueError, match="spine idref 'ch0' has empty or missing content"
    ):
        extract_blocks(epub_path)
