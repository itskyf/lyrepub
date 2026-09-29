"""Run Issue #14 cases through audio.cpp's VieNeu v3 Turbo CUDA route."""

import hashlib
import importlib.metadata
import json
import logging
from pathlib import Path

import numpy as np
import soundfile as sf
from vieneu_utils.core_utils import gaps_to_silence, join_audio_chunks
from vieneu_utils.phonemize_text import (
    normalize_to_chunks_v3_with_gaps,
    phonemize_text_with_emotions,
)

from lyrepub.segmentation import (
    SAT_NAME,
    SAT_REVISION,
    TOKENIZER_NAME,
    TOKENIZER_REVISION,
    segment_sentences,
)
from scripts.issue14_feasibility import (
    load_records,
    normalize_slash_enumeration,
    ogg_duration,
    run_tool,
    save_records,
)

LOGGER = logging.getLogger(__name__)
AUDIOCPP_REVISION = "955c8725c611d511774e6be132aff6609163b2d2"
VIENEU_REVISION = "c1390abbdb2eedcdf58eafb546966c06ce27af71"
SEA_REVISION = "dae5ca83ea45f356c43bdb70a1bcd42e8729ff16"
DICTIONARY_SHA256 = "4346e690d0711ebc5231e7a42c5c88aaf6e40377e894b4617c018fd81c6f4096"
CHECKPOINT_REVISION = "61b85e3d937fbbacb387714180e8182823512523"
CHECKPOINT_SHA256 = "c9c23d51989382e27730077c2373023bcfb0891db63a1efec97fd73b4bd6b7dc"
VOICE_SHA256 = {
    "ref_codes.txt": (
        "363b2eee93aeca4f789e1ce63ad904d7e0bef88bb20c830dd2e559ea3fe0054a"
    ),
    "speaker.emb.txt": (
        "ab66bc624b0ffaa735c8ece1aa71b12f18b48bddc2e7cd27ba9eec3d85c2bce9"
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthesize(
    output: Path,
    model: Path,
    voice_dir: Path,
    image: str,
) -> None:
    """Synthesize prepared cases with separate preprocessing and runtime evidence."""
    model = model.resolve()
    voice_dir = voice_dir.resolve()
    output = output.resolve()
    image_info = inspect_image(image)
    required = validate_inputs(model, voice_dir)
    output.joinpath("audio").mkdir(parents=True, exist_ok=True)
    output.joinpath("traces").mkdir(exist_ok=True)
    settings = runtime_settings(model, required, image_info)
    output.joinpath("runtime.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    records = load_records(output)
    selected = [record for record in records if record.get("status") != "ok"]
    for record in selected:
        record.pop("error", None)
        try:
            text_input = normalize_slash_enumeration(record["source"]["text"])
            record["interventions"] = (
                ["ordered slash enumeration: marker slash -> comma"]
                if text_input != record["source"]["text"]
                else []
            )
            manual = record.get("manual_normalization")
            if manual:
                record["interventions"].append(
                    f"manual TTS normalization: {manual['source_span']} "
                    f"-> {manual['tts_text']}"
                )
            record["sentences"] = prepare_sentences(
                record["source"]["text"],
                text_input,
                segment_sentences(record["source"]["text"]),
                manual,
            )
            record["raw_frontend"] = prepare_sentences(
                record["source"]["text"],
                record["source"]["text"],
                [sentence["source_text"] for sentence in record["sentences"]],
            )
            record["status"] = "preprocessed"
            save_records(output, records)
            seed = (
                14
                + record["source"]["spine_index"] * 1000
                + record["source"]["block_index"]
            )
            record["seed"] = seed
            synthesize_sentences(output, model, voice_dir, image, record)
        except (OSError, ValueError, RuntimeError) as exc:
            record["status"] = (
                "preprocessing_failure"
                if record.get("status") != "preprocessed"
                else "synthesis_failure"
            )
            record["error"] = f"{type(exc).__name__}: {exc}"
        save_records(output, records)
        LOGGER.info("%s: %s", record["key"], record["status"])


def prepare_sentences(
    source: str,
    text_input: str,
    sentences: list[str],
    manual_normalization: dict[str, str] | None = None,
) -> list[dict]:
    """Map authored sentences to upstream normalized synthesis chunks without loss.

    Apply explicit manual TTS normalization after locating authored offsets.
    """
    if len(source) != len(text_input):
        message = "enumeration treatment must preserve source offsets"
        raise ValueError(message)
    if (
        manual_normalization
        and text_input.count(manual_normalization["source_span"]) != 1
    ):
        message = "manual normalization requires exactly one observed source span"
        raise ValueError(message)
    result = []
    cursor = 0
    manual_applied = False
    for index, sentence in enumerate(sentences):
        start = source.find(sentence, cursor)
        if start < 0 or source[cursor:start].strip():
            message = "sentence segmentation lost or changed authored text"
            raise ValueError(message)
        end = start + len(sentence)
        prepared = text_input[start:end]
        if manual_normalization and manual_normalization["source_span"] in prepared:
            prepared = prepared.replace(
                manual_normalization["source_span"], manual_normalization["tts_text"]
            )
            manual_applied = True
        chunks, gaps = normalize_to_chunks_v3_with_gaps(prepared)
        if not chunks or any(not chunk.strip() for chunk in chunks):
            message = f"frontend produced empty synthesis input: {sentence!r}"
            raise ValueError(message)
        result.append(
            {
                "index": index,
                "source_start": start,
                "source_end": end,
                "source_text": sentence,
                "tts_input": prepared,
                "gaps": gaps,
                "chunks": [
                    {
                        "normalized_text": chunk,
                        "phonemes": phonemize_text_with_emotions(chunk),
                    }
                    for chunk in chunks
                ],
            }
        )
        cursor = end
    if manual_normalization and not manual_applied:
        message = "observed manual-normalization span crosses sentence targets"
        raise ValueError(message)
    if source[cursor:].strip() or not result:
        message = "sentence segmentation left authored text uncovered"
        raise ValueError(message)
    return result


def frontend_identity() -> dict:
    versions = {
        name: importlib.metadata.version(name) for name in ("vieneu", "sea-g2p")
    }
    if versions != {"vieneu": "3.8.3", "sea-g2p": "0.10.0"}:
        message = "frontend packages differ from the feasibility pins"
        raise ValueError(message)
    dictionary = importlib.metadata.distribution("sea-g2p").locate_file(
        "sea_g2p/sea_g2p.bin"
    )
    digest = sha256(Path(dictionary))
    if digest != DICTIONARY_SHA256:
        message = "SEA-G2P dictionary differs from the feasibility pin"
        raise ValueError(message)
    return {
        "versions": versions,
        "vieneu_revision": VIENEU_REVISION,
        "sea_g2p_revision": SEA_REVISION,
        "dictionary_sha256": digest,
        "normalization": "upstream Vietnamese SEA-G2P",
        "chunking": {"max_chars": 256, "min_chunk_chars": 20},
        "phonemization": "upstream phonemize_text_with_emotions",
    }


def inspect_image(image: str) -> dict:
    stdout, _ = run_tool(["podman", "image", "inspect", image])
    metadata = json.loads(stdout)[0]
    revision = metadata["Config"]["Labels"]["org.opencontainers.image.revision"]
    if revision != AUDIOCPP_REVISION:
        message = "audio.cpp image revision differs from the feasibility pin"
        raise ValueError(message)
    cli_version, _ = run_tool(["podman", "run", "--rm", image, "cli", "--version"])
    return {
        "input": image,
        "id": metadata["Id"],
        "repo_digests": metadata["RepoDigests"],
        "revision": revision,
        "cli_version": cli_version.strip(),
    }


def validate_inputs(model: Path, voice_dir: Path) -> list[Path]:
    required = [model, voice_dir / "ref_codes.txt", voice_dir / "speaker.emb.txt"]
    if any(not path.is_file() for path in required):
        message = f"missing audio.cpp model or Quỳnh Anh assets: {required}"
        raise FileNotFoundError(message)
    if sha256(model) != CHECKPOINT_SHA256 or any(
        sha256(path) != VOICE_SHA256[path.name] for path in required[1:]
    ):
        message = "checkpoint or Quỳnh Anh assets differ from the feasibility pin"
        raise ValueError(message)
    frontend_identity()
    return required


def runtime_settings(model: Path, required: list[Path], image: dict) -> dict:
    return {
        "purpose": "frozen Issue #14 TTS configuration",
        "runtime": "audio.cpp",
        "image": image,
        "checkpoint": f"pnnbao-ump/VieNeu-TTS-v3-Turbo@{CHECKPOINT_REVISION}",
        "checkpoint_precision": "BF16 talker, F16 codec",
        "checkpoint_sha256": sha256(model),
        "voice": "Quỳnh Anh",
        "voice_id": "quynh_anh",
        "voice_package_path": "gguf/voices/quynh_anh",
        "tts_input_treatment": (
            "ordered slash enumeration: marker slash -> comma; "
            "explicit source-case manual normalizations recorded in cases.json"
        ),
        "voice_assets_sha256": {path.name: sha256(path) for path in required[1:]},
        "frontend": frontend_identity(),
        "sentence_segmentation": {
            "checkpoint": SAT_NAME,
            "revision": SAT_REVISION,
            "wtpsplit_version": importlib.metadata.version("wtpsplit"),
            "tokenizer": TOKENIZER_NAME,
            "tokenizer_revision": TOKENIZER_REVISION,
        },
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
            "text_chunk_size": "exact prepared phoneme UTF-8 byte length per request",
            "text_chunk_min": 20,
            "native_frontend": "not invoked: prepared phonemes, no g2p_dict",
        },
        "pcm_channels": "stereo decoder output averaged to mono for upstream join",
        "internal_join": "upstream join_audio_chunks and gaps_to_silence",
        "sentence_join": "upstream join_audio_chunks with sentence gap 0.50 s",
    }


def audio_cpp_command(
    output: Path, model: Path, voice_dir: Path, image: str
) -> list[str]:
    """Use the frozen CUDA image and voice assets for native CLI requests."""
    return [
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
        "--log",
    ]


def run_audio_cpp(
    output: Path, model: Path, voice_dir: Path, image: str, record: dict
) -> None:
    """Synthesize one upstream-prepared phoneme chunk without a second split."""
    phonemes = record["phonemes"]
    if not phonemes.strip() or "\n" in phonemes:
        message = "prepared request must contain one nonempty phoneme paragraph"
        raise ValueError(message)
    # The runtime repacks punctuation pieces within this byte budget.
    record["text_chunk_size_bytes"] = len(phonemes.encode("utf-8"))
    seed = record["seed"]
    name = record["key"]
    command = [
        *audio_cpp_command(output, model, voice_dir, image),
        "--text",
        phonemes,
        "--seed",
        str(seed),
        "--request-option",
        f"text_chunk_size={record['text_chunk_size_bytes']}",
        "--request-option",
        "reference_codes_file=/inputs/voice/ref_codes.txt",
        "--request-option",
        "speaker_embedding_file=/inputs/voice/speaker.emb.txt",
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
    record["audio"] = f"audio/{name}.wav"


def package_audio(output: Path, name: str, pcm: np.ndarray, rate: int) -> dict:
    wav = output / "audio" / f"{name}.wav"
    opus = output / "audio" / f"{name}.opus"
    sf.write(wav, pcm, rate, subtype="PCM_16")
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
            str(opus),
        ]
    )
    duration = str(ogg_duration(opus))
    return {
        "audio": f"audio/{name}.wav",
        "packaged_audio": f"audio/{name}.opus",
        "pcm_samples": len(pcm),
        "sample_rate": rate,
        "clip_begin": "0.000",
        "clip_end": duration,
        "duration_seconds": duration,
    }


def synthesize_sentences(
    output: Path, model: Path, voice_dir: Path, image: str, record: dict
) -> None:
    sentences_pcm = []
    rate = None
    for sentence in record["sentences"]:
        chunks_pcm = []
        name = f"case={record['key']},sentence={sentence['index']:03d}"
        for index, chunk in enumerate(sentence["chunks"]):
            chunk["key"] = f"{name},chunk={index:02d}"
            chunk["seed"] = record["seed"]
            run_audio_cpp(output, model, voice_dir, image, chunk)
            pcm, chunk_rate = sf.read(
                output / chunk["audio"], dtype="float32", always_2d=True
            )
            pcm = pcm.mean(axis=1)
            if rate is not None and rate != chunk_rate:
                message = "inconsistent PCM sample rates"
                raise ValueError(message)
            rate = chunk_rate
            chunks_pcm.append(pcm)
        pcm = join_audio_chunks(
            chunks_pcm, rate, silence_ps=gaps_to_silence(sentence["gaps"])
        )
        sentence.update(package_audio(output, name, pcm, rate))
        sentences_pcm.append(pcm)
    pcm = join_audio_chunks(
        sentences_pcm, rate, silence_ps=[0.5] * (len(sentences_pcm) - 1)
    )
    record.update(package_audio(output, f"case={record['key']}", pcm, rate))
    record["status"] = "ok"
