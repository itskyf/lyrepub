#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["fast-ebook", "huggingface_hub", "torch", "wtpsplit>=2.2"]
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
#
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# ///
"""Screen SaT/wtpsplit sentence segmentation on the frozen inspection cases.

Documented default inference, no tuning; part of the symmetric
segmentation screen for Issue #11. uv builds an isolated environment
from the inline metadata, so no project dependency is touched:

    PYTHONPATH=src:scripts pixi run --environment dev uv run --script \\
        scripts/screen_wtpsplit.py

Writes data/silver/segmentation_report_wtpsplit.txt.
"""

from _screen_common import run_cases
from huggingface_hub import HfApi
from wtpsplit import SaT

SAT_NAME = "sat-3l"
SAT_REPO = "segment-any-text/sat-3l"

sat = SaT(SAT_NAME)
run_cases(
    "wtpsplit",
    lambda text: list(sat.split(text)),
    ("fast-ebook", "huggingface_hub", "torch", "wtpsplit"),
    notes=(f"{SAT_REPO} revision {HfApi().model_info(SAT_REPO).sha}",),
)
