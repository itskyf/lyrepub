"""Final-publication paths preserve source text and experimental evidence."""

import json
from pathlib import Path
from xml.etree.ElementTree import tostring
from zipfile import ZipFile

import pytest
from defusedxml import ElementTree as ET
from test_media_overlays import _source

from lyrepub.epub_text import Block
from scripts import publication
from scripts import tts_publication as tts
from scripts.publication import NS, XHTML, repair, verify_alignment
from scripts.tts_synthesis import sha256


def _tts_source(path: Path) -> None:
    files = _source(path)
    package = (
        files["OEBPS/package.opf"]
        .decode()
        .replace(
            "</manifest>",
            '<item id="imgcv" href="cover.jpg" media-type="image/jpeg"/>'
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
            "</manifest>",
        )
    )
    files["OEBPS/package.opf"] = package.encode()
    files["OEBPS/cover.jpg"] = b"image"
    files["OEBPS/toc.ncx"] = (
        b'<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/">'
        b"<navMap><navPoint><navLabel><text>Chapter</text></navLabel>"
        b'<content src="two.xhtml"/></navPoint></navMap></ncx>'
    )
    files.pop("OEBPS/nav.xhtml")
    files["OEBPS/package.opf"] = files["OEBPS/package.opf"].replace(
        b'<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
        b'properties="nav" />',
        b"",
    )
    root = ET.fromstring(files["OEBPS/package.opf"])
    root.set("version", "2.0")
    metadata = root.find("p:metadata", NS)
    metadata.remove(metadata.find("p:meta[@property='dcterms:modified']", NS))
    files["OEBPS/package.opf"] = tostring(root)
    with ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_full_tts_publication_and_source_preservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "tts"
    _tts_source(source)
    digest = sha256(source)
    monkeypatch.setattr(tts, "segment_sentences", lambda text: [text])
    tts.prepare(source, output)
    monkeypatch.setattr(tts, "ogg_duration", lambda _p: publication.Decimal("1.25"))
    records = tts.load_records(output)
    assert len(records) == 4
    for record in records:
        sentence = record["sentences"][0]
        assert sentence["tts_input"] == sentence["source_text"]
        audio = f"{record['key']}.opus"
        (output / audio).write_bytes(b"opus")
        sentence.update(packaged_audio=audio, clip_begin="0.000", clip_end="1.25")
        record["status"] = "ok"
    tts.save_records(output, records)
    tts.publish(source, output)
    assert sha256(source) == digest
    with ZipFile(output / "final.epub") as archive:
        assert archive.namelist()[0] == "mimetype"
        assert "OEBPS/toc.ncx" not in archive.namelist()
        nav = ET.fromstring(archive.read("OEBPS/nav.xhtml"))
        assert nav.find("x:body/x:nav", NS).get("role") == "doc-toc"
        for record in records:
            sentence = record["sentences"][0]
            root = ET.fromstring(archive.read("OEBPS/" + record["source"]["href"]))
            target = next(
                e for e in root.iter() if e.get("id") == record["source"]["element_id"]
            )
            assert "".join(target.itertext()) == sentence["source_text"]
        smil = ET.fromstring(archive.read("OEBPS/two.smil"))
        assert [a.get("clipEnd") for a in smil.findall(".//s:audio", NS)] == [
            "1.25s"
        ] * 3
        package = ET.fromstring(archive.read("OEBPS/package.opf"))
        modes = package.findall("p:metadata/p:meta[@property='schema:accessMode']", NS)
        assert {m.text for m in modes} == {"textual", "visual", "auditory"}
        assert "synchronizedAudioText" in [
            m.text
            for m in package.findall(
                "p:metadata/p:meta[@property='schema:accessibilityFeature']", NS
            )
        ]
    records[0]["sentences"][0]["source_text"] = "changed"
    tts.save_records(output, records)
    with pytest.raises(ValueError, match="source text drift"):
        tts.publish(source, output)


def test_tts_rejects_incomplete_coverage_and_synthesis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "tts"
    _tts_source(source)
    monkeypatch.setattr(tts, "segment_sentences", lambda text: [text])
    tts.prepare(source, output)
    records = tts.load_records(output)
    with pytest.raises(ValueError, match="incomplete synthesis"):
        tts.publish(source, output)
    tts.save_records(output, records[:-1])
    with pytest.raises(ValueError, match="cover source blocks exactly"):
        tts.publish(source, output)


def test_tts_preparation_retains_raw_frontend_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "tts"
    files = _source(source)
    text = "1/ Một. 2/ Hai."
    files["OEBPS/one.xhtml"] = (
        f'<html xmlns="{XHTML}"><head><title>One</title></head>'
        f"<body><p>{text}</p></body></html>"
    ).encode()
    with ZipFile(source, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    digest = sha256(source)
    monkeypatch.setattr(tts, "segment_sentences", lambda text: [text])
    tts.prepare(source, output)
    record = next(
        r for r in tts.load_records(output) if r["source"]["href"] == "one.xhtml"
    )
    assert record["raw_frontend"][0]["tts_input"] == text
    assert record["raw_frontend"][0]["source_text"] == text
    assert record["sentences"][0]["tts_input"] == "1, Một. 2, Hai."
    assert sha256(source) == digest


def test_repair_preserves_ids_inline_content_and_note_text(tmp_path: Path) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "final.epub"
    files = _source(source)
    files["OEBPS/two.xhtml"] = (
        f'<html xmlns="{XHTML}"><head><title/></head><body section="chapter">'
        '<h2 id="heading">II</h2><p id="sentence">Năm <em>1774</em> '
        '<a href="note:" title="1774 (chú thích của tác giả).">(2)</a>.</p>'
        '<img src="../Images/b1vz-bia-1.jpg" alt=""/>'
        '<img src="../Images/hero__section_12.jpg"/>'
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<image xmlns:xlink="http://www.w3.org/1999/xlink" '
        'xlink:href="../Images/cover_l.jpg"/></svg>'
        "</body></html>"
    ).encode()
    with ZipFile(source, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    digest = sha256(source)
    repair(source, output, "alignment")
    assert sha256(source) == digest
    with ZipFile(output) as archive:
        root = ET.fromstring(archive.read("OEBPS/two.xhtml"))
        sentence = root.find(".//x:p[@id='sentence']", NS)
        assert "".join(sentence.itertext()) == "Năm 1774 (2)."
        assert sentence.findtext("x:em", namespaces=NS) == "1774"
        assert root.find("x:body", NS).get("section") is None
        assert root.find(".//x:h1", NS).get("id") == "heading"
        note = root.find(".//x:aside", NS)
        assert note.findtext("x:p", namespaces=NS) == "1774 (chú thích của tác giả)."
        assert sentence.find("x:a", NS).get("href") == "#" + note.get("id")
        assert root.find(".//x:img", NS).get("alt") == (
            "Chân dung nhà văn Nguyễn Huy Tưởng."
        )
        svg = root.find(".//{http://www.w3.org/2000/svg}svg")
        assert svg.get("role") == "img"
        assert svg.get("aria-label").startswith("Test — ")
        back_cover = root.findtext(
            ".//x:div[@id='lyrepub-back-cover-text']/x:p", namespaces=NS
        )
        assert "chồng chất giữa những oan khiên" in back_cover
        assert "oan oan" not in back_cover
        assert "\u201cbách tính\u201d" in back_cover
        package = ET.fromstring(archive.read("OEBPS/package.opf"))
        assert "auditory" not in [
            m.text
            for m in package.findall(
                "p:metadata/p:meta[@property='schema:accessMode']", NS
            )
        ]
        assert "synchronizedAudioText" not in [
            m.text
            for m in package.findall(
                "p:metadata/p:meta[@property='schema:accessibilityFeature']", NS
            )
        ]
        sufficient = package.findall(
            "p:metadata/p:meta[@property='schema:accessModeSufficient']", NS
        )
        assert [m.text for m in sufficient] == ["textual"]
        summary = package.findtext(
            "p:metadata/p:meta[@property='schema:accessibilitySummary']",
            namespaces=NS,
        )
        assert "Back-cover image text is absent from the audiobook" in summary


def test_alignment_opus_keeps_exact_smil_timings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "alignment"
    files = _source(source)
    files["OEBPS/package.opf"] = files["OEBPS/package.opf"].replace(
        b"</manifest>",
        b'<item id="audio" href="Audio/track.mp3" media-type="audio/mpeg"/>'
        b'<item id="mo" href="two.smil" media-type="application/smil+xml"/>'
        b"</manifest>",
    )
    files["OEBPS/Audio/track.mp3"] = b"mp3"
    files["OEBPS/two.smil"] = (
        b'<smil xmlns="http://www.w3.org/ns/SMIL"><body><par>'
        b'<text src="two.xhtml#first"/><audio src="Audio/track.mp3" '
        b'clipBegin="0.000s" clipEnd="1.200s"/></par></body></smil>'
    )
    with ZipFile(source, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    digest = sha256(source)

    def transcode(command: list[str]) -> tuple[str, str]:
        Path(command[-1]).write_bytes(b"opus")
        return "", ""

    monkeypatch.setattr(publication, "run_tool", transcode)
    monkeypatch.setattr(
        publication, "ogg_duration", lambda _p: publication.Decimal("1.2")
    )
    publication.package_alignment(source, output)
    assert sha256(source) == digest
    with ZipFile(output / "final.epub") as archive:
        assert "OEBPS/Audio/track.mp3" not in archive.namelist()
        assert archive.read("OEBPS/Audio/track.opus") == b"opus"
        audio = ET.fromstring(archive.read("OEBPS/two.smil")).find(".//s:audio", NS)
        assert audio.attrib == {
            "src": "Audio/track.opus",
            "clipBegin": "0.000s",
            "clipEnd": "1.200s",
        }
        package = ET.fromstring(archive.read("OEBPS/package.opf"))
        assert (
            package.find("p:manifest/p:item[@id='audio']", NS).get("media-type")
            == "audio/ogg; codecs=opus"
        )
    monkeypatch.setattr(
        publication, "ogg_duration", lambda _p: publication.Decimal("1.1")
    )
    with pytest.raises(ValueError, match="exceeds packaged audio"):
        publication.package_alignment(source, output)


def test_alignment_report_mismatch_stops_before_publication(tmp_path: Path) -> None:
    frozen, regenerated = tmp_path / "frozen.json", tmp_path / "new.json"
    frozen.write_text(json.dumps({"totals": {"aligned": 1}}))
    regenerated.write_text(json.dumps({"totals": {"aligned": 2}}))
    with pytest.raises(ValueError, match="differs from frozen evidence"):
        verify_alignment(frozen, regenerated, tmp_path / "missing.epub")
    assert json.loads(frozen.read_text()) == {"totals": {"aligned": 1}}


def test_reviewed_dash_join_keeps_the_initial_dialogue_dash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.epub"
    _tts_source(source)
    text = "- Ta chỉ sợ các con không đủ sức - Rồi người vẫy tay. Sau."
    block = Block(
        text=text,
        spine_index=23,
        href="Text/24.html",
        block_index=37,
        linear=True,
        element_path=(1, 0),
        run_index=0,
        element_id=None,
        tag="p",
        lang="vi",
        epub_type=None,
        role=None,
    )
    monkeypatch.setattr(tts, "extract_blocks", lambda _p: [block])
    monkeypatch.setattr(
        tts,
        "segment_sentences",
        lambda _t: [
            "- Ta chỉ sợ các con không đủ sức",
            "-",
            "Rồi người vẫy tay.",
            "Sau.",
        ],
    )
    output = tmp_path / "tts"
    tts.prepare(source, output)
    record = tts.load_records(output)[0]
    sentences = record["sentences"]
    assert [s["source_text"] for s in sentences] == [
        "- Ta chỉ sợ các con không đủ sức",
        "- Rồi người vẫy tay.",
        "Sau.",
    ]
    for sentence in sentences:
        assert (
            text[sentence["source_start"] : sentence["source_end"]]
            == sentence["source_text"]
        )
    assert record["interventions"] == [
        "reviewed source-preserving punctuation boundary join"
    ]


def test_reviewed_initial_corrections_preserve_bronze_source(tmp_path: Path) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "corrected.epub"
    chapter_one = (
        f'<html xmlns="{XHTML}"><head><title>One</title></head><body>'
        "<p>Vừa bước vào tới cửa cung Thánh từ, vua đã sụp lạy:</p>"
        "<p>V</p><p>- Trình phụ hoàng.</p></body></html>"
    )
    chapter_twelve = (
        f'<html xmlns="{XHTML}"><head><title>Twelve</title></head><body>'
        '<p>"P hú quốc Cường binh sách" của Trần Hưng Đạo.</p>'
        '<p>"P</p><p>Lệnh vua ban khắp nước.</p></body></html>'
    )
    with ZipFile(source, "w") as archive:
        archive.writestr("OEBPS/Text/1.html", chapter_one)
        archive.writestr("OEBPS/Text/12.html", chapter_twelve)
    digest = sha256(source)
    publication.correct_tts_source(source, output)
    assert sha256(source) == digest
    with ZipFile(output) as archive:
        one = ET.fromstring(archive.read("OEBPS/Text/1.html"))
        twelve = ET.fromstring(archive.read("OEBPS/Text/12.html"))
        assert [p.text for p in one.findall("x:body/x:p", NS)] == [
            "Vừa bước vào tới cửa cung Thánh từ, vua đã sụp lạy:",
            "- Trình phụ hoàng.",
        ]
        assert [p.text for p in twelve.findall("x:body/x:p", NS)] == [
            '"Phú quốc Cường binh sách" của Trần Hưng Đạo.',
            "Lệnh vua ban khắp nước.",
        ]
