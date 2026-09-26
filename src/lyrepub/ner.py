"""Named-entity recognition with a Vietnamese ELECTRA checkpoint.

Candidate-finding aid screened for Issue #11:
NlpHUST/ner-vietnamese-electra-base (VLSP 2018 labels) through the
Transformers token-classification pipeline with simple aggregation,
revision-pinned. Known limits from screening: no tokenizer
model_max_length shipped (the model's positional limit is applied so
long inputs chunk instead of crashing), weak ORG coverage (court terms
land in MISC), and no explicit model-card license.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import cast

import torch
from transformers import TokenClassificationPipeline, pipeline

NER_MODEL = "NlpHUST/ner-vietnamese-electra-base"
NER_REVISION = "0292941f879af923edf4acf5b082b41f7492b352"


@dataclass(frozen=True, slots=True)
class Entity:
    """One recognized entity with its character span.

    Args:
        label: Entity group (PER, LOC, ORG, or MISC).
        start: Start offset into the input text.
        end: End offset into the input text.
    """

    text: str
    label: str
    start: int
    end: int


@lru_cache(maxsize=1)
def _ner() -> TokenClassificationPipeline:
    device = 0 if torch.cuda.is_available() else -1
    ner = pipeline(
        "token-classification",
        model=NER_MODEL,
        revision=NER_REVISION,
        aggregation_strategy="simple",
        device=device,
    )
    tokenizer = ner.tokenizer
    if tokenizer is None:
        msg = "token-classification pipeline has no tokenizer"
        raise RuntimeError(msg)
    tokenizer.model_max_length = ner.model.config.max_position_embeddings
    return ner


def recognize_entities(text: str) -> list[Entity]:
    """Return named entities with character spans into text.

    Long inputs are chunked with stride, so spans always address the full
    input.
    """
    return [
        Entity(
            entity["word"],
            entity["entity_group"],
            cast("int", entity["start"]),
            cast("int", entity["end"]),
        )
        for entity in _ner()(text, stride=64)
    ]
