"""Tests for EPUB text-block extraction."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

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


def _content_opf() -> bytes:
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
                "media-type": "application/xhtml+xml",
            },
        )
    spine = ET.SubElement(package, "spine")
    for idref in ("ch0", "ch2", "ch1"):
        ET.SubElement(spine, "itemref", {"idref": idref})
    return ET.tostring(package, encoding="utf-8", xml_declaration=True)


def _write_minimal_epub(path: Path, documents: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        archive.writestr("META-INF/container.xml", _container_xml())
        archive.writestr("OEBPS/content.opf", _content_opf())
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
        '<svg><image href="pic.png"/></svg>'
        "<p>   Khoảng    trắng    nhiều. </p>"
        "</section></body></html>"
    )

    blocks = parse_blocks(xhtml, spine_index=3, href="Text/ch1.xhtml")

    assert [b.text for b in blocks] == [
        "Chương một & những điều",
        "Ông Nguyễn Huy Tưởng… đi 1 bộ.",
        "Đoạn bọc trong div.",
        "Khoảng trắng nhiều.",
    ]
    assert [b.block_index for b in blocks] == [0, 1, 2, 3]
    assert all(b.spine_index == 3 and b.href == "Text/ch1.xhtml" for b in blocks)


def test_extract_blocks_preserves_spine_order(tmp_path: Path) -> None:
    documents = {
        "ch0.xhtml": "<p>Trang một — \u201cdấu thoại\u201d.</p>",
        "ch1.xhtml": "<html><body><p>Ba</p></body></html>",
        "ch2.xhtml": "<html><body><p>Hai &amp; demi</p></body></html>",
    }
    epub_path = tmp_path / "minimal.epub"
    _write_minimal_epub(epub_path, documents)

    blocks = extract_blocks(epub_path)

    assert [(b.spine_index, b.href, b.text) for b in blocks] == [
        (0, "ch0.xhtml", "Trang một — \u201cdấu thoại\u201d."),
        (1, "ch2.xhtml", "Hai & demi"),
        (2, "ch1.xhtml", "Ba"),
    ]
