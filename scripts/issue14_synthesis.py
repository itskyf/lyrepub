"""Run Issue #14 cases through audio.cpp's VieNeu v3 Turbo CUDA route."""

import hashlib
import importlib.metadata
import json
import logging
import re
from pathlib import Path

from issue14_feasibility import load_records, ogg_duration, run_tool, save_records
from nemo_text_processing.text_normalization.normalize import Normalizer
from sea_g2p import G2P

LOGGER = logging.getLogger(__name__)
AUDIOCPP_REVISION = "955c8725c611d511774e6be132aff6609163b2d2"
NEMO_REVISION = "c3afd14899658d53920b2737ff4d7216d9a32c83"
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
    normalizer = Normalizer(input_case="cased", lang="vi", deterministic=True)
    phonemizer = G2P(lang="vi")
    for record in selected:
        text_input = record.get("tts_input", record["source"]["text"])
        record["tts_input"] = text_input
        try:
            normalized, phonemes = preprocess(text_input, normalizer, phonemizer)
            if not normalized.strip() or not phonemes.strip():
                message = "preprocessing produced empty input"
                raise ValueError(message)
            record["phonemes"] = phonemes
            record["normalized_text"] = normalized
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


def preprocess(text: str, normalizer: Normalizer, phonemizer: G2P) -> tuple[str, str]:
    """Apply only NeMo Vietnamese TN, then SEA-G2P phonemization."""
    normalized = normalizer.normalize(
        text, verbose=False, punct_pre_process=False, punct_post_process=False
    )
    return normalized, phonemizer.convert(normalized, punc_norm=False)


def add_variants(records: list[dict], path: Path) -> None:
    """Add explicit experimental inputs without changing baseline records."""
    for variant in json.loads(path.read_text(encoding="utf-8")):
        if not re.fullmatch(r"[a-z0-9-]+", variant["key"]) or not isinstance(
            variant["tts_input"], str
        ):
            message = "variant requires a safe artifact key and explicit text input"
            raise ValueError(message)
        baseline = next(r for r in records if r["key"] == variant["variant_of"])
        if baseline.get("status") != "ok" or any(
            r["key"] == variant["key"] for r in records
        ):
            message = "variant requires completed baseline and a distinct unused key"
            raise ValueError(message)
        record = {
            **variant,
            "source": baseline["source"],
            "case": False,
            "playback": False,
        }
        records.append(record)


def inspect_image(image: str) -> dict:
    stdout, _ = run_tool(["podman", "image", "inspect", image])
    metadata = json.loads(stdout)[0]
    revision = metadata["Config"]["Labels"]["org.opencontainers.image.revision"]
    if revision != AUDIOCPP_REVISION:
        message = "audio.cpp image revision differs from the feasibility pin"
        raise ValueError(message)
    return {
        "input": image,
        "id": metadata["Id"],
        "repo_digests": metadata["RepoDigests"],
        "revision": revision,
    }


def validate_inputs(model: Path, voice_dir: Path) -> list[Path]:
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
    nemo_url = json.loads(
        importlib.metadata.distribution("nemo-text-processing").read_text(
            "direct_url.json"
        )
    )
    if nemo_url["vcs_info"]["commit_id"] != NEMO_REVISION:
        message = "NeMo Vietnamese TN differs from the repository pin"
        raise ValueError(message)
    return required


def runtime_settings(model: Path, required: list[Path], image: dict) -> dict:
    return {
        "runtime": "audio.cpp",
        "image": image,
        "checkpoint": f"pnnbao-ump/VieNeu-TTS-v3-Turbo@{CHECKPOINT_REVISION}",
        "checkpoint_precision": "BF16 talker, F16 codec",
        "checkpoint_sha256": sha256(model),
        "voice": "Thục Đoan",
        "voice_assets_sha256": {path.name: sha256(path) for path in required[1:]},
        "frontend": (
            f"sea-g2p {importlib.metadata.version('sea-g2p')} "
            "G2P(vi), phonemization only, punc_norm=False"
        ),
        "normalization": {
            "package": "nemo-text-processing",
            "revision": NEMO_REVISION,
            "lang": "vi",
            "input_case": "cased",
            "deterministic": True,
            "post_process": True,
            "punct_pre_process": False,
            "punct_post_process": False,
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
            "text_chunk_size": 200,
            "text_chunk_min": 20,
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
    seed = record["seed"]
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
        "--log",
        "--text",
        phonemes,
        "--seed",
        str(seed),
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
