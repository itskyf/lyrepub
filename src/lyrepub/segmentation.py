"""Sentence segmentation with SaT (wtpsplit).

Selected in the Issue #11 screening for boundary correctness on the
observed source phenomena; adds no stack beyond the existing
torch/transformers dependencies. Checkpoint segment-any-text/sat-3l at
revision a3b7ba6b61881d619989757aea971cde7d3d6a98, enforced at load time
through from_pretrained_kwargs; the larger sat-12l and sat-12l-sm merge
rapid question bursts and were rejected in the checkpoint comparison.
The tokenizer stays SaT's default (facebookAI/xlm-roberta-base), which
SaT loads without a revision argument — the one unpinned piece.
"""

from functools import lru_cache

from wtpsplit import SaT

SAT_NAME = "sat-3l"
SAT_REVISION = "a3b7ba6b61881d619989757aea971cde7d3d6a98"


@lru_cache(maxsize=1)
def _sat() -> SaT:
    return SaT(SAT_NAME, from_pretrained_kwargs={"revision": SAT_REVISION})


def segment_sentences(text: str) -> list[str]:
    """Split text into sentences using SaT default inference.

    Stripped and non-empty because SaT outputs carry trailing whitespace.
    """
    return [sentence.strip() for sentence in _sat().split(text) if sentence.strip()]
