#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["fast-ebook", "huggingface_hub", "stanza", "torch"]
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
#
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# ///
"""Screen Stanza Vietnamese tokenization on the frozen inspection cases.

Documented default inference, no tuning; part of the symmetric
segmentation screen for Issue #11. uv builds an isolated environment
from the inline metadata, so no project dependency is touched:

    PYTHONPATH=src:scripts pixi run --environment dev uv run --script \\
        scripts/screen_stanza.py

Writes data/silver/segmentation_report_stanza.txt.
"""

import stanza
from _screen_common import run_cases

stanza.download("vi", verbose=False)
pipe = stanza.Pipeline("vi", processors="tokenize", verbose=False)


def with_stanza(text: str) -> list[str]:
    return [sentence.text for sentence in pipe(text).sentences]


run_cases(
    "stanza",
    with_stanza,
    ("fast-ebook", "huggingface_hub", "stanza", "torch"),
)
