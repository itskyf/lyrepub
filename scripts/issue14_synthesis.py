"""Run Issue #14 cases through audio.cpp's VieNeu v3 Turbo CUDA route."""

import hashlib
import importlib.metadata
import json
import logging
import wave
from array import array
from pathlib import Path

from issue14_feasibility import load_records, ogg_duration, run_tool, save_records
from sea_g2p import SEAPipeline

LOGGER = logging.getLogger(__name__)
IMAGE = (
    "localhost/audio.cpp@sha256:"
    "b881a557d10c435690b12894315b33dfeff22a61f833e6c55331f510ce99282d"
)
IMAGE_REVISION = "955c8725c611d511774e6be132aff6609163b2d2"
CHECKPOINT_REVISION = "61b85e3d937fbbacb387714180e8182823512523"
CHECKPOINT_SHA256 = "c9c23d51989382e27730077c2373023bcfb0891db63a1efec97fd73b4bd6b7dc"
VOICE_SHA256 = {
    "ref_codes.txt": (
        "9d084951e34f7c2d3cf7c6bb0f2fbcdc6e61e1e369bb0dfed1c2874077ca6bad"
    ),
    "speaker.emb.txt": (
        "aae1818cda77c25d6ccd39c64387695b895fa5e85c7b279205fea744fb95a400"
    ),
}
SHOUT_SOURCE = "S…át Th.. át!"
SHOUT_INPUT = "Sát Thát!"
SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLE_WIDTH = 2


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chunk_trace(helper: Path, phonemes: str) -> list[dict]:
    stdout, _ = run_tool([str(helper)], input_text=phonemes)
    return [
        {"gap_before": gap, "phonemes": chunk}
        for gap, chunk in (line.split("\t", 1) for line in stdout.splitlines())
    ]


def joined_chunk_times(wav: Path, dump: Path, chunk_count: int) -> list[float]:
    """Locate audio.cpp's zero-padded seams from generated frame counts."""
    frames = [
        int(line.split()[1])
        for line in dump.read_text().splitlines()
        if line.startswith("generated_codes ")
    ]
    if len(frames) != chunk_count:
        message = f"audio.cpp synthesized {len(frames)} chunks; traced {chunk_count}"
        raise RuntimeError(message)
    with wave.open(str(wav)) as audio:
        if (
            audio.getframerate() != SAMPLE_RATE
            or audio.getnchannels() != CHANNELS
            or audio.getsampwidth() != SAMPLE_WIDTH
        ):
            message = "unexpected audio.cpp WAV format"
            raise RuntimeError(message)
        samples = array("h", audio.readframes(audio.getnframes()))
        total = audio.getnframes()
    position = 0
    joins = []
    for frame_count in frames[:-1]:
        position += frame_count * 3840
        while (
            position < total and samples[2 * position] == samples[2 * position + 1] == 0
        ):
            position += 1
        joins.append(position / SAMPLE_RATE)
    if position + frames[-1] * 3840 != total:
        message = "chunk frame and WAV timeline differ"
        raise RuntimeError(message)
    return joins


def synthesize(
    output: Path, model: Path, voice_dir: Path, chunk_helper: Path, image: str = IMAGE
) -> None:
    """Synthesize prepared cases, retaining source, frontend, and chunk evidence."""
    model = model.resolve()
    voice_dir = voice_dir.resolve()
    output = output.resolve()
    required = validate_inputs(model, voice_dir, chunk_helper)
    output.joinpath("audio").mkdir(parents=True, exist_ok=True)
    output.joinpath("traces").mkdir(exist_ok=True)
    settings = runtime_settings(model, required, image)
    output.joinpath("runtime.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    records = load_records(output)
    frontend = SEAPipeline(lang="vi")
    for record in records:
        source_text = record["source"]["text"]
        text_input = source_text
        if record["key"] == "s17-b135":
            if source_text.count(SHOUT_SOURCE) != 1:
                message = "expected one elongated Sát Thát cry"
                raise ValueError(message)
            text_input = source_text.replace(SHOUT_SOURCE, SHOUT_INPUT)
            record["intervention"] = {
                "type": "TTS input only",
                "source": SHOUT_SOURCE,
                "replacement": SHOUT_INPUT,
            }
        record["tts_input"] = text_input
        try:
            normalized = frontend.normalizer.normalize(text_input, punc_norm=False)
            phonemes = frontend.g2p.convert(normalized)
            chunks = chunk_trace(chunk_helper, phonemes)
            if not chunks:
                message = "audio.cpp produced no synthesis chunks"
                raise ValueError(message)
            record["phonemes"] = phonemes
            record["normalized_text"] = normalized
            record["chunks"] = chunks
            record["status"] = "preprocessed"
            save_records(output, records)
            seed = (
                14
                + record["source"]["spine_index"] * 1000
                + record["source"]["block_index"]
            )
            record["seed"] = seed
            run_audio_cpp(output, model, voice_dir, image, record)
        except (OSError, ValueError, RuntimeError) as exc:
            record["status"] = (
                "preprocessing_failure"
                if record.get("status") != "preprocessed"
                else "synthesis_failure"
            )
            record["error"] = f"{type(exc).__name__}: {exc}"
        save_records(output, records)
        LOGGER.info("%s: %s", record["key"], record["status"])
    listening_clips(output, records)


def validate_inputs(model: Path, voice_dir: Path, chunk_helper: Path) -> list[Path]:
    required = [model, voice_dir / "ref_codes.txt", voice_dir / "speaker.emb.txt"]
    if any(not path.is_file() for path in required):
        message = f"missing audio.cpp model or Thục Đoan assets: {required}"
        raise FileNotFoundError(message)
    if sha256(model) != CHECKPOINT_SHA256 or any(
        sha256(path) != VOICE_SHA256[path.name] for path in required[1:]
    ):
        message = "checkpoint or Thục Đoan assets differ from the feasibility pin"
        raise ValueError(message)
    if importlib.metadata.version("sea-g2p") != "0.9.1":
        message = "this feasibility run requires sea-g2p 0.9.1"
        raise ValueError(message)
    if not chunk_helper.is_file():
        message = f"missing pinned audio.cpp chunk helper: {chunk_helper}"
        raise FileNotFoundError(message)
    return required


def runtime_settings(model: Path, required: list[Path], image: str) -> dict:
    return {
        "runtime": "audio.cpp",
        "image": image,
        "image_revision": IMAGE_REVISION,
        "checkpoint": f"pnnbao-ump/VieNeu-TTS-v3-Turbo@{CHECKPOINT_REVISION}",
        "checkpoint_precision": "BF16 talker, F16 codec",
        "checkpoint_sha256": sha256(model),
        "voice": "Thục Đoan",
        "voice_assets_sha256": {path.name: sha256(path) for path in required[1:]},
        "frontend": (
            f"sea-g2p {importlib.metadata.version('sea-g2p')} "
            "SEAPipeline(vi), punc_norm=False"
        ),
        "backend": "cuda",
        "seed_per_block": "14 + source spine index * 1000 + block index",
        "sampling": {
            "temperature": 0.8,
            "top_k": 25,
            "top_p": 0.95,
            "repetition_penalty": 1.2,
            "repetition_window": 64,
            "max_tokens": 300,
            "frame_cap": True,
            "do_sample": True,
            "babble_retries": 2,
        },
        "audio_cpp_chunking": {
            "text_chunk_size": 200,
            "text_chunk_min": 20,
            "budget_units": "UTF-8 bytes of phonemes in the pinned C++ implementation",
        },
        "audio_cpp_minimum_pauses_seconds": {
            "paragraph": 0.7,
            "sentence": 0.5,
            "minor": 0.3,
        },
    }


def run_audio_cpp(
    output: Path, model: Path, voice_dir: Path, image: str, record: dict
) -> None:
    """Generate and package one already-phonemized source target."""
    phonemes = record["phonemes"]
    chunks = record["chunks"]
    seed = record["seed"]
    dump = output / "traces" / f"{record['key']}.codes"
    dump.unlink(missing_ok=True)
    name = record["key"]
    command = [
        "podman",
        "run",
        "--rm",
        "--user",
        "0",
        "--security-opt",
        "label=disable",
        "--device",
        "nvidia.com/gpu=all",
        "-v",
        f"{model}:/inputs/model.gguf:ro",
        "-v",
        f"{voice_dir}:/inputs/voice:ro",
        "-v",
        f"{output}:/output",
        image,
        "cli",
        "--task",
        "tts",
        "--family",
        "vieneu_v3_turbo",
        "--model",
        "/inputs/model.gguf",
        "--backend",
        "cuda",
        "--text",
        phonemes,
        "--seed",
        str(seed),
        "--request-option",
        "reference_codes_file=/inputs/voice/ref_codes.txt",
        "--request-option",
        "speaker_embedding_file=/inputs/voice/speaker.emb.txt",
        "--request-option",
        f"codes_dump_file=/output/traces/{name}.codes",
        "--out",
        f"/output/audio/{name}.wav",
    ]
    record["command"] = [
        part.replace(str(model), "<model>")
        .replace(str(voice_dir), "<voice-dir>")
        .replace(str(output), "<output>")
        for part in command
    ]
    stdout, stderr = run_tool(command)
    (output / "traces" / f"{name}.log").write_text(stdout + stderr, encoding="utf-8")
    wav = output / "audio" / f"{name}.wav"
    if not wav.is_file() or wav.stat().st_size == 0:
        message = "audio.cpp returned no audio"
        raise RuntimeError(message)
    record["join_seconds"] = joined_chunk_times(wav, dump, len(chunks))
    ogg = output / "audio" / f"{name}.ogg"
    run_tool(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(wav),
            "-c:a",
            "libopus",
            "-b:a",
            "96k",
            str(ogg),
        ]
    )
    if not ogg.is_file() or ogg.stat().st_size == 0:
        message = "Opus packaging returned no audio"
        raise RuntimeError(message)
    record["audio"] = f"audio/{name}.wav"
    record["packaged_audio"] = f"audio/{name}.ogg"
    record["duration_seconds"] = str(ogg_duration(ogg))
    record["status"] = "ok"


def listening_clips(output: Path, records: list[dict]) -> None:
    """Make short listening excerpts at measured long-block synthesis seams."""
    record = next(r for r in records if r["key"] == "s5-b9")
    if record.get("status") != "ok":
        return
    output.joinpath("joins").mkdir(exist_ok=True)
    clips = []
    for index in (0, len(record["join_seconds"]) // 2, len(record["join_seconds"]) - 1):
        seam = record["join_seconds"][index]
        start = max(0, seam - 4)
        end = min(float(record["duration_seconds"]), seam + 4)
        filename = f"joins/s5-b9-join-{index + 1:02}.ogg"
        run_tool(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(output / record["packaged_audio"]),
                "-t",
                str(end - start),
                "-c:a",
                "libopus",
                "-b:a",
                "96k",
                str(output / filename),
            ]
        )
        clips.append(
            {
                "path": filename,
                "start_seconds": start,
                "end_seconds": end,
                "join_seconds": seam,
            }
        )
    output.joinpath("clips.json").write_text(
        json.dumps(clips, indent=2) + "\n", encoding="utf-8"
    )
