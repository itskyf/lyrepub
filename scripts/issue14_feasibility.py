"""Generate Issue #14 TTS listening evidence and a paragraph-overlay EPUB.

Source and model locations are runtime inputs. Outputs live in gitignored data/.
"""

import argparse
import copy
import hashlib
import importlib
import json
import logging
import os
import tempfile
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

ISBN = "9786045633946"
CASES = (
    (10, 42),
    (5, 26),
    (15, 17),
    (12, 68),
    (12, 30),
    (18, 35),
    (2, 70),
    (5, 9),
    (17, 135),
)
PREFIXES = {
    (10, 42): "Quang Khải nắm tay Quốc Tuấn",
    (5, 26): "Chính việc cha dặn bị vỡ lở",
    (15, 17): "Cứ theo như Đỗ Vỹ tâu",
    (12, 68): "Thu thập tin tức xong, Đỗ Vỹ",
    (12, 30): "(Đây ám chỉ Marco Polo",
    (18, 35): "- Muôn tâu thượng hoàng",
    (2, 70): "(Văn Thù: là một trong 8 vị",
    (5, 9): "Phủ Chiêu Quốc không phải là phủ lớn nhất",
    (17, 135): 'Tiếng "Sát Thát!',
}
PLAYBACK = ((5, 8), (5, 9), (5, 10), (10, 41), (10, 42), (10, 43))
XHTML = "http://www.w3.org/1999/xhtml"
OPF = "http://www.idpf.org/2007/opf"
DC = "http://purl.org/dc/elements/1.1/"
SMIL = "http://www.w3.org/ns/SMIL"
EPUB = "http://www.idpf.org/2007/ops"
LOGGER = logging.getLogger(__name__)


def run_tool(command: list[str], input_text: str | None = None) -> tuple[str, str]:
    """Run a local tool without a shell, capturing stdout and stderr."""
    with (
        tempfile.TemporaryFile() as stdin,
        tempfile.TemporaryFile() as stdout,
        tempfile.TemporaryFile() as stderr,
    ):
        if input_text is not None:
            stdin.write(input_text.encode())
            stdin.seek(0)
        actions = [
            (os.POSIX_SPAWN_DUP2, stdout.fileno(), 1),
            (os.POSIX_SPAWN_DUP2, stderr.fileno(), 2),
        ]
        if input_text is not None:
            actions.append((os.POSIX_SPAWN_DUP2, stdin.fileno(), 0))
        pid = os.posix_spawnp(command[0], command, os.environ, file_actions=actions)
        _, status = os.waitpid(pid, 0)
        stdout.seek(0)
        stderr.seek(0)
        out, err = stdout.read().decode(), stderr.read().decode()
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
        message = f"{command[0]} failed: {err[-1000:]}"
        raise RuntimeError(message)
    return out, err


def key(spine_index: int, block_index: int) -> str:
    return f"s{spine_index}-b{block_index}"


def load_records(output: Path) -> list[dict]:
    return json.loads((output / "cases.json").read_text(encoding="utf-8"))


def save_records(output: Path, records: list[dict]) -> None:
    (output / "cases.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def prepare(output: Path, source: Path) -> None:
    extract_blocks = importlib.import_module("lyrepub.epub_text").extract_blocks

    if not source.is_file():
        raise FileNotFoundError(source)
    blocks = {(b.spine_index, b.block_index): b for b in extract_blocks(source)}
    expected = set(CASES) | set(PLAYBACK)
    records = []
    for spine_index, block_index in sorted(expected):
        block = blocks[(spine_index, block_index)]
        if block.tag != "p" or block.run_index != 0:
            message = f"unexpected source target {key(spine_index, block_index)}"
            raise ValueError(message)
        expected_prefix = PREFIXES.get((spine_index, block_index))
        if expected_prefix and not block.text.startswith(expected_prefix):
            message = f"source text changed at {key(spine_index, block_index)}"
            raise ValueError(message)
        records.append(
            {
                "key": key(spine_index, block_index),
                "case": (spine_index, block_index) in CASES,
                "playback": (spine_index, block_index) in PLAYBACK,
                "source": {
                    "isbn": ISBN,
                    "spine_index": spine_index,
                    "href": block.href,
                    "block_index": block_index,
                    "element_path": block.element_path,
                    "run_index": block.run_index,
                    "element_id": block.element_id,
                    "text": block.text,
                },
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    save_records(output, records)
    (output / "source.json").write_text(
        json.dumps(
            {
                "filename": source.name,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def source_paragraph(source_epub: Path, record: dict) -> ET.Element:
    source = record["source"]
    with zipfile.ZipFile(source_epub) as archive:
        root = importlib.import_module("defusedxml.ElementTree").fromstring(
            archive.read("OEBPS/" + source["href"])
        )
    element = root
    for index in source["element_path"]:
        element = list(element)[index]
    if element.tag != f"{{{XHTML}}}p" or element.get("id") != source["element_id"]:
        message = f"source XHTML target changed: {record['key']}"
        raise ValueError(message)
    paragraph = copy.deepcopy(element)
    paragraph.tail = None
    paragraph.set("id", record["key"])
    text = " ".join("".join(paragraph.itertext()).split())
    if text != source["text"]:
        message = f"XHTML text differs from Block.text: {record['key']}"
        raise ValueError(message)
    return paragraph


def xhtml_document(title: str, paragraphs: list[ET.Element]) -> bytes:
    root = ET.Element(f"{{{XHTML}}}html", {"lang": "vi"})
    head = ET.SubElement(root, f"{{{XHTML}}}head")
    ET.SubElement(head, f"{{{XHTML}}}title").text = title
    ET.SubElement(
        head,
        f"{{{XHTML}}}link",
        {"rel": "stylesheet", "href": "../Styles/overlay.css", "type": "text/css"},
    )
    body = ET.SubElement(root, f"{{{XHTML}}}body")
    ET.SubElement(body, f"{{{XHTML}}}h1").text = title
    body.extend(paragraphs)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def ogg_duration(path: Path) -> Decimal:
    stdout, _ = run_tool(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    duration = Decimal(stdout.strip()).quantize(Decimal("0.001"))
    if duration <= 0:
        message = f"invalid packaged audio duration: {path}"
        raise ValueError(message)
    return duration


def overlay_assets(
    output: Path, source: Path, records: dict[str, dict]
) -> tuple[dict, list, Decimal]:
    ET.register_namespace("", XHTML)
    assets = {}
    duration_total = Decimal(0)
    spine = []
    for spine_index, start, stop, title in (
        (5, 8, 10, "Chương 6: đoạn dài"),
        (10, 41, 43, "Chương 11: lời kể"),
    ):
        name = f"s{spine_index}"
        selected = [records[key(spine_index, i)] for i in range(start, stop + 1)]
        paragraphs = [source_paragraph(source, r) for r in selected]
        assets[f"EPUB/Text/{name}.xhtml"] = xhtml_document(title, paragraphs)
        smil = ET.Element(f"{{{SMIL}}}smil", {"version": "3.0"})
        body = ET.SubElement(smil, f"{{{SMIL}}}body")
        duration = Decimal(0)
        for r in selected:
            case_key = r["key"]
            ogg = output / "audio" / f"{case_key}.ogg"
            seconds = ogg_duration(ogg)
            assets[f"EPUB/Audio/{case_key}.ogg"] = ogg.read_bytes()
            par = ET.SubElement(body, f"{{{SMIL}}}par", {"id": f"par-{case_key}"})
            ET.SubElement(
                par, f"{{{SMIL}}}text", {"src": f"../Text/{name}.xhtml#{case_key}"}
            )
            ET.SubElement(
                par,
                f"{{{SMIL}}}audio",
                {
                    "src": f"../Audio/{case_key}.ogg",
                    "clipBegin": "0.000s",
                    "clipEnd": f"{seconds:.3f}s",
                },
            )
            duration += seconds
        assets[f"EPUB/Overlays/{name}.smil"] = ET.tostring(
            smil, encoding="utf-8", xml_declaration=True
        )
        spine.append((name, title, duration))
        duration_total += duration
    return assets, spine, duration_total


def publish(output: Path, source: Path) -> None:
    validate_source(output, source)
    records = {r["key"]: r for r in load_records(output)}
    missing = [
        key(s, b) for s, b in PLAYBACK if records[key(s, b)].get("status") != "ok"
    ]
    if missing:
        message = f"cannot publish without playback audio: {missing}"
        raise RuntimeError(message)
    assets, spine, duration_total = overlay_assets(output, source, records)
    assets["EPUB/Styles/overlay.css"] = (
        b".-epub-media-overlay-active { background: #ffe07a; color: #111; }\n"
    )
    nav = ET.Element(f"{{{XHTML}}}html", {"lang": "vi"})
    ET.SubElement(
        ET.SubElement(nav, f"{{{XHTML}}}head"), f"{{{XHTML}}}title"
    ).text = "Mục lục"
    body = ET.SubElement(nav, f"{{{XHTML}}}body")
    toc = ET.SubElement(
        body, f"{{{XHTML}}}nav", {f"{{{EPUB}}}type": "toc", "role": "doc-toc"}
    )
    ET.SubElement(toc, f"{{{XHTML}}}h1").text = "Mục lục"
    links = ET.SubElement(toc, f"{{{XHTML}}}ol")
    for name, title, _ in spine:
        ET.SubElement(
            ET.SubElement(links, f"{{{XHTML}}}li"),
            f"{{{XHTML}}}a",
            {"href": f"Text/{name}.xhtml"},
        ).text = title
    assets["EPUB/nav.xhtml"] = ET.tostring(nav, encoding="utf-8", xml_declaration=True)
    ET.register_namespace("", OPF)
    ET.register_namespace("dc", DC)
    package = ET.Element(
        f"{{{OPF}}}package",
        {
            "version": "3.0",
            "unique-identifier": "pub-id",
            "prefix": "media: http://www.idpf.org/epub/vocab/overlays/#",
            "{http://www.w3.org/XML/1998/namespace}lang": "vi",
        },
    )
    metadata = ET.SubElement(package, f"{{{OPF}}}metadata")
    ET.SubElement(
        metadata, f"{{{DC}}}identifier", {"id": "pub-id"}
    ).text = "urn:uuid:55424568-7e31-4b1b-b0ac-7db07d43f014"
    ET.SubElement(
        metadata, f"{{{DC}}}title"
    ).text = "Thăng Long nổi giận — TTS feasibility excerpt"
    ET.SubElement(metadata, f"{{{DC}}}language").text = "vi"
    ET.SubElement(metadata, f"{{{DC}}}creator").text = "Hoàng Quốc Hải"
    ET.SubElement(
        metadata, f"{{{OPF}}}meta", {"property": "dcterms:modified"}
    ).text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    ET.SubElement(
        metadata, f"{{{OPF}}}meta", {"property": "media:active-class"}
    ).text = "-epub-media-overlay-active"
    ET.SubElement(
        metadata, f"{{{OPF}}}meta", {"property": "media:duration"}
    ).text = f"{duration_total:.3f}s"
    for prop, value in (
        ("schema:accessMode", "textual"),
        ("schema:accessMode", "auditory"),
        ("schema:accessModeSufficient", "textual"),
        ("schema:accessibilityFeature", "synchronizedAudioText"),
        ("schema:accessibilityHazard", "none"),
        (
            "schema:accessibilitySummary",
            (
                "Text-only feasibility excerpt with synchronized narration. "
                "Audio quality and playback usability await human review."
            ),
        ),
    ):
        ET.SubElement(metadata, f"{{{OPF}}}meta", {"property": prop}).text = value
    manifest = ET.SubElement(package, f"{{{OPF}}}manifest")
    ET.SubElement(
        manifest,
        f"{{{OPF}}}item",
        {
            "id": "nav",
            "href": "nav.xhtml",
            "media-type": "application/xhtml+xml",
            "properties": "nav",
        },
    )
    ET.SubElement(
        manifest,
        f"{{{OPF}}}item",
        {"id": "style", "href": "Styles/overlay.css", "media-type": "text/css"},
    )
    reading_order = ET.SubElement(package, f"{{{OPF}}}spine")
    for name, _, duration in spine:
        ET.SubElement(
            manifest,
            f"{{{OPF}}}item",
            {
                "id": name,
                "href": f"Text/{name}.xhtml",
                "media-type": "application/xhtml+xml",
                "media-overlay": f"mo-{name}",
            },
        )
        ET.SubElement(
            manifest,
            f"{{{OPF}}}item",
            {
                "id": f"mo-{name}",
                "href": f"Overlays/{name}.smil",
                "media-type": "application/smil+xml",
            },
        )
        ET.SubElement(
            metadata,
            f"{{{OPF}}}meta",
            {"refines": f"#mo-{name}", "property": "media:duration"},
        ).text = f"{duration:.3f}s"
        ET.SubElement(reading_order, f"{{{OPF}}}itemref", {"idref": name})
    for r in records.values():
        if r["playback"]:
            ET.SubElement(
                manifest,
                f"{{{OPF}}}item",
                {
                    "id": f"a-{r['key']}",
                    "href": f"Audio/{r['key']}.ogg",
                    "media-type": "audio/ogg; codecs=opus",
                },
            )
    assets["EPUB/package.opf"] = ET.tostring(
        package, encoding="utf-8", xml_declaration=True
    )
    container = ET.Element(
        "container",
        {"xmlns": "urn:oasis:names:tc:opendocument:xmlns:container", "version": "1.0"},
    )
    files = ET.SubElement(container, "rootfiles")
    ET.SubElement(
        files,
        "rootfile",
        {
            "full-path": "EPUB/package.opf",
            "media-type": "application/oebps-package+xml",
        },
    )
    assets["META-INF/container.xml"] = ET.tostring(
        container, encoding="utf-8", xml_declaration=True
    )
    path = output / "feasibility.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        for name, content in assets.items():
            archive.writestr(name, content, compress_type=zipfile.ZIP_DEFLATED)
    LOGGER.info("Wrote %s", path)


def validate_source(output: Path, source: Path) -> None:
    expected_sha = json.loads((output / "source.json").read_text())["sha256"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha:
        message = "source EPUB changed since prepare"
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare", "synthesize", "publish"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/issue-14-feasibility")
    )
    parser.add_argument("--source-epub", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--voice-dir", type=Path)
    parser.add_argument("--chunk-helper", type=Path)
    args = parser.parse_args()
    if args.step in {"prepare", "publish"} and args.source_epub is None:
        parser.error("--source-epub is required")
    if args.step == "prepare":
        prepare(args.output, args.source_epub)
    elif args.step == "synthesize":
        if any(v is None for v in (args.model, args.voice_dir, args.chunk_helper)):
            parser.error("synthesize requires --model, --voice-dir, --chunk-helper")
        importlib.import_module("issue14_synthesis").synthesize(
            args.output, args.model, args.voice_dir, args.chunk_helper
        )
    else:
        publish(args.output, args.source_epub)


if __name__ == "__main__":
    main()
