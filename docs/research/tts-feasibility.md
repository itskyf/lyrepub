# VieNeu-TTS feasibility review and frozen configuration

Human feasibility listening is complete. Together with the
`Frozen Issue #14 evaluation` subsection in the [protocol](protocol.md),
this record freezes the TTS configuration for the reported Issue #14
evaluation. No reported evaluation has run yet.

Source: *Thăng Long nổi giận* (`9786045633946`), SHA-256
`39475a49286e7a95ee4f359937811ac4de90a81472af41a0ff30005860309ef0`.
The nine cases come from [source characterization](source-characterization.md);
the protocol freezes them as the reported benchmark.

## Selected voice, model, runtime, and frontend

Focused pre-experiment listening selected **Quỳnh Anh**, female, Northern
Vietnamese, storytelling; the selection rationale is in the
[candidate survey](tts-candidate-survey.md). The pinned package's
[manifest](https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo/blob/61b85e3d937fbbacb387714180e8182823512523/gguf/voices/manifest.json)
identifies `quynh_anh`, label `Quỳnh Anh — Nữ · Bắc · Phong cách đọc truyện`,
70 reference frames. Its exact assets are:

| Package asset | SHA-256 |
| --- | --- |
| `gguf/voices/quynh_anh/ref_codes.txt` | `363b2eee93aeca4f789e1ce63ad904d7e0bef88bb20c830dd2e559ea3fe0054a` |
| `gguf/voices/quynh_anh/speaker.emb.txt` | `ab66bc624b0ffaa735c8ece1aa71b12f18b48bddc2e7cd27ba9eec3d85c2bce9` |

Both hashes are verified before synthesis, with no default-voice fallback.

- [VieNeu-TTS 3.8.3](https://github.com/pnnbao97/VieNeu-TTS/tree/c1390abbdb2eedcdf58eafb546966c06ce27af71),
  revision `c1390abbdb2eedcdf58eafb546966c06ce27af71`;
  wheel SHA-256 `7388d166e65746f5bb075bf8094d324f8131a82393680b712260d6f2f983ef06`.
  Import its utility functions, without initializing a Python speech model.
- [SEA-G2P 0.10.0](https://pypi.org/project/sea-g2p/0.10.0/), revision
  `dae5ca83ea45f356c43bdb70a1bcd42e8729ff16`; Linux wheel SHA-256
  `020121dd6af8ae707e2d3b946730b501c48400e3b1135f7b16233f44610c022e`.
  Installed `sea_g2p.bin` SHA-256, checked before synthesis:
  `4346e690d0711ebc5231e7a42c5c88aaf6e40377e894b4617c018fd81c6f4096`.
- Use upstream `normalize_to_chunks_v3_with_gaps` defaults (256 normalized
  characters, minimum 20), then `phonemize_text_with_emotions`, exactly the
  pinned v3 frontend path. Its normalization before packing retains punctuation;
  final chunks receive upstream punctuation normalization. Phonemization follows
  upstream combined SEA-G2P behavior, including its normalization call. LyrePub
  adds no Vietnamese TN layer.
- Existing SaT `sat-3l-sm` at `137da054051ad9f1eac42025f758db4ac9f22535`
  supplies outer sentence targets on authored text. Forward source offsets verify
  exact coverage with only whitespace gaps. XLM-R tokenizer
  `facebookAI/xlm-roberta-base` is pinned to snapshot
  `e73636d4f797dec63c3081bb6ed5c7b0bb3f2089`, using Hub `snapshot_download`
  with the immutable revision and only `config.json`, `tokenizer_config.json`,
  `tokenizer.json`, `sentencepiece.bpe.model`, passed to SaT's public
  `tokenizer_name_or_path`; no wtpsplit patch or custom loader. A rerun on all
  nine cases confirmed **118/118 authored sentence text, start and end triples
  identical** to the previous records. Runtime metadata records the revision,
  not a machine-local cache path.
- audio.cpp `vieneu_v3_turbo`, explicit **CUDA**, revision
  `955c8725c611d511774e6be132aff6609163b2d2`; the OCI revision is verified
  before synthesis. CLI version reports `dev`, Release/GCC 14.2.0,
  `cpu,cuda`.
- Checkpoint `pnnbao-ump/VieNeu-TTS-v3-Turbo`, revision
  `61b85e3d937fbbacb387714180e8182823512523`;
  `vieneu-v3-turbo-bf16.gguf`, BF16 talker/F16 codec, SHA-256
  `c9c23d51989382e27730077c2373023bcfb0891db63a1efec97fd73b4bd6b7dc`.
- Defaults unchanged: temperature 0.8, top-k 25, top-p 0.95, repetition
  penalty 1.2/window 64, max tokens 300, sampling/frame cap enabled,
  babble retries 2; subtalker follows the main sampler.
  Seed: `14 + 1000 * spine_index + block_index`, reused explicitly for each
  prepared request in that block.
- The native audio.cpp raw-text route phonemizes before its generic byte
  splitter; using that frontend alone does not resolve the diagnosed number
  splits, so the audited runtime pin is kept. Prepared phoneme requests do not
  supply `g2p_dict`, so native normalization is not run again. Set each
  request's `text_chunk_size` to its exact phoneme UTF-8 byte length,
  preventing a second split; zero is rejected by this runtime. This is derived
  from the prepared unit, not an arbitrarily increased chunk limit.
- Join only internal chunks belonging to one sentence with upstream
  `join_audio_chunks(..., silence_ps=gaps_to_silence(gaps))`: paragraph/sentence/
  minor minimum gaps remain 0.70/0.50/0.30 s. No custom pause/edge heuristic.
  The runtime decoder emits stereo; average its two PCM channels to mono for
  the upstream mono join interface, without gain changes.
- FFmpeg/FFprobe 9.0.2; Ogg Opus via `libopus`, 96 kb/s; duration measured
  from final Ogg and rounded consistently to milliseconds.

Source/model/voice/image locations are runtime arguments, not encoded host paths.

## Final processing path

```text
authored Block.text -> authored SaT sentence targets
 -> accepted ordered slash-list disambiguation (TTS only, if applicable)
 -> explicitly reviewed manual cry normalization (affected source span only)
 -> VieNeu/SEA-G2P Vietnamese normalization
 -> upstream safe normalized-text chunks -> upstream SEA-G2P phonemes
 -> one audio.cpp request per prepared chunk -> upstream PCM join per sentence
 -> final sentence Ogg Opus and its own [0, duration] interval
```

`cases.json` extends the block record with nested `sentences` and
`raw_frontend`: exact authored offsets/text, TTS input/interventions, normalized
text chunks from public upstream outputs, gap classifications, phonemes, seed,
per-request commands/logs, PCM sample counts/rate, sentence audio and final
Opus intervals. There are no invented XHTML fragment IDs. Preprocessing and
synthesis exceptions have separate statuses. Normal tests require no inference.

## Frozen TTS-input treatments

### Sequential slash-list enumeration

Source XHTML has inline slash-number items inside a `<p>`, with no `<ol>` or
`<li>` semantics. SEA-G2P 0.10.0 on raw source yields `một trên`, `hai trên`,
etc. This source notation denotes list markers, so disambiguation remains
necessary. The narrow TTS-only rule recognizes a whole sequential run starting
at `1/`, with at least two markers, at text/line start or after `(`, `:`, `;`,
or `.`; item bodies begin with letters. Replace only those marker slashes with
commas, before sentence slices, retaining source offsets. Dates, fractions,
singleton and ambiguous non-sequential markers remain unchanged. Authored XHTML
is unchanged.

Selected input yields `một, văn thù sư lỵ.`, `hai, quan thế âm.`, etc. Human
listening accepts the comma realization: ordered-list separation is correct.
No pause parameter is tuned. Tests retain positive lists and
fraction/date/ambiguous negatives.

### s17-b135 cry: raw failure, manual correction, expressive limitation

The authored context repeats "Sát Thát!" and establishes the lexical form.
Under current SEA-G2P 0.10.0, the intra-word ellipsis/multi-dot notation is
folded before standalone-letter handling. The raw `S…át Th.. át!` consequently
produces an incorrect audible realization such as letter names (`ét át th. át!`
in the normalized trace). Human review classifies this as a **frontend
normalization failure**, separately from the inability to express the
stronger/extended shout.

Apply the explicitly reviewed, **manual TTS-only normalization** to exactly one
observed span in the s17-b135 case:

```text
S…át Th.. át! -> Sát Thát!
```

The source-case fixture records the correction; reusable processing has no
book-specific pronunciation rule. Authored source/XHTML, sentence text and
source offsets are unchanged. Locate each sentence on the authored source
first, then apply the correction within its TTS input before upstream
normalization. Fail if the observed span is missing, repeated or crosses
sentence targets. No generic ellipsis regex, vendor patch, custom phonemes,
emotion tags or gain processing. The historical replacement that caused
omission under the older pathway remains rejected; no generic variant
infrastructure is restored for this reviewed correction.

This changes sentence 001, authored offsets `[34, 95)`. The exact TTS input is:
`Dường như cả Thăng Long: Sát Thát! Sát Thát! Sát Thát!...`
Human listening accepts `audio/case=s17-b135,sentence=001.opus` as lexically
correct after this explicit manual intervention, reported as required manual
correction. Raw SEA-G2P normalization remains a recorded failure; the upstream
frontend itself has not been fixed. Raw failed sentence audio and its trace are
retained with `input=raw` names.

This selected route has no documented per-span shout/loudness control. The
stronger/extended cry indicated by typography remains an
**expressive-prosody limitation**.

## Number-stutter root cause and semantic-chunking fix

Human listening found intra-number stutters in `1256` (`s5-b26`,
"một nghìn hai ... trăm năm mươi sáu") and `1284` (`s15-b17`,
"một nghìn ... hai trăm tám mươi tư"). The retained
`number-boundary-diagnostic.json` records the two relevant upstream
`split_phoneme_chunks` boundary pairs.

Both diagnosed boundaries fell at **199-byte** chunks where the upstream
whitespace fallback splits inside the normalized number phrase — `s5-b26`:
chunk 3 ends `một nghìn hai`, chunk 4 begins `trăm năm mươi sáu`; `s15-b17`:
chunk 1 ends `một nghìn`, chunk 2 begins `hai trăm tám mươi tư` — each with
`Minor` gap classification and upstream minimum pause **0.30 s**. These
lexical boundaries coincided exactly with the audible stutters: the cause is
synthesis segmentation/pause within a number phrase, not incorrect number
content. The diagnostic shows boundary placement, not the final audible gap
duration.

The reviewed fix is semantic text chunking **before** phonemization using the
pinned upstream VieNeu implementation, rather than a local numeric-span rule.
Both diagnosed years are now indivisible within prepared requests:

- `s5-b26`, sentence 2: `một nghìn hai trăm năm mươi sáu` (1256), one chunk,
  297 phoneme UTF-8 bytes.
- `s15-b17`, sentence 1, chunk 0: `một nghìn hai trăm tám mươi bốn` (1284);
  the first prepared request has 452 phoneme UTF-8 bytes. Its sole internal
  boundary is `... sang đánh chiêm thành, | và phong cho y làm trấn nam vương.`,
  classified `minor`, outside the year phrase.

Human listening confirmed both reviewed number phrases/boundaries are correct
and the prior intra-number stutter is resolved.

Three normalized outer sentence targets exceed the upstream default packing
budget and are split by the pinned upstream splitter/balancer, with no copied
number-word tables, connective rules, greedy splitter, increased default
budget, or custom helper:

| Case / zero-based sentence | Normalized characters before packing | Final upstream chunks | Gap |
| --- | ---: | --- | --- |
| `s10-b42` / 23 | 272 | 243 + 28 | minor |
| `s12-b68` / 16 | 265 | 206 + 58 | minor |
| `s15-b17` / 1 | 267 | 232 + 34 | minor |

The longest authored block remains 3,427 characters, mapped to 40 sentence
requests; none of those outer sentences requires an internal split.

Material normalization changes reviewed by listening include `tám mươi tư` ->
`tám mươi bốn` in 1284, numeric expression realizations, foreign-name
punctuation/forms, and ellipsis handling. Exact strings for every case, not
abbreviated excerpts, are retained in `frontend-comparison.json`.

## Final human findings

These are listening observations, not scores; generation success is not a
subjective prosody judgement. Listening on the preceding revision found the
case content correct apart from the two intra-number stutters (resolved
above); the cry case is recorded above as a raw frontend failure with its
reviewed correction. All nine cases completed
preprocessing, synthesis and Opus packaging: **118 sentence targets /
121 prepared requests**, no runtime exceptions. Every recorded request uses its
actual phoneme byte length as the runtime budget; all prepared requests are
single phoneme paragraphs.

| Case | Sentences | Requests | Full-case Opus s | Final human finding |
| --- | ---: | ---: | ---: | --- |
| `s2-b70` | 9 | 9 | 15.976 | Ordered-list separation correct; narrow slash-list -> comma treatment accepted. |
| `s5-b9` | 40 | 40 | 203.916 | Long-form prosody under sentence synthesis acceptable. |
| `s5-b26` | 9 | 9 | 51.396 | 1256 correct (sentence 002); prior intra-number stutter resolved. |
| `s10-b42` | 25 | 26 | 152.506 | Sentence 023 internal synthesis boundary acceptable in focused listening. |
| `s12-b30` | 5 | 5 | 27.576 | Sentences 000/002/004 (year range/foreign names, Koubilay context, French title/name) acceptable in focused listening. |
| `s12-b68` | 17 | 18 | 91.876 | Sentence 016 internal synthesis boundary acceptable in focused listening. |
| `s15-b17` | 2 | 3 | 18.916 | 1284 and the later internal boundary correct (sentence 001). |
| `s17-b135` | 3 | 3 | 7.916 | Sentence 001 lexically correct after the explicit manual normalization; raw input remains a recorded frontend failure; stronger/extended shout unsupported. |
| `s18-b35` | 8 | 8 | 36.056 | Sentence 005 acceptable in focused listening; authored transliteration plus original forms remain source behavior. |

Six focused frontend tests plus six existing generic Media Overlay tests and
`hk check --pr` pass; these are deterministic/structural checks, not listener
acceptance.

## Synchronization granularity, timing semantics, and Issue #16 handoff

Human playback of a repaired paragraph-level overlay found correct paragraph
targets and smooth paragraph transitions, but highlighting was too large and
following/navigation too difficult for publication use. **Sentence level is
frozen as the smallest justified finer Media Overlay synchronization unit.**
No score or threshold is invented. The diagnostic paragraph artifact is not
the frozen publication granularity and not evidence that sentence playback has
been implemented; synthetic headings in it were not authored text, and their
absence from narration was not TTS omission. Final publication must synchronize
authored visible headings.

Keep three levels distinct:

1. Issue #12 authored source block/target;
2. one or more upstream VieNeu text chunks/phoneme requests per sentence;
3. sentence target and its final packaged-audio timing range.

Each sentence is synthesized independently and owns one final packaged file.
Its eventual `Timing` interval is `0` to that file's measured duration, with
PCM sample count/rate retained for verification. Internal TTS boundaries do
not become Media Overlay targets. No ASR/forced alignment is needed for this
arrangement. Audio uses the exact MIME `audio/ogg; codecs=opus` supported by
the generic timing-to-Media-Overlay publisher merged in #33.

Issue #16 owns publication-facing sentence-addressable XHTML targeting and will
map these frozen sentence source identities/offsets and final Opus intervals to
addressable XHTML targets. The generic publisher merged in #33 consumes the
resulting timings. Issue #14 stops at the reviewed sentence identities,
synthesis units, and reproducible final Opus intervals.

The paragraph diagnostic used for the granularity decision passed EPUBCheck
5.4.0 and Ace 1.4.6. Those validator results apply only to that diagnostic
artifact, not to the final publication.

## Reproduction and retained evidence

Set `SOURCE_EPUB`, `MODEL_GGUF`, `VOICE_DIR` (verified Quỳnh Anh assets),
and `AUDIOCPP_IMAGE` as runtime inputs. Full reproduction uses an unused output
directory, separately from retained evidence:

```sh
OUT=data/issue-14-final-frontend-reproduction
pixi run -e dev python -m scripts.issue14_feasibility prepare --output "$OUT" --source-epub "$SOURCE_EPUB"
pixi run -e dev python -m scripts.issue14_feasibility synthesize --output "$OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR" --image "$AUDIOCPP_IMAGE"
pixi run -e dev python -m pytest tests/test_issue14_feasibility.py tests/test_epub_media_overlays.py -q
hk check --pr
```

The `data/silver/issue-14/` handoff retains the four aggregate JSON files
(`cases.json`, `runtime.json`, `source.json`, `frontend-comparison.json`) and
all **128 final Opus files**: 118 selected sentences, nine full cases, and the
raw cry failure (`audio/case=s17-b135,sentence=001,input=raw.opus`). All 118
source text/offset triples and packaged-audio references/intervals were
verified. Actual pins/settings are in `runtime.json`; exact normalized outputs,
phonemes, requests and final timings are in `cases.json` and
`frontend-comparison.json`. Intermediate WAV/log references in the records
describe historical execution; those files are intentionally not copied.
Sentence indexes identify logical source targets, not XHTML IDs.

Two unique earlier artifacts are retained alongside them:
`number-boundary-diagnostic.json` (the two stutter boundary pairs) and
`feasibility.epub` (the repaired paragraph-level artifact used for the human
granularity decision). No intermediate audio, models, assets, logs or validator
images are staged.

Feasibility listening is complete and the configuration above is frozen for the
reported Issue #14 evaluation, which has not run.
