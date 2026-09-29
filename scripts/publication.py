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

from scripts.tts_benchmark import ogg_duration, run_tool

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


def publication_metadata(package: Element, pathway: str) -> None:
    """Set metadata from declared resources and the publication's coverage."""
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
    modified = next(
        (
            element
            for element in metadata
            if element.get("property") == "dcterms:modified"
            and "refines" not in element.attrib
        ),
        None,
    )
    if modified is None:
        modified = SubElement(
            metadata, f"{{{OPF}}}meta", {"property": "dcterms:modified"}
        )
    modified.text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    for element in list(metadata):
        if element.get("property", "").startswith("schema:access"):
            metadata.remove(element)
    for prop, value in (
        ("schema:accessMode", "textual"),
        (
            "schema:accessModeSufficient",
            "textual",
        ),
        ("schema:accessibilityFeature", "tableOfContents"),
        ("schema:accessibilityHazard", "unknown"),
        (
            "schema:accessibilitySummary",
            (
                "Vietnamese text with sentence-level synchronized narration. "
                "Final visual, audio and accessibility review is pending."
                if pathway == "tts"
                else "Vietnamese text with synchronized audiobook narration. "
                "Some headings are unmatched; interpolated timings and audio-only "
                "passages are retained. Back-cover image text is absent from "
                "the audiobook. Final visual, audio and accessibility review "
                "is pending."
            ),
        ),
    ):
        SubElement(metadata, f"{{{OPF}}}meta", {"property": prop}).text = value
    manifest = package.find("p:manifest", NS)
    media_types = {item.get("media-type", "") for item in manifest}
    if any(media.startswith("audio/") for media in media_types):
        SubElement(
            metadata, f"{{{OPF}}}meta", {"property": "schema:accessMode"}
        ).text = "auditory"
    if any(media.startswith("image/") for media in media_types):
        SubElement(
            metadata, f"{{{OPF}}}meta", {"property": "schema:accessMode"}
        ).text = "visual"
    if any(item.get("media-overlay") for item in manifest):
        SubElement(
            metadata, f"{{{OPF}}}meta", {"property": "schema:accessibilityFeature"}
        ).text = "synchronizedAudioText"


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
    if any("nav" in item.get("properties", "").split() for item in manifest):
        return
    ncx_item = manifest.find("p:item[@media-type='application/x-dtbncx+xml']", NS)
    ncx = ET.fromstring(archive.read(posixpath.join(directory, ncx_item.get("href"))))
    ncx_ns = {"n": "http://www.daisy.org/z3986/2005/ncx/"}
    nav = ET.fromstring(
        f'<html xmlns="{XHTML}" xmlns:epub="{EPUB}" lang="vi" xml:lang="vi">'
        '<head><title>Mục lục</title></head><body><nav epub:type="toc" '
        'id="toc" role="doc-toc"><h1>Mục lục</h1><ol/></nav></body></html>'
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
        anchor.attrib.pop("title")


def _xhtml(root: Element, name: str, title: str, pathway: str) -> None:
    root.set("lang", "vi")
    root.set("{http://www.w3.org/XML/1998/namespace}lang", "vi")
    body, head = root.find("x:body", NS), root.find("x:head", NS)
    if pathway == "alignment":
        body.attrib.pop("section", None)
    heading_tag = "h4" if pathway == "tts" else "h2"
    heading = next(
        (e for e in body.iter() if e.tag == f"{{{XHTML}}}{heading_tag}"), None
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
        if pathway == "tts" and element.tag == f"{{{XHTML}}}author":
            element.tag = f"{{{XHTML}}}div"
    for link in list(head.findall("x:link", NS)):
        if pathway == "alignment" and link.get("href") == "../Styles/book-style-3.css":
            head.remove(link)
    for nav in root.findall(".//x:nav", NS):
        if nav.get(f"{{{EPUB}}}type") == "toc":
            nav.set("role", "doc-toc")
    if pathway == "alignment":
        _notes(root, body)


def _alignment_images(root: Element, title: str, author: str) -> None:
    for image in root.findall(".//x:img", NS):
        if image.get("src", "").endswith("b1vz-bia-1.jpg"):
            image.set("alt", "Chân dung nhà văn Nguyễn Huy Tưởng.")
        elif image.get("src", "").endswith("hero__section_12.jpg"):
            transcription = (
                "Đêm hội Long Trì, những sinh hoạt xưa ở kinh kỳ mà trong đó, "
                "huyên náo những cảnh lộng hành bạo ngược của chị em bà Chúa Chè "
                "người Kinh Bắc. Những đau khổ của người dân phải chịu đựng mọi "
                "thời ăn chơi vô độ của các triều đại vua chúa. Nhưng chồng chất "
                "giữa những oan khiên này, vẫn thấy được đời sống người Kẻ Chợ "
                "cùng mọi quang cảnh phố phường sinh sôi. Đấy là sức sống âm thầm "
                "mà mãnh liệt của \u201cbách tính\u201d đã làm nên bao đời Kẻ Chợ. "
                "Thăng Long "
                "nhộn nhịp suốt sáng không biết có đêm trong những đêm hội Long "
                "Trì quanh Hồ Gươm, Hồ Tây... Nhà văn Tô Hoài. Giá: 39.000đ. "
                "ISBN 978-604-2-01596-7. www.nxbkimdong.com.vn. "
                "www.facebook.com/nxbkimdong. THƯ VIỆN EBOOK KIM ĐỒNG — "
                "BECOME A MEMBER. Barcodes: 5151100030004; 8935244804317."
            )
            image.set("alt", "Bìa sau; bản chép chữ bên dưới.")
            image.set("aria-describedby", "lyrepub-back-cover-text")
            body = root.find("x:body", NS)
            description = SubElement(
                body, f"{{{XHTML}}}div", {"id": "lyrepub-back-cover-text"}
            )
            SubElement(description, f"{{{XHTML}}}p").text = transcription

    for svg in root.findall(".//{http://www.w3.org/2000/svg}svg"):
        image = svg.find("{http://www.w3.org/2000/svg}image")
        if image is not None and image.get(
            "{http://www.w3.org/1999/xlink}href", ""
        ).endswith("cover_l.jpg"):
            svg.set("role", "img")
            svg.set("aria-label", f"{title} — {author}")


def repair(source: Path, output: Path, pathway: str) -> None:
    """Apply source repairs and reviewed image alternatives to the final copy."""
    edits = {}
    removed = (
        {"OEBPS/toc.ncx"}
        if pathway == "tts"
        else {
            "OEBPS/Fonts/SourceSansPro-Regular.ttf",
            "OEBPS/Images/b1vz-bia-1_700.jpg",
            "OEBPS/Images/cover.jpg",
            "OEBPS/Images/cover_x.jpg",
            "OEBPS/Images/featured__section_1.jpg",
            "OEBPS/Images/featured__section_12.jpg",
            "OEBPS/Images/hero__section_1.jpg",
            "OEBPS/Styles/fonts-books2.css",
        }
    )
    with ZipFile(source) as archive:
        package_path = next(n for n in archive.namelist() if n.endswith(".opf"))
        package = ET.fromstring(archive.read(package_path))
        directory = posixpath.dirname(package_path)
        metadata, _manifest = (
            package.find("p:metadata", NS),
            package.find("p:manifest", NS),
        )
        for item in list(_manifest):
            if (
                pathway == "alignment"
                and posixpath.join(directory, item.get("href")) in removed
            ):
                _manifest.remove(item)
        title = metadata.findtext("d:title", namespaces=NS)
        author = metadata.findtext("d:creator", namespaces=NS)
        publication_metadata(package, pathway)
        if pathway == "tts":
            _tts_navigation(package, archive, edits, directory)
        for name in archive.namelist():
            if name in removed:
                continue
            if name.endswith((".html", ".xhtml")):
                root = ET.fromstring(archive.read(name))
                _xhtml(root, name, title, pathway)
                if pathway == "alignment":
                    _alignment_images(root, title, author)
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
            elif pathway == "tts" and name == "OEBPS/stylesheet.css":
                edits[name] = (
                    archive.read(name).replace(b"h4 {", b"h1 {")
                    + b"\n.-epub-media-overlay-active { background-color: #ffb; }\n"
                    b".author { color: #555; }\n.ebook { color: #555; }\n"
                )
            elif pathway == "alignment" and name == "OEBPS/Styles/Styles.css":
                edits[name] = (
                    archive.read(name)
                    + b"\nh1.lyrepub-heading { font-size: 2.5em; padding-top: 12px; "
                    b"margin-bottom: 8px; }\n"
                )
        edits[package_path] = tostring(package, encoding="utf-8", xml_declaration=True)
    write_epub(source, output, edits, removed)


def correct_tts_source(source: Path, output: Path) -> None:
    """Correct reviewed duplicate initials in the final TTS source copy."""
    edits = {}
    with ZipFile(source) as archive:
        for name, duplicate, prefix in (
            ("OEBPS/Text/1.html", "V", "Vừa bước vào tới cửa cung Thánh từ"),
            ("OEBPS/Text/12.html", '"P', '"P hú quốc Cường binh sách"'),
        ):
            if name not in archive.namelist():
                continue
            root = ET.fromstring(archive.read(name))
            body = root.find("x:body", NS)
            paragraphs = body.findall("x:p", NS)
            if (
                not paragraphs[0].text.startswith(prefix)
                or paragraphs[1].text != duplicate
            ):
                message = "reviewed duplicate-initial context differs from source"
                raise ValueError(message)
            if duplicate == '"P':
                paragraphs[0].text = paragraphs[0].text.replace('"P hú', '"Phú', 1)
            body.remove(paragraphs[1])
            edits[name] = tostring(root, encoding="utf-8", xml_declaration=True)
    write_epub(source, output, edits, set())


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
    work = output / "work"
    work.mkdir(exist_ok=True)
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
                work / Path(path).name,
                work / Path(path).with_suffix(".opus").name,
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
    repackaged = work / "opus.epub"
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
