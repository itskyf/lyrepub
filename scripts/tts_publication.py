#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#   "defusedxml>=0.7.1,<0.8", "fast-ebook>=0.2.0,<0.3", "numpy", "soundfile",
#   "vieneu==3.8.3", "sea-g2p==0.10.0", "wtpsplit==2.2.2",
#   "transformers[torch]==5.17.0", "zapros[pyreqwest]==0.19.0",
# ]
# ///
"""Build the full TTS publication using the existing frozen sentence path."""

import argparse
import asyncio
import json
import logging
import posixpath
from collections import defaultdict
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from xml.etree.ElementTree import tostring
from zipfile import ZipFile

from defusedxml import ElementTree

from lyrepub.audio import ogg_duration
from lyrepub.epub_text import extract_blocks, materialize_sentence_targets
from lyrepub.media_overlays import Timing, publish_media_overlays
from lyrepub.segmentation import segment_sentences
from scripts.publication import correct_tts_source, publication_metadata, repair
from scripts.tts_synthesis import (
    MANUAL_NORMALIZATIONS,
    normalize_slash_enumeration,
    prepare_sentences,
    sha256,
    synthesize_records,
)

LOGGER = logging.getLogger(__name__)


def load_records(output: Path) -> list[dict]:
    return json.loads((output / "sentences.json").read_text())


def save_records(output: Path, records: list[dict]) -> None:
    (output / "sentences.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    )


def prepare(source: Path, output: Path) -> None:
    """Prepare all readable source blocks without storing duplicate block text."""
    if (output / "sentences.json").exists():
        raise FileExistsError(output / "sentences.json")
    output.mkdir(parents=True, exist_ok=True)
    corrected = output / "corrected-source.epub"
    correct_tts_source(source, corrected)
    records = []
    bronze_blocks = [
        block
        for block in extract_blocks(source)
        if (block.href, block.text)
        not in {("Text/1.html", "V"), ("Text/12.html", '"P')}
    ]
    for original, block in zip(bronze_blocks, extract_blocks(corrected), strict=True):
        expected_text = (
            original.text.replace('"P hú', '"Phú', 1)
            if original.href == "Text/12.html"
            else original.text
        )
        if original.href != block.href or expected_text != block.text:
            message = "final source differs beyond reviewed corrections"
            raise ValueError(message)
        location = asdict(block)
        location.pop("text")
        manual = MANUAL_NORMALIZATIONS.get((block.spine_index, block.block_index))
        treated = normalize_slash_enumeration(block.text)
        authored = segment_sentences(block.text)
        join = {(17, 24): (6, 7), (23, 37): (1, 2), (23, 172): (1, 2)}.get(
            (block.spine_index, block.block_index)
        )
        if join:
            left, right = join
            expected = {(17, 24): ")", (23, 37): "-", (23, 172): '"'}[
                block.spine_index, block.block_index
            ]
            punctuation = left if expected == "-" else right
            if authored[punctuation] != expected:
                message = "reviewed punctuation target differs from source"
                raise ValueError(message)
            cursor = 0
            for previous in authored[:left]:
                cursor = block.text.index(previous, cursor) + len(previous)
            start = block.text.index(authored[left], cursor)
            end = block.text.index(authored[right], start + len(authored[left])) + len(
                authored[right]
            )
            authored[left : right + 1] = [block.text[start:end]]
        try:
            sentences = prepare_sentences(block.text, treated, authored, manual)
        except ValueError as exc:
            records.append(
                {
                    "key": f"s{block.spine_index}-b{block.block_index}",
                    "source": location,
                    "status": "preprocessing_failure",
                    "error": str(exc),
                    "sentences": [],
                }
            )
            LOGGER.error("%s: %s", records[-1]["key"], exc)
            continue
        record = {
            "key": f"s{block.spine_index}-b{block.block_index}",
            "source": location,
            "bronze_block_index": original.block_index,
            "seed": 14 + original.spine_index * 1000 + original.block_index,
            "sentences": sentences,
            "status": "preprocessed",
            "interventions": [],
        }
        if join:
            record["interventions"].append(
                "reviewed source-preserving punctuation boundary join"
            )
        if treated != block.text:
            record["interventions"].append(
                "ordered slash enumeration: marker slash -> comma"
            )
        if manual:
            record["manual_normalization"] = manual
            record["interventions"].append(
                f"manual TTS normalization: {manual['source_span']} "
                f"-> {manual['tts_text']}"
            )
        records.append(record)
    save_records(output, records)
    (output / "source.json").write_text(
        json.dumps(
            {
                "filename": source.name,
                "sha256": sha256(source),
                "corrected_sha256": sha256(corrected),
            },
            indent=2,
        )
        + "\n"
    )


def synthesize(output: Path, model: Path, voice: Path, concurrency: int = 1) -> None:
    """Resume completed blocks through the Compose audio.cpp server."""
    records = load_records(output)
    asyncio.run(
        synthesize_records(
            output,
            (model.resolve(), voice.resolve()),
            records,
            concurrency,
            filename="sentences.json",
        )
    )


def _prepared_source(source: Path, output: Path) -> Path:
    provenance = json.loads((output / "source.json").read_text())
    if sha256(source) != provenance["sha256"]:
        msg = "source EPUB differs from prepared source"
        raise ValueError(msg)
    source = output / "corrected-source.epub"
    if sha256(source) != provenance["corrected_sha256"]:
        message = "corrected source EPUB differs from prepared source"
        raise ValueError(message)
    return source


def publish(source: Path, output: Path) -> None:
    """Materialize original source ranges and publish measured sentence audio."""
    source = _prepared_source(source, output)
    blocks = {(b.spine_index, b.block_index): b for b in extract_blocks(source)}
    records = load_records(output)
    identities = [
        (r["source"]["spine_index"], r["source"]["block_index"]) for r in records
    ]
    if len(set(identities)) != len(records) or set(identities) != set(blocks):
        msg = "publication records do not cover source blocks exactly"
        raise ValueError(msg)
    documents = defaultdict(list)
    for record, identity in zip(records, identities, strict=True):
        if record["status"] != "ok":
            msg = f"incomplete synthesis: {record['key']}"
            raise ValueError(msg)
        block = blocks[identity]
        location = {
            name: value for name, value in asdict(block).items() if name != "text"
        }
        location["element_path"] = list(location["element_path"])
        if location != record["source"]:
            msg = "source location drift"
            raise ValueError(msg)
        cursor = 0
        for sentence in record["sentences"]:
            start, end = sentence["source_start"], sentence["source_end"]
            if start < cursor or block.text[cursor:start].strip():
                msg = "sentence coverage gap or overlap"
                raise ValueError(msg)
            cursor = end
            documents[block.href].append((block, sentence))
        if not record["sentences"] or block.text[cursor:].strip():
            msg = "incomplete sentence coverage"
            raise ValueError(msg)
    edits, timings, audio = {}, [], {}
    work = output / "work"
    work.mkdir(exist_ok=True)
    with ZipFile(source) as archive:
        opf = next(name for name in archive.namelist() if name.endswith(".opf"))
        package = ElementTree.fromstring(archive.read(opf))
        publication_metadata(package, "tts")
        edits[opf] = tostring(package, encoding="utf-8", xml_declaration=True)
        for href, rows in documents.items():
            path = posixpath.join(posixpath.dirname(opf), href)
            edits[path], hrefs = materialize_sentence_targets(
                archive.read(path),
                [
                    (
                        b,
                        s["index"],
                        s["source_start"],
                        s["source_end"],
                        s["source_text"],
                    )
                    for b, s in rows
                ],
            )
            for target, (_, sentence) in zip(hrefs, rows, strict=True):
                audio_path = output / sentence["packaged_audio"]
                if (
                    not audio_path.resolve().is_relative_to(output.resolve())
                    or sentence["packaged_audio"] in audio
                    or Decimal(sentence["clip_begin"]) != 0
                    or Decimal(sentence["clip_end"]) != ogg_duration(audio_path)
                ):
                    message = "sentence audio reference or measured timing drift"
                    raise ValueError(message)
                audio[sentence["packaged_audio"]] = audio_path
                timings.append(
                    Timing(
                        target,
                        sentence["packaged_audio"],
                        timedelta(
                            microseconds=int(Decimal(sentence["clip_begin"]) * 1000000)
                        ),
                        timedelta(
                            microseconds=int(Decimal(sentence["clip_end"]) * 1000000)
                        ),
                    )
                )
        targeted = work / "targeted.epub"
        with ZipFile(targeted, "w") as result:
            for info in archive.infolist():
                result.writestr(
                    info, edits.get(info.filename, archive.read(info.filename))
                )
    overlaid = work / "overlaid.epub"
    publish_media_overlays(targeted, overlaid, timings, audio)
    repair(overlaid, output / "final.epub", "tts")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare", "synthesize", "publish"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--voice", type=Path)
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()
    if args.concurrency <= 0:
        parser.error("--concurrency must be positive")
    logging.basicConfig(level=logging.INFO)
    if args.step == "synthesize":
        if not args.model or not args.voice:
            parser.error("synthesize requires --model and --voice")
        synthesize(args.output, args.model, args.voice, args.concurrency)
    else:
        if not args.source:
            parser.error("prepare/publish require --source")
        if args.step == "prepare":
            prepare(args.source, args.output)
        else:
            publish(args.source, args.output)


if __name__ == "__main__":
    main()
