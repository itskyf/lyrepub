# VieNeu-TTS feasibility review and frozen configuration

Human feasibility listening is complete. Together with the
`Frozen Issue #14 evaluation` subsection in the [protocol](protocol.md),
this record freezes the TTS configuration for the reported Issue #14
evaluation. No reported evaluation has run yet.

Source: *Thăng Long nổi giận* (`9786045633946`), SHA-256
`39475a49286e7a95ee4f359937811ac4de90a81472af41a0ff30005860309ef0`.
The nine cases come from [source characterization](source-characterization.md);
the protocol freezes them as the reported benchmark.

## Selected configuration

Focused pre-experiment listening selected the packaged preset **Quỳnh Anh**
(female, Northern Vietnamese, storytelling); the selection rationale is in the
[candidate survey](tts-candidate-survey.md).

The frozen synthesis path uses:

- VieNeu-TTS 3.8.3 with SEA-G2P 0.10.0. Upstream
  `normalize_to_chunks_v3_with_gaps` performs semantic text chunking before
  `phonemize_text_with_emotions`; LyrePub adds no general Vietnamese text
  normalization layer.
- SaT `sat-3l-sm` revision
  `137da054051ad9f1eac42025f758db4ac9f22535` for authored sentence targets,
  with `facebookAI/xlm-roberta-base` tokenizer revision
  `e73636d4f797dec63c3081bb6ed5c7b0bb3f2089`. Re-running all nine cases after
  pinning the tokenizer preserved **118/118 sentence text/start/end triples**.
- audio.cpp `vieneu_v3_turbo` on CUDA at revision
  `955c8725c611d511774e6be132aff6609163b2d2`, using checkpoint
  `pnnbao-ump/VieNeu-TTS-v3-Turbo` revision
  `61b85e3d937fbbacb387714180e8182823512523`
  (`vieneu-v3-turbo-bf16.gguf`, BF16 talker/F16 codec) and the packaged
  Quỳnh Anh voice assets. The synthesis script verifies the selected runtime,
  checkpoint, frontend, and voice assets before inference.
- Sampling defaults: temperature 0.8, top-k 25, top-p 0.95, repetition penalty
  1.2/window 64, max tokens 300, sampling/frame cap enabled, babble retries 2.
  The deterministic block seed is `14 + 1000 * spine_index + block_index`.
- One audio.cpp request per upstream-prepared phoneme chunk, with
  `text_chunk_size` set to that request's exact phoneme UTF-8 length so the
  runtime does not apply a second generic split. Internal chunks belonging to
  one sentence are joined with VieNeu's upstream gap handling.
- Final audio is Ogg Opus via FFmpeg 9.0.2/`libopus` at 96 kb/s. Publication
  timing uses the measured final Opus duration, not an intermediate WAV.

Exact machine-readable settings and generated frontend/timing records are
retained in `runtime.json`, `cases.json`, and `frontend-comparison.json`.

## Final processing path

```text
authored Block.text -> authored SaT sentence targets
 -> reviewed TTS-only source treatments where required
 -> VieNeu/SEA-G2P normalization
 -> upstream semantic text chunks -> SEA-G2P phonemes
 -> audio.cpp inference per prepared chunk -> upstream join per sentence
 -> final sentence Ogg Opus and [0, duration] timing
```

Authored EPUB text and source offsets remain unchanged by TTS-only treatments.

## Frozen TTS-input treatments

### Sequential slash-list enumeration

The source contains an inline sequential `1/`, `2/`, ... list whose slash
markers are spoken by SEA-G2P as fractions. The selected TTS-only treatment
changes only an observed sequential list run to comma-separated markers before
synthesis. Dates, fractions, singleton markers, and ambiguous/non-sequential
uses are unchanged, and authored XHTML is not modified.

Focused listening accepted the resulting ordered-list separation.

### s17-b135 cry

For the authored `S…át Th.. át!`, SEA-G2P 0.10.0 produces an incorrect lexical
realization. The frozen configuration therefore applies exactly one explicit
manual TTS-input correction:

```text
S…át Th.. át! -> Sát Thát!
```

The correction is recorded as required manual intervention; authored XHTML,
sentence text, and source offsets remain unchanged. The raw failed audio is
retained as evidence.

Focused listening accepted the corrected lexical pronunciation. The typography
also indicates a stronger/extended shout that the selected route does not
reproduce; this remains an **expressive-prosody limitation** rather than a
reason to add custom phonemes, emotion controls, or another generic
normalization rule.

## Feasibility findings

### Number-stutter diagnosis and fix

Earlier audio had audible stutters inside `1256` (`s5-b26`) and `1284`
(`s15-b17`). The retained `number-boundary-diagnostic.json` shows that the
audio.cpp raw-text route's generic phoneme splitter divided the normalized
number phrases:

- `một nghìn hai | trăm năm mươi sáu`;
- `một nghìn | hai trăm tám mươi tư`.

Those boundaries introduced the audible pause inside each number. The selected
fix is the pinned VieNeu semantic **text** chunking before phonemization rather
than a local number rule or a larger arbitrary chunk limit. Both number phrases
remain intact in the selected prepared requests, and focused listening confirmed
the prior stutters are resolved.

The remaining upstream semantic boundaries reviewed in `s10-b42` sentence 023
and `s12-b68` sentence 016 were also acceptable in focused listening. The
longest source case, `s5-b9`, was acceptable under sentence synthesis.

### Final human findings

These are qualitative listening observations, not scores.

| Case | Final finding |
| --- | --- |
| `s2-b70` | Ordered-list separation accepted after the narrow TTS-only treatment. |
| `s5-b9` | Long-form prosody under sentence synthesis acceptable. |
| `s5-b26` | 1256 correct; prior intra-number stutter resolved. |
| `s10-b42` | Reviewed internal synthesis boundary acceptable. |
| `s12-b30` | Reviewed year-range and foreign-name/title material acceptable. |
| `s12-b68` | Reviewed internal synthesis boundary acceptable. |
| `s15-b17` | 1284 and later internal boundary correct. |
| `s17-b135` | Corrected lexical pronunciation accepted; raw frontend failure and expressive-shout limitation retained. |
| `s18-b35` | Reviewed transliteration plus original-name material acceptable; both forms are authored source content. |

All nine cases completed preprocessing, synthesis, and Opus packaging without
runtime exceptions.

## Synchronization and publication handoff

Human playback of the repaired paragraph-level diagnostic found correct
targeting and transitions, but paragraph highlighting was too coarse for
following/navigation. **Sentence level is therefore frozen as the Media Overlay
synchronization granularity.**

Keep these units distinct:

1. authored source block;
2. one or more internal TTS chunks per sentence;
3. sentence-level publication synchronization target.

Each sentence owns one final packaged Opus file whose local timing interval is
`0` to its measured duration. Internal TTS chunk boundaries do not become
Media Overlay targets. Publication audio uses MIME
`audio/ogg; codecs=opus`.

Issue #16 owns sentence-addressable XHTML targeting. Issue #14 supplies the
frozen authored sentence identities/offsets and final Opus sentence timings.

## Reproduction and retained evidence

Set `SOURCE_EPUB`, `MODEL_GGUF`, `VOICE_DIR`, and `AUDIOCPP_IMAGE` to
the reviewed inputs, then reproduce into a fresh output directory:

```sh
OUT=data/issue-14-final-frontend-reproduction
pixi run -e dev python -m scripts.issue14_feasibility prepare --output "$OUT" --source-epub "$SOURCE_EPUB"
pixi run -e dev python -m scripts.issue14_feasibility synthesize --output "$OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR" --image "$AUDIOCPP_IMAGE"
```

The main-worktree `data/silver/issue-14/` handoff retains:

- `cases.json`, `runtime.json`, `source.json`, and
  `frontend-comparison.json`;
- the selected sentence Opus outputs, full-case listening outputs, and raw
  s17 failure;
- `number-boundary-diagnostic.json`, which supports the number-stutter
  diagnosis;
- the repaired paragraph `feasibility.epub` used for the synchronization
  granularity decision.

Intermediate audio, models, voice assets, logs, and validator images are not
duplicated into the silver handoff.

Feasibility listening is complete and this configuration is frozen for the
reported Issue #14 evaluation, which has not run.
