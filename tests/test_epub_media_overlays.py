"""Synthetic EPUB Media Overlay publication checks."""

from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest
from defusedxml import ElementTree as ET

from lyrepub.epub_media_overlays import Timing, publish_media_overlays

_OPF = "http://www.idpf.org/2007/opf"
_SMIL = "http://www.w3.org/ns/SMIL"
_DC = "http://purl.org/dc/elements/1.1/"


def _source(path: Path) -> dict[str, bytes]:
    files = {
        "mimetype": b"application/epub+zip",
        "META-INF/container.xml": (
            b'<?xml version="1.0"?>'
            b'<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
            b'version="1.0"><rootfiles><rootfile full-path="OEBPS/package.opf" '
            b'media-type="application/oebps-package+xml"/></rootfiles></container>'
        ),
        "OEBPS/package.opf": f"""<?xml version="1.0"?>
<package xmlns="{_OPF}" version="3.0" unique-identifier="uid">
<metadata xmlns:dc="{_DC}">
<dc:identifier id="uid">test</dc:identifier><dc:title>Test</dc:title>
<dc:language>vi</dc:language>
<meta property="dcterms:modified">2026-09-27T00:00:00Z</meta></metadata>
<manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="style" href="style.css" media-type="text/css"/>
<item id="two" href="two.xhtml" media-type="application/xhtml+xml"/>
<item id="one" href="one.xhtml" media-type="application/xhtml+xml"/>
</manifest><spine><itemref idref="two"/><itemref idref="one"/></spine>
</package>""".encode(),
        "OEBPS/nav.xhtml": (
            b'<html xmlns="http://www.w3.org/1999/xhtml" '
            b'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Navigation'
            b'</title></head><body><nav epub:type="toc"><ol><li>'
            b'<a href="two.xhtml">Two</a></li><li><a href="one.xhtml">One</a>'
            b"</li></ol></nav></body></html>"
        ),
        "OEBPS/two.xhtml": (
            b'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi">'
            b'<head><title>Two</title><link rel="stylesheet" href="style.css"/>'
            b'</head><body><p id="first">First.</p><p id="second">Second.</p>'
            b'<p id="untimed">Untimed.</p>'
            b"</body></html>"
        ),
        "OEBPS/one.xhtml": (
            b'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi">'
            b'<head><title>One</title></head><body><p id="last">Last.</p>'
            b"</body></html>"
        ),
        "OEBPS/style.css": b"p { color: black; }",
    }
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", files["mimetype"], compress_type=ZIP_STORED)
        for name, data in files.items():
            if name != "mimetype":
                archive.writestr(name, data)
    return files


def _timings() -> list[Timing]:
    return [
        Timing("one.xhtml#last", "audio/tone.mp3", 0.3, 0.4),
        Timing("two.xhtml#second", "audio/tone.mp3", 0.2, 0.3),
        Timing("two.xhtml#first", "audio/tone.mp3", 0.0, 0.2),
    ]


def test_publish_orders_and_preserves(tmp_path: Path) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "output.epub"
    original = _source(source)
    audio = Path(__file__).with_name("tone.mp3")
    publish_media_overlays(source, output, _timings(), {"audio/tone.mp3": audio})

    with ZipFile(output) as archive:
        for name, data in original.items():
            if name != "OEBPS/package.opf":
                assert archive.read(name) == data
        assert archive.read("OEBPS/audio/tone.mp3") == audio.read_bytes()
        opf = ET.fromstring(archive.read("OEBPS/package.opf"))
        ns = {"p": _OPF}
        manifest = {
            item.get("id"): item for item in opf.findall("p:manifest/p:item", ns)
        }
        assert [item.get("idref") for item in opf.findall("p:spine/p:itemref", ns)] == [
            "two",
            "one",
        ]
        assert manifest["nav"].get("properties") == "nav"
        assert manifest["lyrepub-audio-0"].get("media-type") == "audio/mpeg"
        assert manifest["two"].get("media-overlay") == "lyrepub-smil-0"
        assert manifest["one"].get("media-overlay") == "lyrepub-smil-1"
        assert manifest["lyrepub-smil-0"].get("media-type") == "application/smil+xml"
        metas = {
            (meta.get("refines"), meta.get("property")): meta.text
            for meta in opf.findall("p:metadata/p:meta", ns)
        }
        assert metas[("#lyrepub-smil-0", "media:duration")] == "0.3s"
        assert metas[("#lyrepub-smil-1", "media:duration")] == "0.1s"
        assert metas[(None, "media:duration")] == "0.4s"
        first = ET.fromstring(archive.read("OEBPS/two.smil"))
        second = ET.fromstring(archive.read("OEBPS/one.smil"))
        assert first.tag == f"{{{_SMIL}}}smil"
        pars = first.findall(f"{{{_SMIL}}}body/{{{_SMIL}}}par")
        assert [p.find(f"{{{_SMIL}}}text").get("src") for p in pars] == [
            "two.xhtml#first",
            "two.xhtml#second",
        ]
        assert [
            (
                p.find(f"{{{_SMIL}}}audio").get("src"),
                p.find(f"{{{_SMIL}}}audio").get("clipBegin"),
                p.find(f"{{{_SMIL}}}audio").get("clipEnd"),
            )
            for p in pars
        ] == [
            ("audio/tone.mp3", "0.0s", "0.2s"),
            ("audio/tone.mp3", "0.2s", "0.3s"),
        ]
        assert (
            second.find(f"{{{_SMIL}}}body/{{{_SMIL}}}par/{{{_SMIL}}}text").get("src")
            == "one.xhtml#last"
        )


@pytest.mark.parametrize(
    ("timing", "audio_name", "message"),
    [
        (
            Timing("two.xhtml#missing", "audio/tone.mp3", 0, 0.1),
            "tone.mp3",
            "unresolvable XHTML target",
        ),
        (
            Timing("two.xhtml#first", "audio/tone.mp3", -1, 0.1),
            "tone.mp3",
            "invalid clip times",
        ),
        (
            Timing("two.xhtml#first", "audio/tone.mp3", 1, 1),
            "tone.mp3",
            "invalid clip times",
        ),
        (
            Timing("two.xhtml#first", "audio/tone.mp3", float("nan"), 1),
            "tone.mp3",
            "invalid clip times",
        ),
        (
            Timing("two.xhtml#first", "audio/tone.mp3", 0, float("inf")),
            "tone.mp3",
            "invalid clip times",
        ),
        (
            Timing("two.xhtml#first", "audio/missing.mp3", 0, 0.1),
            "absent.mp3",
            "missing audio file",
        ),
        (
            Timing("two.xhtml#first", "audio/tone.wav", 0, 0.1),
            "tone.mp3",
            "unsupported EPUB",
        ),
        (
            Timing("two.xhtml#first", "audio/tone.m4a", 0, 0.1),
            "tone.mp3",
            "audio content",
        ),
        (
            Timing("nav.xhtml#x", "audio/tone.mp3", 0, 0.1),
            "tone.mp3",
            "unresolvable XHTML target",
        ),
    ],
)
def test_invalid_inputs(
    tmp_path: Path, timing: Timing, audio_name: str, message: str
) -> None:
    source = tmp_path / "source.epub"
    _source(source)
    audio = Path(__file__).with_name(audio_name)
    with pytest.raises(ValueError, match=message):
        publish_media_overlays(
            source, tmp_path / "out.epub", [timing], {timing.audio_href: audio}
        )


def test_submillisecond_clip_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.epub"
    output = tmp_path / "output.epub"
    _source(source)
    timing = Timing("two.xhtml#first", "audio/tone.mp3", 0.0001, 0.0002)
    audio = Path(__file__).with_name("tone.mp3")
    with pytest.raises(ValueError, match="EPUBCheck timing resolution"):
        publish_media_overlays(source, output, [timing], {timing.audio_href: audio})
    assert not output.exists()
