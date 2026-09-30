"""Pure TTS source mapping and sentence-input treatments."""

import pytest

from lyrepub import segmentation
from lyrepub.tts_text import map_sentence_inputs, normalize_slash_enumeration


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
    mapped = map_sentence_inputs(source, source, sentences)
    assert [(s["source_start"], s["source_end"]) for s in mapped] == [(2, 11), (13, 28)]
    with pytest.raises(ValueError, match="uncovered"):
        map_sentence_inputs(source, source, sentences[:1])


def test_manual_normalization_preserves_authored_offsets() -> None:
    source = "Trước. S…át Th.. át! Sau."
    sentences = ["Trước.", "S…át Th.. át!", "Sau."]
    manual = {"source_span": "S…át Th.. át!", "tts_text": "Sát Thát!"}
    raw = map_sentence_inputs(source, source, sentences)
    treated = map_sentence_inputs(source, source, sentences, manual)
    for original, selected in zip(raw, treated, strict=True):
        for field in ("source_text", "source_start", "source_end"):
            assert original[field] == selected[field]
    assert treated[1]["tts_input"] == "Sát Thát!"
    with pytest.raises(ValueError, match="exactly one"):
        map_sentence_inputs("Sau.", "Sau.", ["Sau."], manual)
    with pytest.raises(ValueError, match="exactly one"):
        map_sentence_inputs(source + source, source + source, sentences * 2, manual)


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
