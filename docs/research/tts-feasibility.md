# VieNeu-TTS feasibility review and frozen configuration

Human feasibility review is complete, and the configuration below is frozen for the reported Issue #14 evaluation.
No reported evaluation has run yet.
The nine benchmark cases come from [source characterization](source-characterization.md), and the methodological freeze is recorded in the [protocol](protocol.md).

## Selected configuration

Focused pre-experiment listening selected the packaged **Quỳnh Anh** preset; the selection rationale is in the [candidate survey](tts-candidate-survey.md).
The frozen frontend uses VieNeu-TTS 3.8.3 with SEA-G2P 0.10.0 and upstream semantic text chunking before phonemization.
Authored sentence targets use SaT `sat-3l-sm` revision `137da054051ad9f1eac42025f758db4ac9f22535` with `facebookAI/xlm-roberta-base` tokenizer revision `e73636d4f797dec63c3081bb6ed5c7b0bb3f2089`.
Re-running the nine cases after pinning the tokenizer preserved all **118/118 sentence text/start/end triples**.
Synthesis uses audio.cpp `vieneu_v3_turbo` on CUDA at revision `955c8725c611d511774e6be132aff6609163b2d2` with checkpoint `pnnbao-ump/VieNeu-TTS-v3-Turbo` revision `61b85e3d937fbbacb387714180e8182823512523` and the packaged Quỳnh Anh voice.
Each upstream-prepared phoneme chunk is rendered as one audio.cpp request so the runtime does not introduce a second generic split.
Internal chunks belonging to one sentence are joined with VieNeu's upstream gap handling.
Final publication audio is Ogg Opus, and sentence timing is measured from the final packaged Opus rather than an intermediate WAV.
Exact inference settings, asset verification, frontend records, and sentence timings are retained in `runtime.json`, `cases.json`, and `frontend-comparison.json`.

## Processing path

```text
authored block
 -> authored sentence targets
 -> reviewed TTS-only input treatment where required
 -> VieNeu/SEA-G2P normalization and semantic chunking
 -> phonemization
 -> audio.cpp inference
 -> sentence Opus
 -> sentence [0, duration] timing
```

TTS-only treatments do not modify authored EPUB text or source offsets.

## Frozen TTS-input treatments

### s2-b70 slash-list markers

The authored paragraph contains a sequential list written as `1/ Văn Thù...`, `2/ Quan Thế âm...`, and similar items.
SEA-G2P reads the raw markers as fractions such as `một trên` and `hai trên`, so the item numbers run into the following item text instead of sounding like list markers.
The selected TTS-only treatment changes only this observed sequential marker pattern from slash to comma before synthesis.
Dates, fractions, singleton markers, and ambiguous or non-sequential uses are left unchanged.
Focused listening confirmed that the treated output separates the list items correctly.

### s17-b135 cry

SEA-G2P 0.10.0 gives an incorrect lexical realization for the authored `S…át Th.. át!`.
The frozen configuration therefore applies exactly one explicit manual TTS-input correction:

```text
S…át Th.. át! -> Sát Thát!
```

The correction is reported as required manual intervention, while authored XHTML, sentence text, and source offsets remain unchanged.
Focused listening accepted the corrected lexical pronunciation.
The raw failed audio is retained as evidence.
The stronger or extended shout suggested by the typography is not reproduced and remains an expressive-prosody limitation.

## Number-stutter diagnosis and fix

Earlier audio split `1256` as `một nghìn hai | trăm năm mươi sáu` and `1284` as `một nghìn | hai trăm tám mươi tư`, producing audible pauses inside the numbers.
The retained `number-boundary-diagnostic.json` records those raw audio.cpp splitter boundaries.
The selected fix is VieNeu's upstream semantic **text** chunking before phonemization rather than a number-specific rule or an arbitrary larger chunk limit.
Focused listening confirmed that both number stutters are resolved.
The remaining reviewed internal boundaries in `s10-b42` sentence 023 and `s12-b68` sentence 016 were also acceptable.

## Final feasibility findings

These are qualitative listening observations, not scores.

| Case | Final finding |
| --- | --- |
| `s2-b70` | Raw slash-number markers were read as fractions; the narrow TTS-only slash-to-comma treatment produced clear list-item separation. |
| `s5-b9` | Long-form prosody under sentence synthesis was acceptable. |
| `s5-b26` | 1256 was correct after semantic chunking; the prior intra-number stutter was resolved. |
| `s10-b42` | The reviewed internal synthesis boundary was acceptable. |
| `s12-b30` | Reviewed year-range and foreign-name/title material was acceptable. |
| `s12-b68` | The reviewed internal synthesis boundary was acceptable. |
| `s15-b17` | 1284 and the later internal boundary were correct. |
| `s17-b135` | The corrected lexical pronunciation was accepted; the raw frontend failure and expressive-shout limitation remain recorded. |
| `s18-b35` | Reviewed transliteration plus original-name material was acceptable; both forms are authored source content. |

All nine cases completed preprocessing, synthesis, and Opus packaging without runtime exceptions.

## Synchronization handoff

Human playback of the paragraph-level diagnostic found correct targeting and transitions but paragraph highlighting was too coarse for following and navigation.
Sentence level is therefore frozen as the Media Overlay synchronization granularity.
Source blocks, internal TTS chunks, and publication synchronization targets remain distinct units.
Each sentence owns one final Opus file with a local timing interval from zero to its measured duration.
Internal TTS chunk boundaries do not become Media Overlay targets.
Issue #16 owns sentence-addressable XHTML targeting and consumes the frozen sentence identities, offsets, and Opus timings produced by Issue #14.

## Reproduction and retained evidence

Set `SOURCE_EPUB`, `MODEL_GGUF`, `VOICE_DIR`, and `AUDIOCPP_IMAGE` to the reviewed inputs and reproduce into a fresh output directory:

```sh
OUT=data/issue-14-final-frontend-reproduction
pixi run -e dev python -m scripts.issue14_feasibility prepare --output "$OUT" --source-epub "$SOURCE_EPUB"
pixi run -e dev python -m scripts.issue14_feasibility synthesize --output "$OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR" --image "$AUDIOCPP_IMAGE"
```

The retained `data/silver/issue-14/` handoff contains the JSON records needed to reproduce and inspect the frozen run, the selected Opus outputs, the raw s17 failure, `number-boundary-diagnostic.json`, and the paragraph diagnostic EPUB used for the granularity decision.
Intermediate audio, models, voice assets, logs, and validator images are not duplicated into the silver handoff.
