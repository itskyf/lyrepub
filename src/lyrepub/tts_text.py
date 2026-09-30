"""Source-preserving text treatments shared by TTS workflows."""

import re


def normalize_slash_enumeration(text: str) -> str:
    """Separate ordered slash-list markers; leave ambiguous slashes unchanged."""
    markers = list(
        re.finditer(r"(?:^|(?<=[(:;.\n]))[ \t]*(\d+)/[ \t]+(?=[^\W\d_])", text)
    )
    replacements = []
    run = []
    minimum_markers = 2
    for marker in markers:
        number = int(marker.group(1))
        if run and number != int(run[-1].group(1)) + 1:
            if len(run) >= minimum_markers:
                replacements.extend(run)
            run = []
        if run or number == 1:
            run.append(marker)
    if len(run) >= minimum_markers:
        replacements.extend(run)
    for marker in reversed(replacements):
        slash = marker.end(1)
        text = text[:slash] + "," + text[slash + 1 :]
    return text


def join_sentence_boundary(
    source: str, sentences: list[str], left: int, right: int, punctuation: str
) -> None:
    """Join a reviewed punctuation split without altering the authored span."""
    boundary = left if punctuation == "-" else right
    if sentences[boundary] != punctuation:
        message = "reviewed punctuation target differs from source"
        raise ValueError(message)
    cursor = 0
    for previous in sentences[:left]:
        cursor = source.index(previous, cursor) + len(previous)
    start = source.index(sentences[left], cursor)
    end = source.index(sentences[right], start + len(sentences[left])) + len(
        sentences[right]
    )
    sentences[left : right + 1] = [source[start:end]]


def map_sentence_inputs(
    source: str,
    text_input: str,
    sentences: list[str],
    manual_normalization: dict[str, str] | None = None,
) -> list[dict]:
    """Locate authored spans before applying sentence-local synthesis text edits."""
    if len(source) != len(text_input):
        message = "enumeration treatment must preserve source offsets"
        raise ValueError(message)
    if (
        manual_normalization
        and text_input.count(manual_normalization["source_span"]) != 1
    ):
        message = "manual normalization requires exactly one observed source span"
        raise ValueError(message)
    result = []
    cursor = 0
    manual_applied = False
    for index, sentence in enumerate(sentences):
        start = source.find(sentence, cursor)
        if start < 0 or source[cursor:start].strip():
            message = "sentence segmentation lost or changed authored text"
            raise ValueError(message)
        end = start + len(sentence)
        prepared = text_input[start:end]
        if manual_normalization and manual_normalization["source_span"] in prepared:
            prepared = prepared.replace(
                manual_normalization["source_span"], manual_normalization["tts_text"]
            )
            manual_applied = True
        result.append(
            {
                "index": index,
                "source_start": start,
                "source_end": end,
                "source_text": sentence,
                "tts_input": prepared,
            }
        )
        cursor = end
    if manual_normalization and not manual_applied:
        message = "observed manual-normalization span crosses sentence targets"
        raise ValueError(message)
    if source[cursor:].strip() or not result:
        message = "sentence segmentation left authored text uncovered"
        raise ValueError(message)
    return result
