"""Sentence segmentation with SaT (wtpsplit).

Selected in the Issue #11 screening for boundary correctness on the
observed source phenomena; adds no stack beyond the existing
torch/transformers dependencies. Checkpoint segment-any-text/sat-3l-sm
at revision 137da054051ad9f1eac42025f758db4ac9f22535, enforced at load
time through from_pretrained_kwargs. Checkpoint comparison on the frozen
cases: sat-3l over-splits at commas and dashes (including spurious
lone-dash sentences), the 12-layer variants merge rapid question bursts,
while sat-3l-sm is exact on that common pattern and never fragments; its
only coarseness is merging colon-introduced quotations. The tokenizer
stays SaT's default (facebookAI/xlm-roberta-base), which SaT loads
without a revision argument — the one unpinned piece.
"""

from functools import lru_cache

from wtpsplit import SaT

SAT_NAME = "sat-3l-sm"
SAT_REVISION = "137da054051ad9f1eac42025f758db4ac9f22535"


@lru_cache(maxsize=1)
def _sat() -> SaT:
    return SaT(SAT_NAME, from_pretrained_kwargs={"revision": SAT_REVISION})


def segment_sentences(text: str) -> list[str]:
    """Split text into sentences using SaT default inference.

    Stripped and non-empty because SaT outputs carry trailing whitespace.
    """
    return [sentence.strip() for sentence in _sat().split(text) if sentence.strip()]
