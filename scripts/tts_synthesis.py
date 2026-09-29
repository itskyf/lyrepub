"""Frozen TTS frontend, audio packaging, and Compose inference."""

import asyncio
import hashlib
import importlib
import importlib.metadata
import io
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy import ndarray
    from zapros import AsyncClient

from lyrepub.audio import encode_opus, run_tool
from lyrepub.segmentation import (
    SAT_NAME,
    SAT_REVISION,
    TOKENIZER_NAME,
    TOKENIZER_REVISION,
)

SAMPLE_RATE = 48000
MANUAL_NORMALIZATIONS = {
    (17, 135): {"source_span": "S…át Th.. át!", "tts_text": "Sát Thát!"},
}

LOGGER = logging.getLogger(__name__)
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


def normalize_slash_enumeration(text: str) -> str:
    """Separate ordered slash-list markers; leave ambiguous slashes unchanged."""
    markers = list(
        re.finditer(r"(?:^|(?<=[(:;.\n]))[ \t]*(\d+)/[ \t]+(?=[^\W\d_])", text)
    )
    replacements = []
    run = []
    minimum_markers = 2
    for marker in markers:
        number = int(marker.group(1))
        if run and number != int(run[-1].group(1)) + 1:
            if len(run) >= minimum_markers:
                replacements.extend(run)
            run = []
        if run or number == 1:
            run.append(marker)
    if len(run) >= minimum_markers:
        replacements.extend(run)
    for marker in reversed(replacements):
        slash = marker.end(1)
        text = text[:slash] + "," + text[slash + 1 :]
    return text


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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
        chunks, gaps = frontend_chunks(prepared)
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
                        "phonemes": frontend_phonemes(chunk),
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
    """Record Python frontend provenance and verify the frozen dictionary."""
    versions = {
        name: importlib.metadata.version(name) for name in ("vieneu", "sea-g2p")
    }
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


def validate_inputs(model: Path, voice_dir: Path) -> list[Path]:
    """Verify pinned checkpoint and Quỳnh Anh conditioning assets."""
    required = [model, voice_dir / "ref_codes.txt", voice_dir / "speaker.emb.txt"]
    if any(not path.is_file() for path in required):
        message = f"missing audio.cpp model or Quỳnh Anh assets: {required}"
        raise FileNotFoundError(message)
    if sha256(model) != CHECKPOINT_SHA256 or any(
        sha256(path) != VOICE_SHA256[path.name] for path in required[1:]
    ):
        message = "checkpoint or Quỳnh Anh assets differ from the feasibility pin"
        raise ValueError(message)
    return required


def runtime_settings(model: Path, required: list[Path], image: dict) -> dict:
    return {
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
            "explicit source-case manual normalizations recorded with sentence inputs"
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


def package_audio(output: Path, name: str, pcm: "ndarray", rate: int) -> dict:
    """Encode joined narration as Opus and record measured clip duration."""
    wav = output / "audio" / f"{name}.wav"
    opus = output / "audio" / f"{name}.opus"
    sf = importlib.import_module("soundfile")

    sf.write(wav, pcm, rate, subtype="PCM_16")
    duration = str(encode_opus(wav, opus))
    return {
        "audio": f"audio/{name}.wav",
        "packaged_audio": f"audio/{name}.opus",
        "pcm_samples": len(pcm),
        "sample_rate": rate,
        "clip_begin": "0.000",
        "clip_end": duration,
    }


def frontend_chunks(text: str) -> tuple[list[str], list[float]]:
    frontend = importlib.import_module("vieneu_utils.phonemize_text")
    return frontend.normalize_to_chunks_v3_with_gaps(text)


def frontend_phonemes(text: str) -> str:
    frontend = importlib.import_module("vieneu_utils.phonemize_text")
    return frontend.phonemize_text_with_emotions(text)


def read_pcm(source: Path | io.BytesIO) -> tuple["ndarray", int]:
    sf = importlib.import_module("soundfile")
    return sf.read(source, dtype="float32", always_2d=True)


async def request_audio(
    client: "AsyncClient", semaphore: asyncio.Semaphore, output: Path, chunk: dict
) -> None:
    """Send one frozen phoneme chunk and reject HTTP or invalid WAV results."""
    phonemes = chunk["phonemes"]
    if not phonemes.strip() or "\n" in phonemes:
        message = "prepared request must contain one nonempty phoneme paragraph"
        raise ValueError(message)
    chunk["text_chunk_size_bytes"] = len(phonemes.encode("utf-8"))
    request = {
        "model": "vieneu",
        "input": phonemes,
        "seed": chunk["seed"],
        "response_format": "wav",
        "options": {
            "text_chunk_size": str(chunk["text_chunk_size_bytes"]),
            "temperature": "0.8",
            "top_k": "25",
            "top_p": "0.95",
            "repetition_penalty": "1.2",
            "repetition_window": "64",
            "max_tokens": "300",
            "frame_cap": "true",
            "do_sample": "true",
            "babble_retries": "2",
        },
    }
    async with semaphore:
        response = await client.post("/v1/audio/speech", json=request)
        content = await response.aread()
        response.raise_for_status()
        if response.headers.get("content-type", "").split(";")[0] != "audio/wav":
            message = "audio.cpp returned a non-WAV response"
            raise ValueError(message)
        pcm, rate = await asyncio.to_thread(read_pcm, io.BytesIO(content))
        if (
            rate != SAMPLE_RATE
            or not len(pcm)
            or not importlib.import_module("numpy").isfinite(pcm).all()
        ):
            message = "audio.cpp returned invalid PCM"
            raise ValueError(message)
        chunk["audio"] = f"audio/{chunk['key']}.wav"
        (output / chunk["audio"]).write_bytes(content)


async def synthesize_sentences(
    output: Path,
    client: "AsyncClient",
    semaphore: asyncio.Semaphore,
    record: dict,
    *,
    join_block: bool = False,
) -> None:
    """Join frontend chunks, package sentence clips and optionally a benchmark block."""
    core = importlib.import_module("vieneu_utils.core_utils")

    sentences_pcm = []
    rate = None
    for sentence in record["sentences"]:
        chunks_pcm = []
        name = f"case={record['key']},sentence={sentence['index']:03d}"
        for index, chunk in enumerate(sentence["chunks"]):
            chunk["key"] = f"{name},chunk={index:02d}"
            chunk["seed"] = record["seed"]
            await request_audio(client, semaphore, output, chunk)
            pcm, chunk_rate = await asyncio.to_thread(read_pcm, output / chunk["audio"])
            if rate is not None and rate != chunk_rate:
                message = "inconsistent PCM sample rates"
                raise ValueError(message)
            rate = chunk_rate
            chunks_pcm.append(pcm.mean(axis=1))
        pcm = core.join_audio_chunks(
            chunks_pcm, rate, silence_ps=core.gaps_to_silence(sentence["gaps"])
        )
        sentence.update(await asyncio.to_thread(package_audio, output, name, pcm, rate))
        if join_block:
            sentences_pcm.append(pcm)
    if join_block:
        pcm = core.join_audio_chunks(
            sentences_pcm, rate, silence_ps=[0.5] * (len(sentences_pcm) - 1)
        )
        record.update(
            await asyncio.to_thread(
                package_audio, output, f"case={record['key']}", pcm, rate
            )
        )
    record["status"] = "ok"


def inspect_runtime(model: Path, voice: Path) -> dict:
    """Verify the configured, loaded Compose runtime and frozen host assets."""
    required = validate_inputs(model, voice)
    stdout, _ = run_tool(
        ["curl", "--fail", "--silent", "--show-error", "http://127.0.0.1:8080/health"]
    )
    health_data = json.loads(stdout)
    stdout, _ = run_tool(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "http://127.0.0.1:8080/v1/models?include_session_options=true",
        ]
    )
    models = json.loads(stdout)["data"]
    loaded = next((m for m in models if m["id"] == "vieneu"), None)
    if (
        loaded is None
        or health_data["backend"] != "cuda"
        or not loaded["loaded"]
        or loaded["family"] != "vieneu_v3_turbo"
    ):
        message = "Compose server must have the CUDA VieNeu v3 Turbo model loaded"
        raise ValueError(message)
    container_id, _ = run_tool(["podman", "compose", "ps", "--quiet", "audiocpp"])
    stdout, _ = run_tool(["podman", "inspect", container_id.strip()])
    container = json.loads(stdout)[0]
    stdout, _ = run_tool(["podman", "image", "inspect", container["Image"]])
    image = json.loads(stdout)[0]
    stdout, _ = run_tool(
        ["podman", "compose", "exec", "--no-TTY", "audiocpp", "cat", "/app/server.json"]
    )
    config = json.loads(stdout)
    entry = {m["id"]: m for m in config["models"]}["vieneu"]
    models_mount = {m["Destination"]: m for m in container["Mounts"]}["/app/models"]

    def host_asset(path: str) -> Path:
        return Path(models_mount["Source"]) / Path(path).relative_to("/app/models")

    if (
        host_asset(loaded["path"]) != model
        or entry["path"] != loaded["path"]
        or config["backend"] != "cuda"
        or any(
            sha256(host_asset(entry["default_request_options"][option]))
            != VOICE_SHA256[name]
            for option, name in [
                ("reference_codes_file", "ref_codes.txt"),
                ("speaker_embedding_file", "speaker.emb.txt"),
            ]
        )
    ):
        message = "server model or voice differs from verified host assets"
        raise ValueError(message)
    settings = runtime_settings(
        model,
        required,
        {
            "id": image["Id"],
            "repo_digests": image["RepoDigests"],
            "revision": image["Config"]["Labels"].get(
                "org.opencontainers.image.revision"
            ),
            "compose_image": container["Config"]["Image"],
        },
    )
    settings["server"] = {"health": health_data, "model": loaded, "config": config}
    settings["execution"] = (
        "Compose HTTP speech requests; one client and semaphore; seed reset per chunk"
    )
    return settings


async def synthesize_records(
    output: Path,
    assets: tuple[Path, Path],
    records: list[dict],
    concurrency: int,
    *,
    filename: str,
) -> None:
    """Retain failures, save resumable records and never switch inference paths."""
    zapros = importlib.import_module("zapros")
    join_block = filename == "cases.json"
    model, voice = assets

    if concurrency <= 0:
        message = "concurrency must be positive"
        raise ValueError(message)
    await asyncio.to_thread(output.mkdir, parents=True, exist_ok=True)
    (output / "audio").mkdir(exist_ok=True)
    if any(r.get("status") == "preprocessing_failure" for r in records):
        message = "unresolved preprocessing failures"
        raise ValueError(message)
    semaphore = asyncio.Semaphore(concurrency)
    async with zapros.AsyncClient(
        handler=zapros.AsyncPyreqwestHandler(), base_url="http://127.0.0.1:8080"
    ) as client:
        settings = await asyncio.to_thread(inspect_runtime, model, voice)
        settings["purpose"] = "TTS benchmark" if join_block else "full TTS publication"
        if not join_block:
            settings.pop("sentence_join")
            settings["seed_per_block"] = (
                "14 + bronze source spine index * 1000 + block index"
            )
        runtime = output / "runtime.json"
        if runtime.exists() and json.loads(runtime.read_text()) != settings:
            message = "runtime differs from existing synthesis"
            raise ValueError(message)
        runtime.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n")

        async def run(record: dict) -> None:
            try:
                await synthesize_sentences(
                    output, client, semaphore, record, join_block=join_block
                )
                record.pop("error", None)
            except Exception as exc:
                record["status"] = "synthesis_failure"
                record["error"] = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                (output / filename).write_text(
                    json.dumps(records, ensure_ascii=False, indent=2) + "\n"
                )
            LOGGER.info("%s: %s", record["key"], record["status"])

        # Only concurrency records are active, avoiding thousands of queued requests.
        selected = [r for r in records if r.get("status") != "ok"]
        for start in range(0, len(selected), concurrency):
            await asyncio.gather(
                *(run(r) for r in selected[start : start + concurrency])
            )
