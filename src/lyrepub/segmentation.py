"""Sentence segmentation with SaT (wtpsplit).

Checkpoint segment-any-text/sat-3l-sm at revision
137da054051ad9f1eac42025f758db4ac9f22535, enforced at load time
through from_pretrained_kwargs; comparison evidence lives in PR #22 and
the silver segmentation reports. SaT loads its default tokenizer
(facebookAI/xlm-roberta-base) without a revision argument — the one
unpinned piece.
"""

from functools import lru_cache
from typing import cast

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
    sentences = cast("list[str]", _sat().split(text))
    return [sentence.strip() for sentence in sentences if sentence.strip()]
