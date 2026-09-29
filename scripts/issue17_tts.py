"""Build the full TTS publication using the existing frozen sentence path."""

import argparse
import json
import logging
import posixpath
import tempfile
from collections import defaultdict
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import soundfile as sf
from vieneu_utils.core_utils import gaps_to_silence, join_audio_chunks

from lyrepub.epub_text import extract_blocks, materialize_sentence_targets
from lyrepub.media_overlays import Timing, publish_media_overlays
from lyrepub.segmentation import segment_sentences
from scripts.issue14_feasibility import (
    MANUAL_NORMALIZATIONS,
    key,
    load_records,
    normalize_slash_enumeration,
    ogg_duration,
    run_tool,
    save_records,
)
from scripts.issue14_synthesis import (
    audio_cpp_command,
    inspect_image,
    package_audio,
    prepare_sentences,
    runtime_settings,
    sha256,
    validate_inputs,
)
from scripts.issue17_publication import repair

LOGGER = logging.getLogger(__name__)


def prepare(source: Path, output: Path) -> None:
    """Prepare all readable source blocks without storing duplicate block text."""
    if (output / "cases.json").exists():
        raise FileExistsError(output / "cases.json")
    records = []
    for block in extract_blocks(source):
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
                    "key": key(block.spine_index, block.block_index),
                    "source": location,
                    "status": "preprocessing_failure",
                    "error": str(exc),
                    "sentences": [],
                }
            )
            LOGGER.error("%s: %s", records[-1]["key"], exc)
            continue
        record = {
            "key": key(block.spine_index, block.block_index),
            "source": location,
            "seed": 14 + block.spine_index * 1000 + block.block_index,
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
        if treated != block.text or manual:
            record["raw_frontend"] = prepare_sentences(
                block.text, block.text, [s["source_text"] for s in sentences]
            )
        records.append(record)
    output.mkdir(parents=True, exist_ok=True)
    save_records(output, records)
    (output / "source.json").write_text(
        json.dumps({"filename": source.name, "sha256": sha256(source)}, indent=2) + "\n"
    )


def synthesize(output: Path, model: Path, voice: Path, image: str) -> None:
    """Resume completed blocks, retaining failures and stopping immediately."""
    output, model, voice = output.resolve(), model.resolve(), voice.resolve()
    settings = runtime_settings(
        model, validate_inputs(model, voice), inspect_image(image)
    )
    settings["purpose"] = "Issue #17 full publication"
    settings.pop("sentence_join")
    settings["execution"] = (
        "native CLI request-sequence, grouped by source spine; seed reset per chunk"
    )
    runtime = output / "runtime.json"
    if runtime.exists() and json.loads(runtime.read_text()) != settings:
        msg = "runtime differs from existing publication synthesis"
        raise ValueError(msg)
    runtime.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
    (output / "audio").mkdir(exist_ok=True)
    (output / "traces").mkdir(exist_ok=True)
    records = load_records(output)
    failures = [r["key"] for r in records if r["status"] == "preprocessing_failure"]
    if failures:
        message = f"unresolved preprocessing failures: {failures}"
        raise ValueError(message)
    chapters = defaultdict(list)
    for record in records:
        if record["status"] != "ok":
            chapters[record["source"]["spine_index"]].append(record)
    for spine_index, chapter in chapters.items():
        try:
            _synthesize_chapter(output, (model, voice, image), chapter)
        except (OSError, ValueError, RuntimeError) as exc:
            for record in chapter:
                record["status"] = "synthesis_failure"
                record["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            save_records(output, records)
        LOGGER.info("spine %s complete", spine_index)


def _synthesize_chapter(
    output: Path, assets: tuple[Path, Path, str], records: list[dict]
) -> None:
    model, voice, image = assets
    requests = []
    for record in records:
        for sentence in record["sentences"]:
            for index, chunk in enumerate(sentence["chunks"]):
                phonemes = chunk["phonemes"]
                if not phonemes.strip() or "\n" in phonemes:
                    message = "prepared request must contain one phoneme paragraph"
                    raise ValueError(message)
                chunk["key"] = f"{record['key']}-s{sentence['index']:03d}-c{index:02d}"
                chunk["seed"] = record["seed"]
                chunk["text_chunk_size_bytes"] = len(phonemes.encode("utf-8"))
                chunk["audio"] = f"audio/{chunk['key']}.wav"
                requests.append(
                    {
                        "id": chunk["key"],
                        "text": phonemes,
                        "seed": chunk["seed"],
                        "options": {
                            "text_chunk_size": str(chunk["text_chunk_size_bytes"]),
                            "reference_codes_file": "/inputs/voice/ref_codes.txt",
                            "speaker_embedding_file": "/inputs/voice/speaker.emb.txt",
                        },
                    }
                )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=output / "traces"
    ) as sequence:
        json.dump(requests, sequence, ensure_ascii=False)
        sequence.flush()
        command = [
            *audio_cpp_command(output, model, voice, image),
            "--request-sequence",
            f"/output/traces/{Path(sequence.name).name}",
            "--out-dir",
            "/output/audio",
            "--batch-manifest-out",
            f"/output/traces/spine-{records[0]['source']['spine_index']}.json",
        ]
        stdout, stderr = run_tool(command)
        (
            output / "traces" / f"spine-{records[0]['source']['spine_index']}.log"
        ).write_text(stdout + stderr)
    for record in records:
        for sentence in record["sentences"]:
            parts, rate = [], None
            for chunk in sentence["chunks"]:
                pcm, current_rate = sf.read(
                    output / chunk["audio"], dtype="float32", always_2d=True
                )
                if rate is not None and current_rate != rate:
                    message = "inconsistent PCM sample rates"
                    raise ValueError(message)
                rate = current_rate
                parts.append(pcm.mean(axis=1))
            pcm = join_audio_chunks(
                parts, rate, silence_ps=gaps_to_silence(sentence["gaps"])
            )
            name = f"case={record['key']},sentence={sentence['index']:03d}"
            sentence.update(package_audio(output, name, pcm, rate))
        record["status"] = "ok"
        record.pop("error", None)


def publish(source: Path, output: Path) -> None:
    """Materialize original source ranges and publish measured sentence audio."""
    provenance = json.loads((output / "source.json").read_text())
    if sha256(source) != provenance["sha256"]:
        msg = "source EPUB differs from prepared source"
        raise ValueError(msg)
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
        location = asdict(block)
        location.pop("text")
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
    with ZipFile(source) as archive:
        opf = next(name for name in archive.namelist() if name.endswith(".opf"))
        for href, rows in documents.items():
            path = posixpath.join(posixpath.dirname(opf), href)
            targets = [
                (b, s["index"], s["source_start"], s["source_end"], s["source_text"])
                for b, s in rows
            ]
            edits[path], hrefs = materialize_sentence_targets(
                archive.read(path), targets
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
        targeted = output / "targeted.epub"
        with ZipFile(targeted, "w") as result:
            for info in archive.infolist():
                result.writestr(
                    info, edits.get(info.filename, archive.read(info.filename))
                )
    # Repair after targeting so source locations always describe the original EPUB.
    staged = output / "publication-source.epub"
    repair(targeted, staged, "tts")
    publish_media_overlays(staged, output / "final.epub", timings, audio)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare", "synthesize", "publish"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--voice", type=Path)
    parser.add_argument("--image", default="localhost/audio.cpp:full-cuda13")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.step == "synthesize":
        if not args.model or not args.voice:
            parser.error("synthesize requires --model and --voice")
        synthesize(args.output, args.model, args.voice, args.image)
    else:
        if not args.source:
            parser.error("prepare/publish require --source")
        if args.step == "prepare":
            prepare(args.source, args.output)
        else:
            publish(args.source, args.output)


if __name__ == "__main__":
    main()
