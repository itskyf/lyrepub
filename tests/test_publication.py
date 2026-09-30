"""Final-publication paths preserve source text and experimental evidence."""

import hashlib
import json
from pathlib import Path
from xml.etree.ElementTree import tostring
from zipfile import ZipFile

import pytest
from defusedxml import ElementTree
from test_media_overlays import _source

from lyrepub.epub_text import extract_blocks
from lyrepub.tts_text import join_sentence_boundary, map_sentence_inputs
from scripts import publication
from scripts.publication import NS, XHTML, repair, verify_alignment


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    root = ElementTree.fromstring(files["OEBPS/package.opf"])
    root.set("version", "2.0")
    metadata = root.find("p:metadata", NS)
    metadata.remove(metadata.find("p:meta[@property='dcterms:modified']", NS))
    files["OEBPS/package.opf"] = tostring(root)
    with ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_ncx_navigation_keeps_nested_order_labels_and_targets(tmp_path: Path) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "final.epub"
    _tts_source(source)
    with ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    files["OEBPS/toc.ncx"] = (
        b'<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap>'
        b'<navPoint><navLabel><text>Part I</text></navLabel><content src="one.xhtml"/>'
        b"<navPoint><navLabel><text>Chapter 1</text></navLabel>"
        b'<content src="one.xhtml#first"/>'
        b"<navPoint><navLabel><text>Section A</text></navLabel>"
        b'<content src="one.xhtml#second"/>'
        b"</navPoint></navPoint></navPoint>"
        b'<navPoint><navLabel><text>Part II</text></navLabel><content src="two.xhtml"/>'
        b"</navPoint></navMap></ncx>"
    )
    with ZipFile(source, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    repair(source, output, "tts")
    with ZipFile(output) as archive:
        nav = ElementTree.fromstring(archive.read("OEBPS/nav.xhtml"))
    top = nav.findall("x:body/x:nav/x:ol/x:li", NS)
    assert [
        (li.findtext("x:a", namespaces=NS), li.find("x:a", NS).get("href"))
        for li in top
    ] == [("Part I", "one.xhtml"), ("Part II", "two.xhtml")]
    chapter = top[0].find("x:ol/x:li", NS)
    assert (
        chapter.findtext("x:a", namespaces=NS),
        chapter.find("x:a", NS).get("href"),
    ) == ("Chapter 1", "one.xhtml#first")
    section = chapter.find("x:ol/x:li", NS)
    assert (
        section.findtext("x:a", namespaces=NS),
        section.find("x:a", NS).get("href"),
    ) == ("Section A", "one.xhtml#second")


def test_distribution_boilerplate_excluded_without_renumbering(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.epub"
    _tts_source(source)
    with ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    files["OEBPS/two.xhtml"] = (
        f'<html xmlns="{XHTML}"><head><title>Chapter</title></head><body>'
        '<div class="header">Thăng Long Nổi Giận</div>'
        '<div class="author">Hoàng Quốc Hải</div>'
        '<author><div class="author">www.dtv-ebook.com</div></author>'
        "<h4>Chương 1</h4><p>Subsequent narration.</p></body></html>"
    ).encode()
    with ZipFile(source, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    original = next(
        block
        for block in extract_blocks(source)
        if block.text == "Subsequent narration."
    )
    narrated = publication.narration_blocks(source)
    assert all(block.text not in publication.DISTRIBUTION_HEADER for block in narrated)
    selected = next(block for block in narrated if block.text == original.text)
    assert (selected.spine_index, selected.block_index) == (
        original.spine_index,
        original.block_index,
    )
    assert selected.element_path == original.element_path
    final = tmp_path / "final.epub"
    repair(source, final, "tts")
    with ZipFile(final) as archive:
        chapter = archive.read("OEBPS/two.xhtml")
        assert all(
            text.encode() not in chapter for text in publication.DISTRIBUTION_HEADER
        )
        assert b"Subsequent narration." in chapter


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
        root = ElementTree.fromstring(archive.read("OEBPS/two.xhtml"))
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
        package = ElementTree.fromstring(archive.read("OEBPS/package.opf"))
        assert "auditory" not in [
            m.text
            for m in package.findall(
                "p:metadata/p:meta[@property='schema:accessMode']", NS
            )
        ]
        assert "synchronizedAudioText" in [
            m.text
            for m in package.findall(
                "p:metadata/p:meta[@property='schema:accessibilityFeature']", NS
            )
        ]
        assert "alternativeText" in [
            m.text
            for m in package.findall(
                "p:metadata/p:meta[@property='schema:accessibilityFeature']", NS
            )
        ]
        sufficient = package.findall(
            "p:metadata/p:meta[@property='schema:accessModeSufficient']", NS
        )
        assert sufficient == []
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

    monkeypatch.setattr(
        publication,
        "encode_opus",
        lambda _s, target: (
            Path(target).write_bytes(b"opus"),
            publication.Decimal("1.2"),
        )[1],
    )
    publication.package_alignment(source, output / "final.epub", output / "work")
    assert sha256(source) == digest
    with ZipFile(output / "final.epub") as archive:
        assert "OEBPS/Audio/track.mp3" not in archive.namelist()
        assert archive.read("OEBPS/Audio/track.opus") == b"opus"
        audio = ElementTree.fromstring(archive.read("OEBPS/two.smil")).find(
            ".//s:audio", NS
        )
        assert audio.attrib == {
            "src": "Audio/track.opus",
            "clipBegin": "0.000s",
            "clipEnd": "1.200s",
        }
        package = ElementTree.fromstring(archive.read("OEBPS/package.opf"))
        assert (
            package.find("p:manifest/p:item[@id='audio']", NS).get("media-type")
            == "audio/ogg; codecs=opus"
        )
    monkeypatch.setattr(
        publication, "encode_opus", lambda _s, _target: publication.Decimal("1.1")
    )
    with pytest.raises(ValueError, match="exceeds packaged audio"):
        publication.package_alignment(source, output / "final.epub", output / "work")


def test_alignment_report_rejects_changed_smil_timing(tmp_path: Path) -> None:
    frozen, regenerated, epub = (
        tmp_path / "frozen.json",
        tmp_path / "new.json",
        tmp_path / "aligned.epub",
    )
    report = {
        "spans": [
            {
                "audio": {"start": 91.88, "end": 93.0, "track": 0},
                "spine": 0,
                "firstSentence": 0,
                "lastSentence": 0,
            }
        ],
        "spine": [{"href": "Text-section_2.html"}],
        "tracks": [{"name": "track.mp3"}],
    }
    frozen.write_text(json.dumps(report))
    regenerated.write_text(json.dumps(report))
    clips = [
        ("Text-section_2.html-s0", "91.88", "93.0"),
        ("Text-section_3.html-s1", "494.20", "495.0"),
        ("Text-section_4.html-s0", "1.54", "2.0"),
        ("Text-section_8.html-s183", "917.30", "918.0"),
    ]

    def write_smil(rows: list[tuple[str, str, str]]) -> None:
        with ZipFile(epub, "w") as archive:
            archive.writestr(
                "OEBPS/timing.smil",
                (
                    '<smil xmlns="http://www.w3.org/ns/SMIL"><body>'
                    + "".join(
                        f'<par id="{key}"><audio src="Audio/track.mp3" '
                        f'clipBegin="{start}s" clipEnd="{end}s"/></par>'
                        for key, start, end in rows
                    )
                    + "</body></smil>"
                ),
            )

    write_smil(clips)
    verify_alignment(frozen, regenerated, epub)
    clips[0] = (clips[0][0], "91.89", clips[0][2])
    write_smil(clips)
    with pytest.raises(ValueError, match="SMIL differs"):
        verify_alignment(frozen, regenerated, epub)


@pytest.mark.parametrize(
    "case",
    [
        (
            "A. B. C. D. E. F. G.) Sau.",
            ["A.", "B.", "C.", "D.", "E.", "F.", "G.", ")", "Sau."],
            6,
            7,
            ")",
            "G.)",
            (18, 21),
        ),
        (
            "- Ta chỉ sợ các con không đủ sức - Rồi người vẫy tay. Sau.",
            ["- Ta chỉ sợ các con không đủ sức", "-", "Rồi người vẫy tay.", "Sau."],
            1,
            2,
            "-",
            "- Rồi người vẫy tay.",
            (33, 53),
        ),
        (
            'Trước. Người nói. " Sau.',
            ["Trước.", "Người nói.", '"', "Sau."],
            1,
            2,
            '"',
            'Người nói. "',
            (7, 19),
        ),
    ],
)
def test_reviewed_boundary_joins_preserve_authored_offsets(
    case: tuple[str, list[str], int, int, str, str, tuple[int, int]],
) -> None:
    text, segments, left, right, punctuation, joined, offsets = case
    join_sentence_boundary(text, segments, left, right, punctuation)
    sentence = next(
        s
        for s in map_sentence_inputs(text, text, segments)
        if s["source_text"] == joined
    )
    assert (sentence["source_start"], sentence["source_end"]) == offsets
    assert text[offsets[0] : offsets[1]] == joined


def test_reviewed_initial_corrections_preserve_bronze_source(
    tmp_path: Path,
) -> None:
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
        one = ElementTree.fromstring(archive.read("OEBPS/Text/1.html"))
        twelve = ElementTree.fromstring(archive.read("OEBPS/Text/12.html"))
        assert [p.text for p in one.findall("x:body/x:p", NS)] == [
            "Vừa bước vào tới cửa cung Thánh từ, vua đã sụp lạy:",
            "- Trình phụ hoàng.",
        ]
        assert [p.text for p in twelve.findall("x:body/x:p", NS)] == [
            '"Phú quốc Cường binh sách" của Trần Hưng Đạo.',
            "Lệnh vua ban khắp nước.",
        ]


@pytest.mark.parametrize(
    "defect", ["missing-resource", "missing-paragraph", "ambiguous", "wrong"]
)
def test_reviewed_initial_correction_fails_closed(tmp_path: Path, defect: str) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "corrected.epub"
    first = [
        "Vừa bước vào tới cửa cung Thánh từ, vua đã sụp lạy:",
        "V",
        "- Trình phụ hoàng.",
    ]
    second = [
        '"P hú quốc Cường binh sách" của Trần Hưng Đạo.',
        '"P',
        "Lệnh vua ban khắp nước.",
    ]
    if defect == "missing-paragraph":
        second.pop(1)
    elif defect == "ambiguous":
        second.extend(second.copy())
    else:
        second[2] = "Unrelated narration."
    with ZipFile(source, "w") as archive:
        for name, paragraphs in (
            ("OEBPS/Text/1.html", first),
            ("OEBPS/Text/12.html", second),
        ):
            if defect == "missing-resource" and name.endswith("12.html"):
                continue
            archive.writestr(
                name,
                f'<html xmlns="{XHTML}"><body>'
                + "".join(f"<p>{p}</p>" for p in paragraphs)
                + "</body></html>",
            )
    with pytest.raises(ValueError, match="reviewed duplicate-initial"):
        publication.correct_tts_source(source, output)
    assert not output.exists()
