"""Frozen TTS frontend, audio packaging, and Compose inference."""

import asyncio
import hashlib
import io
import json
import logging
from pathlib import Path

import numpy as np
import soundfile
import zapros
from vieneu_utils import core_utils
from vieneu_utils.phonemize_text import (
    normalize_to_chunks_v3_with_gaps,
    phonemize_text_with_emotions,
)

from lyrepub.audio import encode_opus
from lyrepub.tts_text import map_sentence_inputs

SAMPLE_RATE = 48000
MANUAL_NORMALIZATIONS = {
    (17, 135): {"source_span": "S…át Th.. át!", "tts_text": "Sát Thát!"},
}

LOGGER = logging.getLogger(__name__)


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
    result = map_sentence_inputs(source, text_input, sentences, manual_normalization)
    for sentence in result:
        chunks, gaps = normalize_to_chunks_v3_with_gaps(sentence["tts_input"])
        if not chunks or any(not chunk.strip() for chunk in chunks):
            message = (
                f"frontend produced empty synthesis input: {sentence['source_text']!r}"
            )
            raise ValueError(message)
        sentence["gaps"] = gaps
        sentence["chunks"] = [
            {
                "normalized_text": chunk,
                "phonemes": phonemize_text_with_emotions(chunk),
            }
            for chunk in chunks
        ]
    return result


def package_audio(
    output: Path, work: Path, name: str, pcm: np.ndarray, rate: int
) -> dict:
    """Encode joined narration as Opus and record measured clip duration."""
    wav = work / "audio" / f"{name}.wav"
    opus = output / "audio" / f"{name}.opus"
    soundfile.write(wav, pcm, rate, subtype="PCM_16")
    duration = str(encode_opus(wav, opus))
    return {
        "packaged_audio": f"audio/{name}.opus",
        "pcm_samples": len(pcm),
        "sample_rate": rate,
        "clip_begin": "0.000",
        "clip_end": duration,
    }


def read_pcm(source: Path | io.BytesIO) -> tuple[np.ndarray, int]:
    return soundfile.read(source, dtype="float32", always_2d=True)


async def request_audio(
    client: zapros.AsyncClient, semaphore: asyncio.Semaphore, work: Path, chunk: dict
) -> Path:
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
        if rate != SAMPLE_RATE or not len(pcm) or not np.isfinite(pcm).all():
            message = "audio.cpp returned invalid PCM"
            raise ValueError(message)
        wav = work / "audio" / f"{chunk['key']}.wav"
        wav.write_bytes(content)
        return wav


async def synthesize_sentences(
    paths: tuple[Path, Path],
    client: zapros.AsyncClient,
    semaphore: asyncio.Semaphore,
    record: dict,
    *,
    join_block: bool = False,
) -> None:
    """Join frontend chunks, package sentence clips and optionally a benchmark block."""
    output, work = paths
    sentences_pcm = []
    rate = None
    for sentence in record["sentences"]:
        chunks_pcm = []
        name = f"case={record['key']},sentence={sentence['index']:03d}"
        for index, chunk in enumerate(sentence["chunks"]):
            chunk["key"] = f"{name},chunk={index:02d}"
            chunk["seed"] = record["seed"]
            wav = await request_audio(client, semaphore, work, chunk)
            pcm, chunk_rate = await asyncio.to_thread(read_pcm, wav)
            if rate is not None and rate != chunk_rate:
                message = "inconsistent PCM sample rates"
                raise ValueError(message)
            rate = chunk_rate
            chunks_pcm.append(pcm.mean(axis=1))
        pcm = core_utils.join_audio_chunks(
            chunks_pcm, rate, silence_ps=core_utils.gaps_to_silence(sentence["gaps"])
        )
        sentence.update(
            await asyncio.to_thread(package_audio, output, work, name, pcm, rate)
        )
        if join_block:
            sentences_pcm.append(pcm)
    if join_block:
        pcm = core_utils.join_audio_chunks(
            sentences_pcm, rate, silence_ps=[0.5] * (len(sentences_pcm) - 1)
        )
        record.update(
            await asyncio.to_thread(
                package_audio, output, work, f"case={record['key']}", pcm, rate
            )
        )
    record["status"] = "ok"


async def synthesize_records(
    output: Path,
    work: Path,
    records: list[dict],
    concurrency: int,
    *,
    filename: str,
) -> None:
    """Retain failures, save resumable records and never switch inference paths."""
    join_block = filename == "cases.json"

    if concurrency <= 0:
        message = "concurrency must be positive"
        raise ValueError(message)
    await asyncio.to_thread(output.mkdir, parents=True, exist_ok=True)
    (output / "audio").mkdir(exist_ok=True)
    (work / "audio").mkdir(parents=True, exist_ok=True)
    if any(r.get("status") == "preprocessing_failure" for r in records):
        message = "unresolved preprocessing failures"
        raise ValueError(message)
    semaphore = asyncio.Semaphore(concurrency)
    async with zapros.AsyncClient(
        handler=zapros.AsyncPyreqwestHandler(), base_url="http://127.0.0.1:8080"
    ) as client:

        async def run(record: dict) -> None:
            try:
                await synthesize_sentences(
                    (output, work), client, semaphore, record, join_block=join_block
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
