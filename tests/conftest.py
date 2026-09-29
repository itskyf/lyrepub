"""Keep standalone TTS frontend packages outside the normal test environment."""

import pytest

from scripts import tts_synthesis


@pytest.fixture(autouse=True)
def frontend_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tts_synthesis, "frontend_chunks", lambda text: ([text], []))
    monkeypatch.setattr(tts_synthesis, "frontend_phonemes", lambda text: text)
