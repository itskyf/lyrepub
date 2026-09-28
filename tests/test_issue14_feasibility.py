"""Focused frontend feasibility checks; no sentence model or synthesis inference."""

from pathlib import Path

import numpy as np
import pytest

from lyrepub import segmentation
from scripts.issue14_feasibility import normalize_slash_enumeration
from scripts.issue14_synthesis import (
    frontend_identity,
    prepare_sentences,
    run_audio_cpp,
    synthesize_sentences,
)


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


def test_frontend_identity() -> None:
    identity = frontend_identity()
    assert identity["versions"] == {"vieneu": "3.8.3", "sea-g2p": "0.10.0"}
    assert identity["dictionary_sha256"] == (
        "4346e690d0711ebc5231e7a42c5c88aaf6e40377e894b4617c018fd81c6f4096"
    )


def test_number_phrases_survive_upstream_chunks() -> None:
    for year, phrase in (
        ("1256", "một nghìn hai trăm năm mươi sáu"),
        ("1284", "một nghìn hai trăm tám mươi bốn"),
    ):
        source = "Nhà vua đã chuẩn bị quân lính và thuyền bè " * 7 + f"vào năm {year}."
        target = prepare_sentences(source, source, [source])[0]
        assert len(target["chunks"]) > 1
        assert (
            sum(phrase in chunk["normalized_text"] for chunk in target["chunks"]) == 1
        )


def test_sentence_mapping_and_internal_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "  Năm 1284.  Nhà vua trở về. "
    sentences = ["Năm 1284.", "Nhà vua trở về."]
    mapped = prepare_sentences(source, source, sentences)
    assert mapped == prepare_sentences(source, source, sentences)
    assert [(s["source_start"], s["source_end"]) for s in mapped] == [(2, 11), (13, 28)]
    assert (
        mapped[0]["chunks"][0]["normalized_text"]
        == "năm một nghìn hai trăm tám mươi bốn."
    )
    with pytest.raises(ValueError, match="uncovered"):
        prepare_sentences(source, source, sentences[:1])

    commands = []
    audio = tmp_path / "audio"
    audio.mkdir()
    (tmp_path / "traces").mkdir()
    chunk = mapped[0]["chunks"][0] | {
        "key": "case=target,sentence=000,chunk=00",
        "seed": 14,
    }

    def fake_runtime(command: list[str]) -> tuple[str, str]:
        commands.append(command)
        (audio / "case=target,sentence=000,chunk=00.wav").write_bytes(b"pcm")
        return "log", ""

    monkeypatch.setattr("scripts.issue14_synthesis.run_tool", fake_runtime)
    run_audio_cpp(tmp_path, tmp_path / "model", tmp_path / "voice", "image", chunk)
    budget = len(chunk["phonemes"].encode("utf-8"))
    assert f"text_chunk_size={budget}" in commands[0]
    assert chunk["text_chunk_size_bytes"] == budget
    assert not any("g2p_dict=" in part for part in commands[0])

    names = []

    def package(_output: Path, name: str, _pcm: np.ndarray, _rate: int) -> dict:
        names.append(name)
        return {"audio": f"audio/{name}.wav"}

    monkeypatch.setattr("scripts.issue14_synthesis.package_audio", package)
    monkeypatch.setattr(
        "scripts.issue14_synthesis.sf.read",
        lambda *_args, **_kwargs: (np.zeros((50, 2), dtype=np.float32), 48000),
    )
    record = {"key": "target", "seed": 14, "sentences": [mapped[0]]}
    synthesize_sentences(
        tmp_path, tmp_path / "model", tmp_path / "voice", "image", record
    )
    assert record["sentences"][0]["chunks"][0]["key"] == (
        "case=target,sentence=000,chunk=00"
    )
    assert names == ["case=target,sentence=000", "case=target"]


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
    assert treated[1]["chunks"][0]["normalized_text"] == "sát thát."
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
