"""Focused frontend feasibility checks; no sentence model or synthesis inference."""

from pathlib import Path

import pytest

from scripts.issue14_feasibility import normalize_slash_enumeration
from scripts.issue14_synthesis import (
    frontend_identity,
    prepare_sentences,
    run_audio_cpp,
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
    chunk = mapped[0]["chunks"][0] | {"key": "target-chunk-00", "seed": 14}

    def fake_runtime(command: list[str]) -> tuple[str, str]:
        commands.append(command)
        (audio / "target-chunk-00.wav").write_bytes(b"pcm")
        return "log", ""

    monkeypatch.setattr("scripts.issue14_synthesis.run_tool", fake_runtime)
    run_audio_cpp(tmp_path, tmp_path / "model", tmp_path / "voice", "image", chunk)
    budget = len(chunk["phonemes"].encode("utf-8"))
    assert f"text_chunk_size={budget}" in commands[0]
    assert chunk["text_chunk_size_bytes"] == budget
    assert not any("g2p_dict=" in part for part in commands[0])
