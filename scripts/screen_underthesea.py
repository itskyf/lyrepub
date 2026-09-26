#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["fast-ebook", "underthesea"]
# ///
"""Screen Underthesea sentence tokenization on the frozen inspection cases.

Documented default inference, no tuning; part of the symmetric
segmentation screen for Issue #11. uv builds an isolated environment
from the inline metadata, so no project dependency is touched:

    PYTHONPATH=src:scripts pixi run --environment dev uv run --script \\
        scripts/screen_underthesea.py

Writes data/silver/segmentation_report_underthesea.txt.
"""

import underthesea
from _screen_common import run_cases

run_cases(
    "underthesea",
    underthesea.sent_tokenize,
    ("fast-ebook", "underthesea"),
)
