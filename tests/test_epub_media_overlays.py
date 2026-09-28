"""Synthetic EPUB Media Overlay publication checks."""

from datetime import UTC, datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_STORED, ZipFile

import pytest
from defusedxml import ElementTree

from lyrepub.epub_media_overlays import Timing, publish_media_overlays

_OPF = "http://www.idpf.org/2007/opf"
_SMIL = "http://www.w3.org/ns/SMIL"
_DC = "http://purl.org/dc/elements/1.1/"
_XHTML = "http://www.w3.org/1999/xhtml"


def _source(path: Path) -> dict[str, bytes]:
    container = Element(
        "container",
        {"version": "1.0", "xmlns": "urn:oasis:names:tc:opendocument:xmlns:container"},
    )
    SubElement(
        SubElement(container, "rootfiles"),
        "rootfile",
        {
            "full-path": "OEBPS/package.opf",
            "media-type": "application/oebps-package+xml",
        },
    )
    package = Element(
        "package", {"version": "3.0", "unique-identifier": "uid", "xmlns": _OPF}
    )
    metadata = SubElement(package, "metadata", {"xmlns:dc": _DC})
    SubElement(metadata, "dc:identifier", {"id": "uid"}).text = "test"
    SubElement(metadata, "dc:title").text = "Test"
    SubElement(metadata, "dc:language").text = "vi"
    SubElement(
        metadata, "meta", {"property": "dcterms:modified"}
    ).text = "2026-09-27T00:00:00Z"
    SubElement(
        metadata, "meta", {"property": "dcterms:modified", "refines": "#uid"}
    ).text = "2020-01-01T00:00:00Z"
    manifest = SubElement(package, "manifest")
    for item_id, href, media_type, properties in (
        ("nav", "nav.xhtml", "application/xhtml+xml", "nav"),
        ("style", "style.css", "text/css", ""),
        ("two", "two.xhtml", "application/xhtml+xml", ""),
        ("one", "one.xhtml", "application/xhtml+xml", ""),
    ):
        attrs = {"id": item_id, "href": href, "media-type": media_type}
        if properties:
            attrs["properties"] = properties
        SubElement(manifest, "item", attrs)
    spine = SubElement(package, "spine")
    for idref in ("two", "one"):
        SubElement(spine, "itemref", {"idref": idref})

    def xhtml(title: str) -> tuple[Element, Element]:
        root = Element("html", {"xmlns": _XHTML, "xml:lang": "vi"})
        head = SubElement(root, "head")
        SubElement(head, "title").text = title
        return root, SubElement(root, "body")

    nav, nav_body = xhtml("Navigation")
    nav.set("xmlns:epub", "http://www.idpf.org/2007/ops")
    nav_list = SubElement(SubElement(nav_body, "nav", {"epub:type": "toc"}), "ol")
    for href, label in (("two.xhtml", "Two"), ("one.xhtml", "One")):
        SubElement(SubElement(nav_list, "li"), "a", {"href": href}).text = label

    two, two_body = xhtml("Two")
    SubElement(two.find("head"), "link", {"rel": "stylesheet", "href": "style.css"})
    for element_id, sentence in (
        ("first", "First."),
        ("second", "Second."),
        ("untimed", "Untimed."),
    ):
        SubElement(two_body, "p", {"id": element_id}).text = sentence
    one, one_body = xhtml("One")
    SubElement(one_body, "p", {"id": "last"}).text = "Last."

    files = {
        "mimetype": b"application/epub+zip",
        "META-INF/container.xml": tostring(
            container, encoding="utf-8", xml_declaration=True
        ),
        "OEBPS/package.opf": tostring(package, encoding="utf-8", xml_declaration=True),
        "OEBPS/nav.xhtml": tostring(nav, encoding="utf-8", xml_declaration=True),
        "OEBPS/two.xhtml": tostring(two, encoding="utf-8", xml_declaration=True),
        "OEBPS/one.xhtml": tostring(one, encoding="utf-8", xml_declaration=True),
        "OEBPS/style.css": b"p { color: black; }",
    }
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", files["mimetype"], compress_type=ZIP_STORED)
        for name, content in files.items():
            if name != "mimetype":
                archive.writestr(name, content)
    return files


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    path = tmp_path / "tone.opus"
    path.write_bytes(b"opaque audio resource")
    return path


def _timings() -> list[Timing]:
    return [
        Timing("one.xhtml#last", "audio/tone.opus", 0.3, 0.4),
        Timing("two.xhtml#second", "audio/tone.opus", 0.2, 0.3),
        Timing("two.xhtml#first", "audio/tone.opus", 0.0, 0.2),
    ]


def test_publish_orders_and_preserves(tmp_path: Path, audio: Path) -> None:
    source, output = tmp_path / "source.epub", tmp_path / "output.epub"
    original = _source(source)
    before = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    publish_media_overlays(source, output, _timings(), {"audio/tone.opus": audio})
    after = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    with ZipFile(output) as archive:
        for name, content in original.items():
            if name != "OEBPS/package.opf":
                assert archive.read(name) == content
        assert archive.read("OEBPS/audio/tone.opus") == audio.read_bytes()
        opf = ElementTree.fromstring(archive.read("OEBPS/package.opf"))
        ns = {"p": _OPF}
        manifest = {
            item.get("id"): item for item in opf.findall("p:manifest/p:item", ns)
        }
        assert [item.get("idref") for item in opf.findall("p:spine/p:itemref", ns)] == [
            "two",
            "one",
        ]
        assert manifest["nav"].get("properties") == "nav"
        assert manifest["lyrepub-audio-0"].get("media-type") == (
            "audio/ogg; codecs=opus"
        )
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
        assert metas[("#uid", "dcterms:modified")] == "2020-01-01T00:00:00Z"
        modified = metas[(None, "dcterms:modified")]
        assert before <= modified <= after
        assert modified != "2026-09-27T00:00:00Z"
        first = ElementTree.fromstring(archive.read("OEBPS/two.smil"))
        second = ElementTree.fromstring(archive.read("OEBPS/one.smil"))
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
            ("audio/tone.opus", "0.0s", "0.2s"),
            ("audio/tone.opus", "0.2s", "0.3s"),
        ]
        assert (
            second.find(f"{{{_SMIL}}}body/{{{_SMIL}}}par/{{{_SMIL}}}text").get("src")
            == "one.xhtml#last"
        )


@pytest.mark.parametrize(
    ("timing", "audio_name", "message"),
    [
        (
            Timing("two.xhtml#missing", "audio/tone.opus", 0, 0.1),
            "tone.opus",
            "unresolvable XHTML target",
        ),
        (
            Timing("two.xhtml#first", "audio/tone.opus", 1, 1),
            "tone.opus",
            "invalid clip times",
        ),
        (
            Timing("two.xhtml#first", "audio/tone.opus", float("nan"), 1),
            "tone.opus",
            "invalid clip times",
        ),
        (
            Timing("two.xhtml#first", "audio/missing.opus", 0, 0.1),
            "missing.opus",
            "missing audio file",
        ),
        (
            Timing("two.xhtml#first", "audio/tone.wav", 0, 0.1),
            "tone.opus",
            "unsupported EPUB",
        ),
    ],
)
def test_invalid_inputs(
    tmp_path: Path, timing: Timing, audio_name: str, message: str
) -> None:
    source = tmp_path / "source.epub"
    _source(source)
    supplied = tmp_path / audio_name
    with pytest.raises(ValueError, match=message):
        publish_media_overlays(
            source, tmp_path / "out.epub", [timing], {timing.audio_href: supplied}
        )
