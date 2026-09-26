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
segmentation screen for Issue #11. The checkpoint revision is enforced
at load time; reruns pass the revision recorded in the silver report so
a future Hub HEAD is never screened silently. uv builds an isolated
environment from the inline metadata, so no project dependency is
touched:

    PYTHONPATH=src:scripts pixi run --environment dev uv run --script \\
        scripts/screen_wtpsplit.py sat-3l-sm 137da054051ad9f1eac42025f758db4ac9f22535

Writes data/silver/segmentation_report_wtpsplit-<checkpoint>.txt.
"""

import sys

from _screen_common import run_cases
from huggingface_hub import HfApi
from wtpsplit import SaT

name, *pinned = sys.argv[1:]
repo = f"segment-any-text/{name}"
# A pinned revision makes reruns evaluate the recorded commit; without
# one, current Hub HEAD is resolved (first screening of a checkpoint).
revision = pinned[0] if pinned else HfApi().model_info(repo).sha

sat = SaT(name, from_pretrained_kwargs={"revision": revision})
run_cases(
    f"wtpsplit-{name}",
    lambda text: list(sat.split(text)),
    ("fast-ebook", "huggingface_hub", "torch", "wtpsplit"),
    notes=(f"{repo} revision {revision} (enforced)",),
)
