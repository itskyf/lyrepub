"""Publish timed XHTML fragments as EPUB 3.3 Media Overlays."""

import math
import posixpath
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZipFile

import defusedxml.minidom
from defusedxml import ElementTree
from fast_ebook import epub

_OPF = "http://www.idpf.org/2007/opf"
_SMIL = "http://www.w3.org/ns/SMIL"
_XHTML = "http://www.w3.org/1999/xhtml"
_CONTAINER = "urn:oasis:names:tc:opendocument:xmlns:container"
_AUDIO = {
    ".mp3": "audio/mpeg",
    ".opus": "audio/ogg; codecs=opus",
}


@dataclass(frozen=True, slots=True)
class Timing:
    """A packaged XHTML fragment and audio clip, both hrefs relative to the OPF."""

    text_href: str
    audio_href: str
    clip_begin: float
    clip_end: float


def _resource_path(href: str, opf_dir: str) -> str:
    parsed = urlsplit(href)
    if (
        not parsed.path
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.path.startswith("/")
    ):
        msg = f"invalid EPUB resource href: {href!r}"
        raise ValueError(msg)
    path = posixpath.normpath(posixpath.join(opf_dir, unquote(parsed.path)))
    if path.startswith("../") or path == "..":
        msg = f"resource escapes EPUB container: {href!r}"
        raise ValueError(msg)
    return path


def _audio_type(href: str, path: Path) -> str:
    media = _AUDIO.get(Path(href).suffix.lower())
    if media is None:
        msg = f"unsupported EPUB Media Overlay audio format: {href!r}"
        raise ValueError(msg)
    if not path.is_file():
        msg = f"missing audio file: {path}"
        raise ValueError(msg)
    return media


def _clock(seconds: float | Decimal) -> str:
    return f"{Decimal(str(seconds)):f}s"


def _spine_items(book: epub.EpubBook) -> dict[str, tuple[int, str, dict[str, int]]]:
    spine_items: dict[str, tuple[int, str, dict[str, int]]] = {}
    for spine_index, (idref, _linear) in enumerate(book.get_spine()):
        item = book.get_item_with_id(idref)
        if item is None or item.get_media_type() != "application/xhtml+xml":
            msg = f"invalid XHTML spine item: {idref!r}"
            raise ValueError(msg)
        href = item.get_name()
        root = ElementTree.fromstring(item.get_content())
        body = root.find(f"{{{_XHTML}}}body")
        if body is None:
            msg = f"XHTML has no body: {href!r}"
            raise ValueError(msg)
        ids = {
            element.get("id"): index
            for index, element in enumerate(body.iter())
            if element.get("id")
        }
        spine_items[href] = (spine_index, idref, ids)
    return spine_items


def _group_timings(
    timings: list[Timing],
    audio_files: dict[str, Path],
    spine_items: dict[str, tuple[int, str, dict[str, int]]],
) -> dict[str, list[tuple[int, Timing, str]]]:
    grouped: dict[str, list[tuple[int, Timing, str]]] = defaultdict(list)
    for timing in timings:
        parts = urlsplit(timing.text_href)
        href, fragment = parts.path, unquote(parts.fragment)
        if (
            parts.scheme
            or parts.netloc
            or parts.query
            or href not in spine_items
            or not fragment
        ):
            msg = f"unresolvable XHTML target: {timing.text_href!r}"
            raise ValueError(msg)
        position = spine_items[href][2].get(fragment)
        if position is None:
            msg = f"unresolvable XHTML target: {timing.text_href!r}"
            raise ValueError(msg)
        if timing.audio_href not in audio_files:
            msg = f"missing supplied audio: {timing.audio_href!r}"
            raise ValueError(msg)
        if not (
            math.isfinite(timing.clip_begin)
            and math.isfinite(timing.clip_end)
            and 0 <= timing.clip_begin < timing.clip_end
        ):
            msg = f"invalid clip times for {timing.text_href!r}"
            raise ValueError(msg)
        grouped[href].append((position, timing, fragment))
    if set(audio_files) != {t.audio_href for t in timings}:
        msg = "audio files must match referenced audio hrefs"
        raise ValueError(msg)
    return grouped


def _add_audio(
    package: minidom.Document,
    manifest: minidom.Element,
    audio_files: dict[str, Path],
    opf_dir: str,
    existing_paths: set[str],
) -> dict[str, Path]:
    additions: dict[str, Path] = {}
    used_ids = {
        item.getAttribute("id")
        for item in manifest.getElementsByTagNameNS(_OPF, "item")
    }
    for index, (href, path) in enumerate(sorted(audio_files.items())):
        full_path = _resource_path(href, opf_dir)
        if (
            full_path in existing_paths
            or href in existing_paths
            or full_path in additions
        ):
            msg = f"EPUB resource already exists: {href!r}"
            raise ValueError(msg)
        media_type = _audio_type(href, path)
        audio_id = f"lyrepub-audio-{index}"
        if audio_id in used_ids:
            msg = f"manifest ID already exists: {audio_id}"
            raise ValueError(msg)
        used_ids.add(audio_id)
        item = package.createElementNS(_OPF, "item")
        for key, value in (
            ("id", audio_id),
            ("href", href),
            ("media-type", media_type),
        ):
            item.setAttribute(key, value)
        manifest.appendChild(item)
        additions[full_path] = path
    return additions


def _smil_content(
    rows: list[tuple[int, Timing, str]], xhtml_path: str, smil_path: str, opf_dir: str
) -> tuple[bytes, Decimal]:
    root = Element("smil", {"xmlns": _SMIL, "version": "3.0"})
    body = SubElement(root, "body")
    duration = Decimal(0)
    for _, timing, fragment in sorted(
        rows,
        key=lambda row: (
            row[0],
            row[1].clip_begin,
            row[1].audio_href,
            row[1].clip_end,
        ),
    ):
        par = SubElement(body, "par")
        text_path = posixpath.relpath(xhtml_path, posixpath.dirname(smil_path))
        audio_path = posixpath.relpath(
            _resource_path(timing.audio_href, opf_dir),
            posixpath.dirname(smil_path),
        )
        SubElement(par, "text", {"src": f"{text_path}#{fragment}"})
        SubElement(
            par,
            "audio",
            {
                "src": audio_path,
                "clipBegin": _clock(timing.clip_begin),
                "clipEnd": _clock(timing.clip_end),
            },
        )
        duration += Decimal(str(timing.clip_end)) - Decimal(str(timing.clip_begin))
    return tostring(root, encoding="utf-8", xml_declaration=True), duration


def _add_overlays(
    package: minidom.Document,
    spine_items: dict[str, tuple[int, str, dict[str, int]]],
    grouped: dict[str, list[tuple[int, Timing, str]]],
    opf_dir: str,
    reserved_paths: set[str],
) -> dict[str, bytes]:
    metadata = package.getElementsByTagNameNS(_OPF, "metadata")[0]
    manifest = package.getElementsByTagNameNS(_OPF, "manifest")[0]
    items = {
        item.getAttribute("id"): item
        for item in manifest.getElementsByTagNameNS(_OPF, "item")
    }
    used_ids = set(items)
    additions: dict[str, bytes] = {}
    total_duration = Decimal(0)
    for index, href in enumerate(sorted(grouped, key=lambda h: spine_items[h][0])):
        _, item_id, _ = spine_items[href]
        xhtml_path = _resource_path(href, opf_dir)
        smil_path = posixpath.splitext(xhtml_path)[0] + ".smil"
        smil_href = posixpath.relpath(smil_path, opf_dir or ".")
        if (
            smil_path in reserved_paths
            or smil_href in reserved_paths
            or smil_path in additions
        ):
            msg = f"EPUB resource already exists: {smil_path!r}"
            raise ValueError(msg)
        smil_id = f"lyrepub-smil-{index}"
        if smil_id in used_ids:
            msg = f"manifest ID already exists: {smil_id}"
            raise ValueError(msg)
        used_ids.add(smil_id)
        content, duration = _smil_content(grouped[href], xhtml_path, smil_path, opf_dir)
        total_duration += duration
        additions[smil_path] = content
        item = package.createElementNS(_OPF, "item")
        for key, value in (
            ("id", smil_id),
            ("href", smil_href),
            ("media-type", "application/smil+xml"),
        ):
            item.setAttribute(key, value)
        manifest.appendChild(item)
        items[item_id].setAttribute("media-overlay", smil_id)
        meta = package.createElementNS(_OPF, "meta")
        meta.setAttribute("property", "media:duration")
        meta.setAttribute("refines", f"#{smil_id}")
        meta.appendChild(package.createTextNode(_clock(duration)))
        metadata.appendChild(meta)
    meta = package.createElementNS(_OPF, "meta")
    meta.setAttribute("property", "media:duration")
    meta.appendChild(package.createTextNode(_clock(total_duration)))
    metadata.appendChild(meta)
    return additions


def _update_modified(package: minidom.Document) -> None:
    metadata = package.getElementsByTagNameNS(_OPF, "metadata")[0]
    modified = [
        meta
        for meta in metadata.getElementsByTagNameNS(_OPF, "meta")
        if meta.getAttribute("property") == "dcterms:modified"
    ]
    if len(modified) != 1:
        msg = "EPUB must have exactly one dcterms:modified value"
        raise ValueError(msg)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if modified[0].firstChild is None:
        modified[0].appendChild(package.createTextNode(timestamp))
    else:
        modified[0].firstChild.nodeValue = timestamp


def publish_media_overlays(
    source: Path,
    output: Path,
    timings: list[Timing],
    audio_files: dict[str, Path],
) -> None:
    """Package audio and one overlay per synchronized spine XHTML document.

    All hrefs are relative to the package document. The source EPUB must not
    already contain overlays; publication leaves authored XHTML untouched.
    """
    if source.resolve() == output.resolve():
        msg = "source and output EPUB must differ"
        raise ValueError(msg)
    if output.exists():
        msg = f"output EPUB already exists: {output}"
        raise ValueError(msg)
    if not timings:
        msg = "at least one timing is required"
        raise ValueError(msg)

    book = epub.read_epub(source, options={"ignore_ncx": True, "ignore_nav": True})
    with ZipFile(source) as archive:
        container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
        rootfile = container.find(f"{{{_CONTAINER}}}rootfiles/{{{_CONTAINER}}}rootfile")
        if rootfile is None:
            msg = "EPUB has no package document"
            raise ValueError(msg)
        opf_path = rootfile.attrib["full-path"]
        opf_dir = posixpath.dirname(opf_path)
        package = defusedxml.minidom.parseString(archive.read(opf_path))
        manifest = package.getElementsByTagNameNS(_OPF, "manifest")[0]
        items = {
            item.getAttribute("id"): item
            for item in manifest.getElementsByTagNameNS(_OPF, "item")
        }
        if any(item.hasAttribute("media-overlay") for item in items.values()):
            msg = "source EPUB already has Media Overlays"
            raise ValueError(msg)
        spine_items = _spine_items(book)
        grouped = _group_timings(timings, audio_files, spine_items)
        existing_paths = set(archive.namelist()) | {
            item.getAttribute("href") for item in items.values()
        }
        additions = _add_audio(package, manifest, audio_files, opf_dir, existing_paths)
        additions.update(
            _add_overlays(
                package,
                spine_items,
                grouped,
                opf_dir,
                existing_paths | additions.keys(),
            )
        )
        _update_modified(package)
        additions[opf_path] = package.toxml(encoding="utf-8")

        with ZipFile(output, "w") as result:
            for info in archive.infolist():
                content = additions.pop(info.filename, None)
                result.writestr(
                    info, archive.read(info.filename) if content is None else content
                )
            for path, content in additions.items():
                if isinstance(content, Path):
                    result.write(content, path)
                else:
                    result.writestr(path, content)
