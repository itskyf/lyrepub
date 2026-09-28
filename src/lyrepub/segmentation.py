"""Sentence segmentation with SaT (wtpsplit).

Checkpoint segment-any-text/sat-3l-sm at revision
137da054051ad9f1eac42025f758db4ac9f22535, enforced at load time
through from_pretrained_kwargs; the tokenizer uses an immutable Hub snapshot.
Comparison evidence lives in PR #22 and the silver segmentation reports.
"""

from functools import lru_cache
from typing import cast

from huggingface_hub import snapshot_download
from wtpsplit import SaT

TOKENIZER_NAME = "facebookAI/xlm-roberta-base"
TOKENIZER_REVISION = "e73636d4f797dec63c3081bb6ed5c7b0bb3f2089"
SAT_NAME = "sat-3l-sm"
SAT_REVISION = "137da054051ad9f1eac42025f758db4ac9f22535"


@lru_cache(maxsize=1)
def _sat() -> SaT:
    tokenizer = snapshot_download(
        TOKENIZER_NAME,
        revision=TOKENIZER_REVISION,
        allow_patterns=[
            "config.json",
            "tokenizer_config.json",
            "tokenizer.json",
            "sentencepiece.bpe.model",
        ],
    )
    return SaT(
        SAT_NAME,
        tokenizer_name_or_path=tokenizer,
        from_pretrained_kwargs={"revision": SAT_REVISION},
    )


def segment_sentences(text: str) -> list[str]:
    """Split text into sentences using SaT default inference.

    Stripped and non-empty because SaT outputs carry trailing whitespace.
    """
    sentences = cast("list[str]", _sat().split(text))
    return [sentence.strip() for sentence in sentences if sentence.strip()]
