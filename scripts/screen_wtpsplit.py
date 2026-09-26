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
"""Screen a SaT/wtpsplit checkpoint on the frozen inspection cases.

Documented default inference, no tuning; part of the symmetric
segmentation screen for Issue #11. The checkpoint revision is fetched
and enforced at load time. uv builds an isolated environment from the
inline metadata, so no project dependency is touched:

    PYTHONPATH=src:scripts pixi run --environment dev uv run --script \\
        scripts/screen_wtpsplit.py sat-3l

Writes data/silver/segmentation_report_wtpsplit-<checkpoint>.txt.
"""

import sys

from _screen_common import run_cases
from huggingface_hub import HfApi
from wtpsplit import SaT

name = sys.argv[1]
repo = f"segment-any-text/{name}"
revision = HfApi().model_info(repo).sha

sat = SaT(name, from_pretrained_kwargs={"revision": revision})
run_cases(
    f"wtpsplit-{name}",
    lambda text: list(sat.split(text)),
    ("fast-ebook", "huggingface_hub", "torch", "wtpsplit"),
    notes=(f"{repo} revision {revision} (enforced)",),
)
