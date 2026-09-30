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

from defusedxml import ElementTree

from lyrepub.audio import encode_opus

OPF = "http://www.idpf.org/2007/opf"
XHTML = "http://www.w3.org/1999/xhtml"
EPUB = "http://www.idpf.org/2007/ops"
SMIL = "http://www.w3.org/ns/SMIL"
DC = "http://purl.org/dc/elements/1.1/"
NS = {"p": OPF, "x": XHTML, "s": SMIL, "d": DC}
DISTRIBUTION_HEADER = (
    "Thăng Long Nổi Giận",
    "Hoàng Quốc Hải",
    "www.dtv-ebook.com",
)
CHAPTER_OPENING_LENGTH = 4  # heading, first paragraph, candidate, next paragraph
OPENING_CREDIT = (
    "Tác phẩm Đêm hội Long Trì - tiểu thuyết - tác giả Nguyễn Huy Tưởng - "
    "NXB Kim Đồng ấn hành - người đọc Ngọc Hân"
)


def join_sentence_boundary(
    source: str, sentences: list[str], left: int, right: int, punctuation: str
) -> None:
    """Join a reviewed #17 punctuation split without changing authored text."""
    boundary = left if punctuation == "-" else right
    if sentences[boundary] != punctuation:
        msg = "reviewed punctuation target differs from source"
        raise ValueError(msg)
    cursor = 0
    for previous in sentences[:left]:
        cursor = source.index(previous, cursor) + len(previous)
    start = source.index(sentences[left], cursor)
    end = source.index(sentences[right], start + len(sentences[left])) + len(
        sentences[right]
    )
    sentences[left : right + 1] = [source[start:end]]


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
    """Set reviewed discovery metadata for each known publication."""
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
    properties = [
        ("schema:accessMode", "textual"),
        ("schema:accessibilityFeature", "tableOfContents"),
        ("schema:accessibilityFeature", "synchronizedAudioText"),
        ("schema:accessibilityHazard", "noFlashingHazard"),
        ("schema:accessibilityHazard", "noMotionSimulationHazard"),
        ("schema:accessibilityHazard", "unknownSoundHazard"),
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
    ]
    if pathway == "alignment":
        properties.extend(
            (
                ("schema:accessMode", "visual"),
                ("schema:accessibilityFeature", "alternativeText"),
            )
        )
    for prop, value in properties:
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
    if any("nav" in item.get("properties", "").split() for item in manifest):
        return
    ncx_item = manifest.find("p:item[@media-type='application/x-dtbncx+xml']", NS)
    ncx = ElementTree.fromstring(
        archive.read(posixpath.join(directory, ncx_item.get("href")))
    )
    ncx_ns = {"n": "http://www.daisy.org/z3986/2005/ncx/"}
    nav = ElementTree.fromstring(
        f'<html xmlns="{XHTML}" xmlns:epub="{EPUB}" lang="vi" xml:lang="vi">'
        '<head><title>Mục lục</title></head><body><nav epub:type="toc" '
        'id="toc" role="doc-toc"><h1>Mục lục</h1><ol/></nav></body></html>'
    )
    listing = nav.find("x:body/x:nav/x:ol", NS)

    def add_points(points: list[Element], parent: Element) -> None:
        for point in points:
            item = SubElement(parent, f"{{{XHTML}}}li")
            SubElement(
                item,
                f"{{{XHTML}}}a",
                {"href": point.find("n:content", ncx_ns).get("src")},
            ).text = point.findtext("n:navLabel/n:text", namespaces=ncx_ns)
            children = point.findall("n:navPoint", ncx_ns)
            if children:
                add_points(children, SubElement(item, f"{{{XHTML}}}ol"))

    add_points(ncx.findall("n:navMap/n:navPoint", ncx_ns), listing)
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
        if name == "OEBPS/Text/cover.xhtml":
            SubElement(
                head,
                f"{{{XHTML}}}link",
                {"rel": "stylesheet", "href": "../Styles/storyteller-readaloud.css"},
            )
            SubElement(
                body, f"{{{XHTML}}}p", {"id": "lyrepub-opening-credit"}
            ).text = OPENING_CREDIT
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
    for link in list(head.findall("x:link", NS)):
        if pathway == "alignment" and link.get("href") == "../Styles/book-style-3.css":
            head.remove(link)
    for nav in root.findall(".//x:nav", NS):
        if nav.get(f"{{{EPUB}}}type") == "toc":
            nav.set("role", "doc-toc")
    if pathway == "alignment":
        _notes(root, body)


def _remove_distribution_boilerplate(body: Element) -> bool:
    if len(body) < len(DISTRIBUTION_HEADER):
        return False
    title, author, distributor = body[: len(DISTRIBUTION_HEADER)]
    if (
        title.tag == f"{{{XHTML}}}div"
        and title.get("class") == "header"
        and " ".join(title.itertext()).strip() == DISTRIBUTION_HEADER[0]
        and author.tag == f"{{{XHTML}}}div"
        and author.get("class") == "author"
        and " ".join(author.itertext()).strip() == DISTRIBUTION_HEADER[1]
        and distributor.tag == f"{{{XHTML}}}author"
        and len(distributor) == 1
        and distributor[0].tag == f"{{{XHTML}}}div"
        and distributor[0].get("class") == "author"
        and " ".join(distributor[0].itertext()).strip() == DISTRIBUTION_HEADER[2]
    ):
        for element in (title, author, distributor):
            body.remove(element)
        return True
    return False


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


def _alignment_opening(
    package: Element, archive: ZipFile, edits: dict[str, bytes]
) -> None:
    """Move the spoken credit to the visible cover before biography playback."""
    # MOSS and adjacent silence locate this boundary; Thorium playback was checked.
    onset, name_onset, year_onset = "20.900s", "21.400s", "22.400s"
    manifest = package.find("p:manifest", NS)
    cover = manifest.find("p:item[@href='Text/cover.xhtml']", NS)
    if cover is None or "OEBPS/Text/cover.xhtml" not in archive.namelist():
        msg = "alignment cover resource missing"
        raise ValueError(msg)
    path = "OEBPS/MediaOverlays/section_11.smil"
    smil = ElementTree.fromstring(archive.read(path))
    seq = smil.find("s:body/s:seq", NS)
    pars = seq.findall("s:par", NS)
    expected = (
        ("Text-section_11.html-s0-before0", "0.000s", "7.960s"),
        ("Text-section_11.html-s0", "7.960s", "9.080s"),
        ("Text-section_11.html-s1", "9.080s", "10.560s"),
        ("Text-section_11.html-s2", "10.560s", "26.100s"),
    )
    if len(pars) < len(expected) or any(
        (
            par.get("id"),
            par.find("s:audio", NS).get("clipBegin"),
            par.find("s:audio", NS).get("clipEnd"),
        )
        != row
        for par, row in zip(pars, expected, strict=False)
    ):
        msg = "alignment opening SMIL differs from reviewed source"
        raise ValueError(msg)
    audio = pars[0].find("s:audio", NS)
    seq.remove(pars[0])
    for par, begin, end in zip(
        pars[1:4],
        (onset, name_onset, year_onset),
        (name_onset, year_onset, "26.100s"),
        strict=True,
    ):
        par_audio = par.find("s:audio", NS)
        par_audio.set("clipBegin", begin)
        par_audio.set("clipEnd", end)
    edits[path] = tostring(smil, encoding="utf-8", xml_declaration=True)

    cover_smil = Element(f"{{{SMIL}}}smil", {"version": "3.0"})
    cover_seq = SubElement(
        SubElement(cover_smil, f"{{{SMIL}}}body"),
        f"{{{SMIL}}}seq",
        {"id": "lyrepub-cover-overlay", f"{{{EPUB}}}textref": "../Text/cover.xhtml"},
    )
    credit = SubElement(cover_seq, f"{{{SMIL}}}par", {"id": "lyrepub-opening-credit"})
    SubElement(
        credit,
        f"{{{SMIL}}}text",
        {"src": "../Text/cover.xhtml#lyrepub-opening-credit"},
    )
    SubElement(
        credit,
        f"{{{SMIL}}}audio",
        {"src": audio.get("src"), "clipBegin": "0.000s", "clipEnd": onset},
    )
    edits["OEBPS/MediaOverlays/cover.smil"] = tostring(
        cover_smil, encoding="utf-8", xml_declaration=True
    )
    cover.set("media-overlay", "lyrepub-cover-overlay")
    SubElement(
        manifest,
        f"{{{OPF}}}item",
        {
            "id": "lyrepub-cover-overlay",
            "href": "MediaOverlays/cover.smil",
            "media-type": "application/smil+xml",
        },
    )
    metadata = package.find("p:metadata", NS)
    duration = metadata.find(
        "p:meta[@property='media:duration'][@refines='#Text-section_11.html_overlay']",
        NS,
    )
    if duration is None or duration.text != "00:01:31.88":
        msg = "alignment opening overlay duration differs from reviewed source"
        raise ValueError(msg)
    duration.text = "00:01:10.98"
    SubElement(
        metadata,
        f"{{{OPF}}}meta",
        {"property": "media:duration", "refines": "#lyrepub-cover-overlay"},
    ).text = "00:00:20.90"


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
        package = ElementTree.fromstring(archive.read(package_path))
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
        elif "OEBPS/MediaOverlays/section_11.smil" in archive.namelist():
            _alignment_opening(package, archive, edits)
        for name in archive.namelist():
            if name in removed:
                continue
            if name.endswith((".html", ".xhtml")):
                root = ElementTree.fromstring(archive.read(name))
                _xhtml(root, name, title, pathway)
                if pathway == "alignment":
                    _alignment_images(root, title, author)
                edits[name] = tostring(root, encoding="utf-8", xml_declaration=True)
            elif name.endswith(".ncx") and pathway == "alignment":
                ncx = ElementTree.fromstring(archive.read(name))
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
    """Remove chapter distribution text and duplicated opening fragments."""
    edits = {}
    corrected_phu = 0
    with ZipFile(source) as archive:
        for name in archive.namelist():
            if not name.startswith("OEBPS/Text/") or not name.endswith(".html"):
                continue
            if not Path(name).stem.isdecimal():
                continue
            root = ElementTree.fromstring(archive.read(name))
            body = root.find("x:body", NS)
            children = list(body) if body is not None else []
            if (
                len(children) < len(DISTRIBUTION_HEADER) + CHAPTER_OPENING_LENGTH
                or children[3].tag != f"{{{XHTML}}}h4"
            ):
                msg = f"chapter opening structure missing or changed: {name}"
                raise ValueError(msg)
            if not _remove_distribution_boilerplate(body):
                msg = f"chapter distribution header missing or changed: {name}"
                raise ValueError(msg)
            children = list(body)
            if (
                len(children) < CHAPTER_OPENING_LENGTH
                or children[1].tag != f"{{{XHTML}}}p"
            ):
                msg = f"chapter opening structure changed: {name}"
                raise ValueError(msg)
            first, candidate, following = children[1:4]
            initial = "".join(candidate.itertext()).strip()
            if (
                candidate.tag == f"{{{XHTML}}}p"
                and len(initial.lstrip('"')) == 1
                and initial[-1:].isalpha()
                and "".join(first.itertext()).startswith(initial)
            ):
                if (
                    first.attrib
                    or len(first)
                    or candidate.attrib
                    or len(candidate)
                    or following.tag != f"{{{XHTML}}}p"
                    or not "".join(following.itertext()).strip()
                ):
                    msg = f"ambiguous detached opening fragment: {name}"
                    raise ValueError(msg)
                body.remove(candidate)
            if name == "OEBPS/Text/12.html":
                if (first.text or "").count('"P hú') != 1:
                    msg = "reviewed Phú correction missing or ambiguous: Text/12.html"
                    raise ValueError(msg)
                first.text = first.text.replace('"P hú', '"Phú', 1)
                corrected_phu += 1
            edits[name] = tostring(root, encoding="utf-8", xml_declaration=True)
    if corrected_phu != 1:
        msg = "reviewed Phú correction resource missing: Text/12.html"
        raise ValueError(msg)
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
                for par in ElementTree.fromstring(archive.read(name)).findall(
                    ".//s:par", NS
                ):
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


def package_alignment(source: Path, final: Path, work: Path) -> None:
    """Replace embedded MP3s with Opus, retaining SMIL clip values exactly."""
    if source.resolve() == final.resolve():
        msg = "source and output EPUB must differ"
        raise ValueError(msg)
    final.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    edits, removed, durations = {}, set(), {}
    with ZipFile(source) as archive:
        package_path = next(n for n in archive.namelist() if n.endswith(".opf"))
        package = ElementTree.fromstring(archive.read(package_path))
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
            duration = encode_opus(mp3, opus)
            packaged = posixpath.splitext(path)[0] + ".opus"
            edits[packaged], durations[packaged] = opus.read_bytes(), duration
            item.set("href", posixpath.splitext(item.get("href"))[0] + ".opus")
            item.set("media-type", "audio/ogg; codecs=opus")
            removed.add(path)
        for name in archive.namelist():
            if not name.endswith(".smil"):
                continue
            root = ElementTree.fromstring(archive.read(name))
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
    repair(repackaged, final, "alignment")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("data/gold/dem-hoi-long-tri.epub")
    )
    parser.add_argument(
        "--work", type=Path, default=Path("data/work/issue-17/dem-hoi-long-tri")
    )
    parser.add_argument("--frozen-report", type=Path, required=True)
    parser.add_argument("--regenerated-report", type=Path, required=True)
    args = parser.parse_args()
    verify_alignment(args.frozen_report, args.regenerated_report, args.source)
    package_alignment(args.source, args.output, args.work)


if __name__ == "__main__":
    main()
