"""TTS source mapping and HTTP contracts without standalone dependencies."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from lyrepub import segmentation
from scripts import tts_synthesis
from scripts.tts_benchmark import normalize_slash_enumeration
from scripts.tts_synthesis import prepare_sentences


def test_runtime_requires_loaded_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tts_synthesis, "validate_inputs", lambda *_args: [])
    monkeypatch.setattr(
        tts_synthesis,
        "run_tool",
        lambda command: (
            '{"backend":"cuda"}' if command[-1].endswith("/health") else '{"data":[]}',
            "",
        ),
    )
    with pytest.raises(ValueError, match="model loaded"):
        tts_synthesis.inspect_runtime(Path("model"), Path("voice"))


def test_slash_enumeration_treatment() -> None:
    for source, expected in (
        (
            "Danh sách: 1/ Văn Thù. 2/ Quan Thế âm. 3/ Di Lặc.",
            "Danh sách: 1, Văn Thù. 2, Quan Thế âm. 3, Di Lặc.",
        ),
        ("1/ Một mục\n2/ Hai mục", "1, Một mục\n2, Hai mục"),
        ("Tỉ lệ: 1/2. Ngày 24/8/1284.", "Tỉ lệ: 1/2. Ngày 24/8/1284."),
        ("1/2 số người; 2/3 số sách", "1/2 số người; 2/3 số sách"),
        ("1/ 2. 2/ 3", "1/ 2. 2/ 3"),
        ("1/ tháng tám", "1/ tháng tám"),
        ("1/ Mục riêng. 3/ Mục khác", "1/ Mục riêng. 3/ Mục khác"),
        ("tên 1/ lựa chọn hoặc 2/ thay thế", "tên 1/ lựa chọn hoặc 2/ thay thế"),
    ):
        assert normalize_slash_enumeration(source) == expected


def test_sentence_mapping_and_coverage() -> None:
    source = "  Năm 1284.  Nhà vua trở về. "
    sentences = ["Năm 1284.", "Nhà vua trở về."]
    mapped = prepare_sentences(source, source, sentences)
    assert [(s["source_start"], s["source_end"]) for s in mapped] == [(2, 11), (13, 28)]
    with pytest.raises(ValueError, match="uncovered"):
        prepare_sentences(source, source, sentences[:1])


def test_manual_normalization_preserves_authored_offsets() -> None:
    source = "Trước. S…át Th.. át! Sau."
    sentences = ["Trước.", "S…át Th.. át!", "Sau."]
    manual = {"source_span": "S…át Th.. át!", "tts_text": "Sát Thát!"}
    raw = prepare_sentences(source, source, sentences)
    treated = prepare_sentences(source, source, sentences, manual)
    for original, selected in zip(raw, treated, strict=True):
        for field in ("source_text", "source_start", "source_end"):
            assert original[field] == selected[field]
        assert "normalized_parts" not in selected
    assert treated[1]["tts_input"] == "Sát Thát!"
    assert treated[1]["chunks"][0]["normalized_text"] == "Sát Thát!"
    with pytest.raises(ValueError, match="exactly one"):
        prepare_sentences("Sau.", "Sau.", ["Sau."], manual)
    with pytest.raises(ValueError, match="exactly one"):
        prepare_sentences(source + source, source + source, sentences * 2, manual)


def test_sat_uses_pinned_tokenizer_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    def snapshot(repo: str, **kwargs: object) -> str:
        calls["download"] = (repo, kwargs)
        return "pinned-tokenizer-snapshot"

    def sat(name: str, **kwargs: object) -> object:
        calls["sat"] = (name, kwargs)
        return object()

    monkeypatch.setattr(segmentation, "snapshot_download", snapshot)
    monkeypatch.setattr(segmentation, "SaT", sat)
    segmentation._sat.cache_clear()
    try:
        segmentation._sat()
        repo, kwargs = calls["download"]
        assert repo == "facebookAI/xlm-roberta-base"
        assert kwargs["revision"] == "e73636d4f797dec63c3081bb6ed5c7b0bb3f2089"
        assert set(kwargs["allow_patterns"]) == {
            "config.json",
            "tokenizer_config.json",
            "tokenizer.json",
            "sentencepiece.bpe.model",
        }
        assert calls["sat"] == (
            segmentation.SAT_NAME,
            {
                "tokenizer_name_or_path": "pinned-tokenizer-snapshot",
                "from_pretrained_kwargs": {"revision": segmentation.SAT_REVISION},
            },
        )
    finally:
        segmentation._sat.cache_clear()


@pytest.mark.asyncio
async def test_http_request_and_result_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "audio").mkdir()
    requests = []
    active = 0
    maximum = 0
    status = 200
    media_type = "audio/wav"

    async def read() -> bytes:
        return b"wav"

    def check_status() -> None:
        if status != 200:
            message = "HTTP failure"
            raise RuntimeError(message)

    async def post(url: str, *, json: dict) -> SimpleNamespace:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        requests.append((url, json))
        await asyncio.sleep(0)
        active -= 1
        return SimpleNamespace(
            aread=read,
            raise_for_status=check_status,
            headers={"content-type": media_type},
        )

    monkeypatch.setattr(
        tts_synthesis, "read_pcm", lambda _s: (np.zeros((20, 2)), 48000)
    )
    client = SimpleNamespace(post=post)
    semaphore = asyncio.Semaphore(1)
    chunks = [{"key": str(i), "seed": 5019, "phonemes": "xin cào"} for i in range(2)]
    await asyncio.gather(
        *(tts_synthesis.request_audio(client, semaphore, tmp_path, c) for c in chunks)
    )
    assert maximum == 1
    for chunk, (url, request) in zip(chunks, requests, strict=True):
        assert url == "/v1/audio/speech"
        assert request["input"] == chunk["phonemes"]
        assert request["seed"] == 5019
        assert request["options"]["text_chunk_size"] == str(
            len(chunk["phonemes"].encode())
        )
        assert "g2p_dict" not in request["options"]
        assert (tmp_path / chunk["audio"]).read_bytes() == b"wav"
    chunk = {"key": "failure", "seed": 14, "phonemes": "xin"}
    status = 503
    with pytest.raises(RuntimeError, match="HTTP failure"):
        await tts_synthesis.request_audio(client, semaphore, tmp_path, chunk)
    status, media_type = 200, "application/json"
    with pytest.raises(ValueError, match="non-WAV"):
        await tts_synthesis.request_audio(client, semaphore, tmp_path, chunk)
    media_type = "audio/wav"
    monkeypatch.setattr(tts_synthesis, "read_pcm", lambda _s: (np.zeros((0, 2)), 48000))
    with pytest.raises(ValueError, match="invalid PCM"):
        await tts_synthesis.request_audio(client, semaphore, tmp_path, chunk)
    assert not (tmp_path / "audio/failure.wav").exists()
