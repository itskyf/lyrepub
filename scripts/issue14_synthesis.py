"""VieNeu-only inference step for Issue #14 feasibility."""

import importlib.metadata
import json
import logging
from pathlib import Path

import soundfile as sf
import torch
from issue14_feasibility import (
    CODEC_REVISION,
    MODEL_REVISION,
    SAMPLE_RATE,
    chunk_offsets,
    load_records,
    save_records,
)
from vieneu import Vieneu
from vieneu._v3_turbo_engine.rep_history import DEFAULT_REP_WINDOW
from vieneu_utils.core_utils import (
    gaps_to_silence,
    join_audio_chunks,
    pause_pad_samples,
)
from vieneu_utils.phonemize_text import normalize_to_chunks_v3_with_gaps

LOGGER = logging.getLogger(__name__)


def synthesize(output: Path) -> None:
    records = load_records(output)
    model = (
        Path.home()
        / ".cache/huggingface/hub/models--pnnbao-ump--VieNeu-TTS-v3-Turbo/snapshots"
        / MODEL_REVISION
    )
    codec = (
        Path.home()
        / ".cache/huggingface/hub/models--OpenMOSS-Team--MOSS-Audio-Tokenizer-Nano"
        / "snapshots"
        / CODEC_REVISION
    )
    if not (model / "update/model.safetensors").is_file() or not codec.is_dir():
        message = "pinned model or codec snapshot unavailable"
        raise FileNotFoundError(message)
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        message = "selected CUDA/bfloat16 backend unavailable"
        raise RuntimeError(message)
    sampling = {
        "temperature": 0.8,
        "top_k": 25,
        "top_p": 0.95,
        "max_new_frames": 300,
        "repetition_penalty": 1.2,
        "repetition_window": DEFAULT_REP_WINDOW,
    }
    settings = {
        "runtime_commit": "c1390abbdb2eedcdf58eafb546966c06ce27af71",
        "vieneu_package": importlib.metadata.version("vieneu"),
        "checkpoint": f"pnnbao-ump/VieNeu-TTS-v3-Turbo@{MODEL_REVISION}/update",
        "codec": f"OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano@{CODEC_REVISION}",
        "backend": "pytorch",
        "device": "cuda",
        "dtype": "bfloat16",
        "voice": "Thục Đoan",
        "sample_rate": SAMPLE_RATE,
        "max_chars": 256,
        "batch_size": 32,
        "babble_retries": 2,
        "apply_watermark": False,
        "sampling": sampling,
        "seed_per_block": "14 + source spine index * 1000 + block index",
        "preprocessing": (
            "VieNeu normalize_to_chunks_v3_with_gaps; no project normalization"
        ),
    }
    (output / "runtime.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tts = Vieneu(
        mode="v3turbo",
        backbone_repo=str(model),
        moss_tokenizer=str(codec),
        backend="pytorch",
        device="cuda",
        dtype="bfloat16",
        babble_retries=2,
        max_batch_size=32,
    )
    if tts.backend != "pytorch" or tts.sample_rate != SAMPLE_RATE:
        message = "VieNeu backend or sample rate mismatch"
        raise RuntimeError(message)
    speaker, ref_codes = tts._resolve_ref(
        voice="Thục Đoan", ref_audio=None, denoise=True, use_ref_codes=True
    )
    (output / "audio").mkdir(exist_ok=True)
    (output / "joins").mkdir(exist_ok=True)
    for record in records:
        if record.get("status") == "ok":
            continue
        synthesize_record(output, records, record, tts, (speaker, ref_codes, sampling))


def synthesize_record(
    output: Path,
    records: list[dict],
    record: dict,
    tts: Vieneu,
    voice: tuple[object, object, dict],
) -> None:
    speaker, ref_codes, sampling = voice
    source = record["source"]
    case_key = record["key"]
    seed = 14 + source["spine_index"] * 1000 + source["block_index"]
    torch.manual_seed(seed)
    try:
        chunks, gaps = normalize_to_chunks_v3_with_gaps(source["text"], max_chars=256)
        record["chunks"] = chunks
        record["gaps"] = gaps
        record["seed"] = seed
        if not chunks:
            message = "VieNeu produced no synthesis chunks"
            raise ValueError(message)
        record["status"] = "preprocessed"
        save_records(output, records)
        waves = tts._infer_chunks(
            chunks=chunks,
            speaker_emb=speaker,
            ref_codes=ref_codes,
            use_ref_codes=True,
            batch_size=32,
            sampling=sampling,
        )
        if len(waves) != len(chunks) or any(not len(w) for w in waves):
            message = "VieNeu returned missing or empty chunk audio"
            raise ValueError(message)
        pauses = gaps_to_silence(gaps)
        pads = [
            pause_pad_samples(waves[i], waves[i + 1], SAMPLE_RATE, pauses[i])
            for i in range(len(gaps))
        ]
        offsets = chunk_offsets([len(w) for w in waves], pads)
        joined = join_audio_chunks(waves, SAMPLE_RATE, silence_ps=pauses)
        expected_samples = offsets[-1] + len(waves[-1])
        if len(joined) != expected_samples:
            message = "chunk timing differs from joined audio"
            raise ValueError(message)
        audio_path = output / "audio" / f"{case_key}.wav"
        sf.write(audio_path, joined, SAMPLE_RATE, subtype="PCM_16")
        record["audio"] = str(audio_path)
        record["samples"] = len(joined)
        record["duration_seconds"] = len(joined) / SAMPLE_RATE
        record["chunk_starts_seconds"] = [n / SAMPLE_RATE for n in offsets]
        record["join_seconds"] = [n / SAMPLE_RATE for n in offsets[1:]]
        if record["case"] and len(waves) > 1:
            for i, boundary in enumerate(offsets[1:], start=1):
                begin = max(0, boundary - SAMPLE_RATE * 4)
                end = min(len(joined), boundary + SAMPLE_RATE * 4)
                sf.write(
                    output / "joins" / f"{case_key}-join-{i:02}.wav",
                    joined[begin:end],
                    SAMPLE_RATE,
                    subtype="PCM_16",
                )
        record["status"] = "ok"
    except (ValueError, RuntimeError, OSError) as exc:
        record["status"] = (
            "preprocessing_failure"
            if record.get("status") != "preprocessed"
            else "synthesis_failure"
        )
        record["error"] = f"{type(exc).__name__}: {exc}"
    save_records(output, records)
    LOGGER.info("%s: %s", case_key, record["status"])
