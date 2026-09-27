"""Deterministic checks for Issue #14 case and overlay bookkeeping."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from defusedxml import ElementTree as DefusedET

from scripts.issue14_feasibility import (
    OPF,
    PLAYBACK,
    SMIL,
    XHTML,
    key,
    publish,
    source_paragraph,
    xhtml_document,
)


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


def test_packaged_opus_bounds_and_duration_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.epub"
    source.write_bytes(b"source")
    output = tmp_path / "output"
    audio = output / "audio"
    audio.mkdir(parents=True)
    records = []
    for spine, block in PLAYBACK:
        case_key = key(spine, block)
        (audio / f"{case_key}.ogg").write_bytes(b"ogg")
        records.append({"key": case_key, "playback": True, "status": "ok"})
    (output / "cases.json").write_text(json.dumps(records))
    (output / "source.json").write_text(
        json.dumps({"sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    )
    monkeypatch.setattr(
        "scripts.issue14_feasibility.ogg_duration", lambda _: Decimal("1.250")
    )
    monkeypatch.setattr(
        "scripts.issue14_feasibility.source_paragraph",
        lambda _source, record: ET.Element(f"{{{XHTML}}}p", {"id": record["key"]}),
    )
    publish(output, source)
    with ZipFile(output / "feasibility.epub") as archive:
        package = DefusedET.fromstring(archive.read("EPUB/package.opf"))
        items = package.findall(f".//{{{OPF}}}item")
        audio_items = [i for i in items if i.get("href", "").endswith(".ogg")]
        assert len(audio_items) == len(PLAYBACK)
        assert all(i.get("media-type") == "audio/ogg; codecs=opus" for i in audio_items)
        durations = package.findall(f".//{{{OPF}}}meta[@property='media:duration']")
        assert {(m.get("refines"), m.text) for m in durations} == {
            (None, "7.500s"),
            ("#mo-s5", "3.750s"),
            ("#mo-s10", "3.750s"),
        }
        for name in ("s5", "s10"):
            smil = DefusedET.fromstring(archive.read(f"EPUB/Overlays/{name}.smil"))
            clips = smil.findall(f".//{{{SMIL}}}audio")
            assert len(clips) == 3
            assert all(
                c.get("clipBegin") == "0.000s" and c.get("clipEnd") == "1.250s"
                for c in clips
            )
