"""Deterministic checks for Issue #14 case and overlay bookkeeping."""

from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from defusedxml import ElementTree as DefusedET

from scripts.issue14_feasibility import (
    CASES,
    PREFIXES,
    XHTML,
    chunk_offsets,
    key,
    source_paragraph,
    xhtml_document,
)


def test_chunk_offsets_include_join_padding() -> None:
    assert set(CASES) == set(PREFIXES)
    assert chunk_offsets([100, 200, 300], [10, 20]) == [0, 110, 330]
    with pytest.raises(ValueError, match="one gap"):
        chunk_offsets([100, 200], [])


def test_excerpt_preserves_paragraph_and_target() -> None:
    paragraph = ET.Element(f"{{{XHTML}}}p", {"id": key(5, 9)})
    paragraph.text = "Phủ Chiêu Quốc "
    ET.SubElement(paragraph, f"{{{XHTML}}}em").text = "đẹp nhất"
    document = DefusedET.fromstring(xhtml_document("Đoạn dài", [paragraph]))
    target = document.find(f".//{{{XHTML}}}p")
    assert target is not None
    assert target.get("id") == "s5-b9"
    assert "".join(target.itertext()) == "Phủ Chiêu Quốc đẹp nhất"


def test_source_paragraph_resolves_block_path_without_changing_text(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.epub"
    with ZipFile(source, "w") as archive:
        archive.writestr(
            "OEBPS/Text/6.html",
            f'<html xmlns="{XHTML}"><head/><body><p>Trước.</p>'
            "<p>Phủ <em>Chiêu Quốc</em>.</p></body></html>",
        )
    record = {
        "key": "s5-b9",
        "source": {
            "href": "Text/6.html",
            "element_path": (1, 1),
            "element_id": None,
            "text": "Phủ Chiêu Quốc.",
        },
    }
    paragraph = source_paragraph(source, record)
    assert paragraph.get("id") == "s5-b9"
    assert "".join(paragraph.itertext()) == "Phủ Chiêu Quốc."
