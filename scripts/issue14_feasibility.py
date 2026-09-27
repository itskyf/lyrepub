"""Generate Issue #14 TTS listening evidence and a paragraph-overlay EPUB.

Run ``prepare`` and ``publish`` with the LyrePub Pixi Python; run ``synthesize``
with the pinned VieNeu environment. Outputs live in gitignored data/.
"""

import argparse
import copy
import hashlib
import importlib
import json
import logging
import zipfile
from datetime import UTC, datetime
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
SAMPLE_RATE = 48_000
MODEL_REVISION = "61b85e3d937fbbacb387714180e8182823512523"
CODEC_REVISION = "6aa02b01e445cc585582cf0ba480bc3ea6c8dd68"
LOGGER = logging.getLogger(__name__)


def key(spine_index: int, block_index: int) -> str:
    return f"s{spine_index}-b{block_index}"


def main_worktree() -> Path:
    pointer = (Path(__file__).resolve().parents[1] / ".git").read_text()
    gitdir = Path(pointer.removeprefix("gitdir: ").strip())
    root = gitdir.parents[2]
    if not (root / "data" / "bronze" / ISBN).is_dir():
        message = "main worktree source data not found"
        raise FileNotFoundError(message)
    return root


def load_records(output: Path) -> list[dict]:
    return json.loads((output / "cases.json").read_text(encoding="utf-8"))


def save_records(output: Path, records: list[dict]) -> None:
    (output / "cases.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def prepare(output: Path) -> None:
    extract_blocks = importlib.import_module("lyrepub.epub_text").extract_blocks

    source = next((main_worktree() / "data" / "bronze" / ISBN).glob("*.epub"))
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
                "path": str(source),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def chunk_offsets(lengths: list[int], pads: list[int]) -> list[int]:
    if len(pads) != max(0, len(lengths) - 1):
        message = "one gap is required between adjacent chunks"
        raise ValueError(message)
    offsets = [0]
    for length, pad in zip(lengths[:-1], pads, strict=True):
        offsets.append(offsets[-1] + length + pad)
    return offsets


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


def overlay_assets(output: Path, records: dict[str, dict]) -> tuple[dict, list, float]:
    source = Path(
        json.loads((output / "source.json").read_text(encoding="utf-8"))["path"]
    )
    ET.register_namespace("", XHTML)
    assets = {}
    duration_total = 0.0
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
        duration = 0.0
        for r in selected:
            case_key = r["key"]
            mp3 = output / "audio" / f"{case_key}.mp3"
            seconds = r["duration_seconds"]
            assets[f"EPUB/Audio/{case_key}.mp3"] = mp3.read_bytes()
            par = ET.SubElement(body, f"{{{SMIL}}}par", {"id": f"par-{case_key}"})
            ET.SubElement(
                par, f"{{{SMIL}}}text", {"src": f"../Text/{name}.xhtml#{case_key}"}
            )
            ET.SubElement(par, f"{{{SMIL}}}audio", {"src": f"../Audio/{case_key}.mp3"})
            duration += seconds
        assets[f"EPUB/Overlays/{name}.smil"] = ET.tostring(
            smil, encoding="utf-8", xml_declaration=True
        )
        spine.append((name, title, duration))
        duration_total += duration
    return assets, spine, duration_total


def publish(output: Path) -> None:
    records = {r["key"]: r for r in load_records(output)}
    missing = [
        key(s, b) for s, b in PLAYBACK if records[key(s, b)].get("status") != "ok"
    ]
    if missing:
        message = f"cannot publish without playback audio: {missing}"
        raise RuntimeError(message)
    assets, spine, duration_total = overlay_assets(output, records)
    assets["EPUB/Styles/overlay.css"] = (
        b".-epub-media-overlay-active { background: #ffe07a; color: #111; }\n"
    )
    nav = ET.Element(f"{{{XHTML}}}html", {"lang": "vi"})
    ET.SubElement(
        ET.SubElement(nav, f"{{{XHTML}}}head"), f"{{{XHTML}}}title"
    ).text = "Mục lục"
    body = ET.SubElement(nav, f"{{{XHTML}}}body")
    toc = ET.SubElement(body, f"{{{XHTML}}}nav", {f"{{{EPUB}}}type": "toc"})
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
                    "href": f"Audio/{r['key']}.mp3",
                    "media-type": "audio/mpeg",
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare", "synthesize", "publish"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/issue-14-feasibility")
    )
    args = parser.parse_args()
    if args.step == "prepare":
        prepare(args.output)
    elif args.step == "synthesize":
        importlib.import_module("issue14_synthesis").synthesize(args.output)
    else:
        publish(args.output)


if __name__ == "__main__":
    main()
