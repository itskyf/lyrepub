"""Repair the two source-specific publications without modifying evidence."""

import argparse
import json
import posixpath
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from defusedxml import ElementTree as ET

from scripts.issue14_feasibility import ogg_duration, run_tool

OPF = "http://www.idpf.org/2007/opf"
XHTML = "http://www.w3.org/1999/xhtml"
EPUB = "http://www.idpf.org/2007/ops"
SMIL = "http://www.w3.org/ns/SMIL"
DC = "http://purl.org/dc/elements/1.1/"
NS = {"p": OPF, "x": XHTML, "s": SMIL, "d": DC}


register_namespace("", XHTML)
register_namespace("epub", EPUB)
register_namespace("dc", DC)


def write_epub(
    source: Path, output: Path, edits: dict[str, bytes], removed: set[str]
) -> None:
    """Copy a container, with its uncompressed mimetype first."""
    if source.resolve() == output.resolve():
        msg = "source and output EPUB must differ"
        raise ValueError(msg)
    with ZipFile(source) as archive, ZipFile(output, "w", ZIP_DEFLATED) as result:
        result.writestr("mimetype", b"application/epub+zip", compress_type=ZIP_STORED)
        for info in archive.infolist():
            if info.filename != "mimetype" and info.filename not in removed:
                result.writestr(
                    info.filename, edits.get(info.filename, archive.read(info))
                )
        for name, content in edits.items():
            if name not in archive.namelist():
                result.writestr(name, content)


def _metadata(package: Element, pathway: str) -> None:
    metadata = package.find("p:metadata", NS)
    identifier = metadata.find("d:identifier", NS)
    identifier.set("id", package.get("unique-identifier"))
    package.set("version", "3.0")
    package.set("{http://www.w3.org/XML/1998/namespace}lang", "vi")
    for element in metadata:
        for attribute in (
            f"{{{OPF}}}role",
            f"{{{OPF}}}scheme",
            f"{{{OPF}}}file-as",
        ):
            element.attrib.pop(attribute, None)
    modified = metadata.find("p:meta[@property='dcterms:modified']", NS)
    if modified is None:
        modified = SubElement(
            metadata, f"{{{OPF}}}meta", {"property": "dcterms:modified"}
        )
    modified.text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    for prop, value in (
        ("schema:accessMode", "textual"),
        ("schema:accessMode", "auditory"),
        ("schema:accessMode", "visual"),
        (
            "schema:accessModeSufficient",
            "textual" if pathway == "tts" else "textual,visual",
        ),
        ("schema:accessibilityFeature", "tableOfContents"),
        ("schema:accessibilityFeature", "synchronizedAudioText"),
        ("schema:accessibilityHazard", "unknown"),
        (
            "schema:accessibilitySummary",
            (
                "Vietnamese text with sentence-level synchronized narration. "
                "Final visual, audio and accessibility review is pending."
                if pathway == "tts"
                else "Vietnamese text with synchronized audiobook narration. "
                "Some headings are unmatched; interpolated timings and audio-only "
                "passages are retained. Image descriptions and final review "
                "are pending."
            ),
        ),
    ):
        SubElement(metadata, f"{{{OPF}}}meta", {"property": prop}).text = value


def _tts_navigation(
    package: Element, archive: ZipFile, edits: dict[str, bytes], directory: str
) -> None:
    metadata, manifest = package.find("p:metadata", NS), package.find("p:manifest", NS)
    cover = manifest.find("p:item[@id='imgcv']", NS)
    cover.set("properties", "cover-image")
    guide = package.find("p:guide", NS)
    if guide is not None:
        package.remove(guide)
    package.find("p:spine", NS).attrib.pop("toc", None)
    ncx_item = manifest.find("p:item[@media-type='application/x-dtbncx+xml']", NS)
    ncx = ET.fromstring(archive.read(posixpath.join(directory, ncx_item.get("href"))))
    ncx_ns = {"n": "http://www.daisy.org/z3986/2005/ncx/"}
    nav = ET.fromstring(
        f'<html xmlns="{XHTML}" xmlns:epub="{EPUB}" lang="vi" xml:lang="vi">'
        '<head><title>Mục lục</title></head><body><nav epub:type="toc" '
        'id="toc"><h1>Mục lục</h1><ol/></nav></body></html>'
    )
    listing = nav.find("x:body/x:nav/x:ol", NS)
    for point in ncx.findall(".//n:navPoint", ncx_ns):
        item = SubElement(listing, f"{{{XHTML}}}li")
        SubElement(
            item,
            f"{{{XHTML}}}a",
            {"href": point.find("n:content", ncx_ns).get("src")},
        ).text = point.findtext("n:navLabel/n:text", namespaces=ncx_ns)
    edits[posixpath.join(directory, "nav.xhtml")] = tostring(
        nav, encoding="utf-8", xml_declaration=True
    )
    SubElement(
        manifest,
        f"{{{OPF}}}item",
        {
            "id": "lyrepub-nav",
            "href": "nav.xhtml",
            "media-type": "application/xhtml+xml",
            "properties": "nav",
        },
    )
    manifest.remove(ncx_item)
    SubElement(
        metadata, f"{{{OPF}}}meta", {"property": "media:active-class"}
    ).text = "-epub-media-overlay-active"


def _notes(root: Element, body: Element) -> None:
    notes = [e for e in body.iter() if e.get("href") == "note:"]
    for index, anchor in enumerate(notes):
        if not anchor.get("title"):
            msg = "note link has no source note text"
            raise ValueError(msg)
        note_id, ref_id = (
            f"lyrepub-note-{index}",
            f"lyrepub-noteref-{index}",
        )
        existing_ids = {e.get("id") for e in root.iter()}
        if note_id in existing_ids or ref_id in existing_ids:
            msg = "note ID collision"
            raise ValueError(msg)
        if anchor.get("id") is None:
            anchor.set("id", ref_id)
        anchor.set("href", f"#{note_id}")
        anchor.set(f"{{{EPUB}}}type", "noteref")
        anchor.set("role", "doc-noteref")
        note = SubElement(
            body,
            f"{{{XHTML}}}aside",
            {
                "id": note_id,
                f"{{{EPUB}}}type": "footnote",
                "role": "doc-footnote",
            },
        )
        SubElement(note, f"{{{XHTML}}}p").text = anchor.get("title")
        SubElement(
            note,
            f"{{{XHTML}}}a",
            {"href": f"#{anchor.get('id')}", "role": "doc-backlink"},
        ).text = "Trở về chú thích"


def _xhtml(root: Element, name: str, title: str) -> None:
    root.set("lang", "vi")
    root.set("{http://www.w3.org/XML/1998/namespace}lang", "vi")
    body, head = root.find("x:body", NS), root.find("x:head", NS)
    body.attrib.pop("section", None)
    heading = next(
        (e for e in body.iter() if e.tag in (f"{{{XHTML}}}h2", f"{{{XHTML}}}h4")),
        None,
    )
    doc_title = head.find("x:title", NS)
    if doc_title is None:
        doc_title = SubElement(head, f"{{{XHTML}}}title")
    if not doc_title.text or not doc_title.text.strip():
        doc_title.text = f"{title} — " + (
            " ".join("".join(heading.itertext()).split())
            if heading is not None
            else "Thông tin tác giả"
            if "section_11" in name
            else "Bìa sau"
        )
    if heading is not None:
        heading.tag = f"{{{XHTML}}}h1"
        heading.set("class", (heading.get("class", "") + " lyrepub-heading").strip())
    for element in root.iter():
        if element.tag == f"{{{XHTML}}}author":
            element.tag = f"{{{XHTML}}}div"
    for link in list(head.findall("x:link", NS)):
        if link.get("href") == "../Styles/book-style-3.css":
            head.remove(link)
    for nav in root.findall(".//x:nav", NS):
        if nav.get(f"{{{EPUB}}}type") == "toc":
            nav.set("role", "doc-toc")
    _notes(root, body)


def repair(source: Path, output: Path, pathway: str) -> None:
    """Apply known source repairs; image descriptions remain human-review drafts."""
    edits = {}
    with ZipFile(source) as archive:
        package_path = next(n for n in archive.namelist() if n.endswith(".opf"))
        package = ET.fromstring(archive.read(package_path))
        directory = posixpath.dirname(package_path)
        metadata, _manifest = (
            package.find("p:metadata", NS),
            package.find("p:manifest", NS),
        )
        title = metadata.findtext("d:title", namespaces=NS)
        _metadata(package, pathway)
        if pathway == "tts":
            _tts_navigation(package, archive, edits, directory)
        for name in archive.namelist():
            if name.endswith((".html", ".xhtml")):
                root = ET.fromstring(archive.read(name))
                _xhtml(root, name, title)
                edits[name] = tostring(root, encoding="utf-8", xml_declaration=True)
            elif name.endswith(".ncx") and pathway == "alignment":
                ncx = ET.fromstring(archive.read(name))
                uid = ncx.find(
                    "{http://www.daisy.org/z3986/2005/ncx/}head/{http://www.daisy.org/z3986/2005/ncx/}meta[@name='dtb:uid']"
                )
                uid.set(
                    "content",
                    package.findtext("p:metadata/d:identifier", namespaces=NS),
                )
                edits[name] = tostring(ncx, encoding="utf-8", xml_declaration=True)
            elif name == "OEBPS/Styles/fonts-books2.css":
                edits[name] = archive.read(name).replace(
                    b"url(../Fonts/EBGaramond-Regular.woff) format('woff'), ", b""
                )
            elif name == "OEBPS/stylesheet.css":
                edits[name] = (
                    archive.read(name).replace(b"h4 {", b"h1 {")
                    + b"\n.-epub-media-overlay-active { background-color: #ffb; }\n"
                    b".author { color: #555; }\n.ebook { color: #555; }\n"
                )
            elif name == "OEBPS/Styles/Styles.css":
                edits[name] = (
                    archive.read(name)
                    + b"\nh1.lyrepub-heading { font-size: 2.5em; padding-top: 12px; "
                    b"margin-bottom: 8px; }\n"
                )
        edits[package_path] = tostring(package, encoding="utf-8", xml_declaration=True)
    write_epub(source, output, edits, {"OEBPS/toc.ncx"} if pathway == "tts" else set())


def verify_alignment(frozen: Path, regenerated: Path, epub: Path) -> None:
    """Check retained report spans and the four recorded sentence starts."""
    report = json.loads(frozen.read_text())
    if report != json.loads(regenerated.read_text()):
        msg = "regenerated alignment report differs from frozen evidence"
        raise ValueError(msg)
    with ZipFile(epub) as archive:
        clips = {}
        for name in archive.namelist():
            if name.endswith(".smil"):
                for par in ET.fromstring(archive.read(name)).findall(".//s:par", NS):
                    audio = par.find("s:audio", NS)
                    if audio is not None:
                        clips[par.get("id")] = audio.attrib
        for span in report["spans"]:
            if span["audio"] is None:
                continue
            href = report["spine"][span["spine"]]["href"]
            first = clips[f"{href.replace('/', '-')}-s{span['firstSentence']}"]
            last = clips[f"{href.replace('/', '-')}-s{span['lastSentence']}"]
            if (
                Decimal(first["clipBegin"].removesuffix("s"))
                != Decimal(str(span["audio"]["start"]))
                or Decimal(last["clipEnd"].removesuffix("s"))
                != Decimal(str(span["audio"]["end"]))
                or Path(first["src"]).name
                != report["tracks"][span["audio"]["track"]]["name"]
            ):
                msg = "SMIL differs from frozen report span"
                raise ValueError(msg)
        for target, begin in (
            ("Text-section_2.html-s0", "91.88"),
            ("Text-section_3.html-s1", "494.20"),
            ("Text-section_4.html-s0", "1.54"),
            ("Text-section_8.html-s183", "917.30"),
        ):
            if Decimal(clips[target]["clipBegin"].removesuffix("s")) != Decimal(begin):
                msg = "SMIL differs from recorded manual boundary"
                raise ValueError(msg)


def package_alignment(source: Path, output: Path) -> None:
    """Replace embedded MP3s with Opus, retaining SMIL clip values exactly."""
    if source.resolve() == (output / "final.epub").resolve():
        msg = "source and output EPUB must differ"
        raise ValueError(msg)
    output.mkdir(parents=True, exist_ok=True)
    edits, removed, durations = {}, set(), {}
    with ZipFile(source) as archive:
        package_path = next(n for n in archive.namelist() if n.endswith(".opf"))
        package = ET.fromstring(archive.read(package_path))
        directory = posixpath.dirname(package_path)
        for item in package.findall("p:manifest/p:item[@media-type='audio/mpeg']", NS):
            path = posixpath.normpath(
                posixpath.join(directory, unquote(item.get("href")))
            )
            mp3, opus = (
                output / Path(path).name,
                output / Path(path).with_suffix(".opus").name,
            )
            mp3.write_bytes(archive.read(path))
            run_tool(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(mp3),
                    "-c:a",
                    "libopus",
                    "-b:a",
                    "96k",
                    str(opus),
                ]
            )
            packaged = posixpath.splitext(path)[0] + ".opus"
            edits[packaged], durations[packaged] = opus.read_bytes(), ogg_duration(opus)
            item.set("href", posixpath.splitext(item.get("href"))[0] + ".opus")
            item.set("media-type", "audio/ogg; codecs=opus")
            removed.add(path)
        for name in archive.namelist():
            if not name.endswith(".smil"):
                continue
            root = ET.fromstring(archive.read(name))
            for audio in root.findall(".//s:audio", NS):
                reference = posixpath.splitext(audio.get("src"))[0] + ".opus"
                path = posixpath.normpath(
                    posixpath.join(posixpath.dirname(name), reference)
                )
                if (
                    not Decimal(0)
                    <= Decimal(audio.get("clipBegin").removesuffix("s"))
                    < Decimal(audio.get("clipEnd").removesuffix("s"))
                    <= durations[path]
                ):
                    msg = "alignment clip exceeds packaged audio duration"
                    raise ValueError(msg)
                audio.set("src", reference)
            edits[name] = tostring(root, encoding="utf-8", xml_declaration=True)
        edits[package_path] = tostring(package, encoding="utf-8", xml_declaration=True)
    repackaged = output / "opus.epub"
    write_epub(source, repackaged, edits, removed)
    repair(repackaged, output / "final.epub", "alignment")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frozen-report", type=Path, required=True)
    parser.add_argument("--regenerated-report", type=Path, required=True)
    args = parser.parse_args()
    verify_alignment(args.frozen_report, args.regenerated_report, args.source)
    package_alignment(args.source, args.output)


if __name__ == "__main__":
    main()
