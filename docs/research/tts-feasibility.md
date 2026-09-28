# VieNeu-TTS compatibility and synchronization feasibility

Issue #14 remains in feasibility mode. Human playback review has frozen the
Media Overlay synchronization granularity at **sentence level**. Preprocessing,
synthesis-unit handling, the publication timing path, and reported runtime
configuration remain unfrozen; no reported evaluation has run.

Source: *Thăng Long nổi giận* (`9786045633946`), SHA-256
`39475a49286e7a95ee4f359937811ac4de90a81472af41a0ff30005860309ef0`.
The nine candidates come from [source characterization](source-characterization.md),
not a newly frozen benchmark. This frontend revision reruns only those nine cases.

## Selected voice, runtime, and preprocessing

Focused pre-experiment listening selected **Quỳnh Anh**, female, Northern
Vietnamese, storytelling. This replaces Thục Đoan without a voice-comparison
experiment; human review confirms the main feasibility issues remain.
The pinned package's [manifest](https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo/blob/61b85e3d937fbbacb387714180e8182823512523/gguf/voices/manifest.json)
identifies `quynh_anh`, label `Quỳnh Anh — Nữ · Bắc · Phong cách đọc truyện`,
70 reference frames. Its exact assets are:

| Package asset | SHA-256 |
| --- | --- |
| `gguf/voices/quynh_anh/ref_codes.txt` | `363b2eee93aeca4f789e1ce63ad904d7e0bef88bb20c830dd2e559ea3fe0054a` |
| `gguf/voices/quynh_anh/speaker.emb.txt` | `ab66bc624b0ffaa735c8ece1aa71b12f18b48bddc2e7cd27ba9eec3d85c2bce9` |

Both hashes are verified before synthesis, with no default-voice fallback.

```text
authored Block.text -> authored SaT sentence targets
 -> accepted ordered slash-list disambiguation (TTS only, if applicable)
 -> explicitly reviewed manual cry normalization (affected source span only)
 -> VieNeu/SEA-G2P Vietnamese normalization
 -> upstream safe normalized-text chunks -> upstream SEA-G2P phonemes
 -> one audio.cpp request per prepared chunk -> upstream PCM join per sentence
 -> final sentence Ogg Opus and its own [0, duration] interval
```

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
  adds no Vietnamese TN layer. NeMo and its OpenFST dependency/checks are removed.
- Existing SaT `sat-3l-sm` at `137da054051ad9f1eac42025f758db4ac9f22535`
  supplies outer sentence targets on authored text. Forward source offsets verify
  exact coverage with only whitespace gaps. XLM-R tokenizer
  `facebookAI/xlm-roberta-base` is now pinned to snapshot
  `e73636d4f797dec63c3081bb6ed5c7b0bb3f2089`, using Hub `snapshot_download`
  with the immutable revision and only `config.json`, `tokenizer_config.json`,
  `tokenizer.json`, `sentencepiece.bpe.model`. Pass the returned local snapshot
  to SaT's public `tokenizer_name_or_path`; no wtpsplit patch or custom loader.
  Actual rerun on all nine cases confirmed **118/118 authored sentence text,
  start and end triples identical** to the previous records. Tokenizer pinning
  did not trigger audio synthesis. Runtime metadata records the revision, not
  a machine-local cache path.
- audio.cpp `vieneu_v3_turbo`, explicit **CUDA**, revision
  `955c8725c611d511774e6be132aff6609163b2d2`. The supplied image has this
  revision but a different image ID from the preceding run. Actual current ID:
  `dcce293dbad74015a269b9d75577050372ce2743e948c4d817f11165f6556a02`.
  The image argument, ID, repository digests, and OCI revision are recorded.
  CLI version reports `dev`, Release/GCC 14.2.0, `cpu,cuda`; its embedded Git
  revision is `unknown`, so source revision verification uses the OCI label,
  while the exact image ID identifies the binary actually used.
- Checkpoint `pnnbao-ump/VieNeu-TTS-v3-Turbo`, revision
  `61b85e3d937fbbacb387714180e8182823512523`;
  `vieneu-v3-turbo-bf16.gguf`, BF16 talker/F16 codec, SHA-256
  `c9c23d51989382e27730077c2373023bcfb0891db63a1efec97fd73b4bd6b7dc`.
- Defaults unchanged: temperature 0.8, top-k 25, top-p 0.95, repetition
  penalty 1.2/window 64, max tokens 300, sampling/frame cap enabled,
  babble retries 2; subtalker follows the main sampler.
  Seed: `14 + 1000 * spine_index + block_index`, reused explicitly for each
  prepared request in that block.
- The native audio.cpp raw-text route phonemizes before its generic byte splitter;
  using that frontend alone does not resolve the diagnosed number splits. Keep
  the audited runtime pin; no required runtime feature is missing. Prepared
  phoneme requests do not supply `g2p_dict`, so native normalization is not run
  again. Set each request's `text_chunk_size` to its exact phoneme UTF-8 byte
  length, preventing a second split; zero is rejected by this runtime. This is
  derived from the prepared unit, not an arbitrarily increased chunk limit.
- Join only internal chunks belonging to one sentence with upstream
  `join_audio_chunks(..., silence_ps=gaps_to_silence(gaps))`: paragraph/sentence/
  minor minimum gaps remain 0.70/0.50/0.30 s. No custom pause/edge heuristic.
  The runtime decoder emits stereo; average its two PCM channels to mono for
  the upstream mono join interface (matching native pause measurement), without
  gain changes. The supplementary full-block listening file joins sentence PCM
  with the upstream sentence gap, 0.50 s; it is not the publication timing input.
- FFmpeg/FFprobe 9.0.2; Ogg Opus via `libopus`, 96 kb/s; duration measured
  from final Ogg and rounded consistently to milliseconds.

Source/model/voice/image locations are runtime arguments, not encoded host paths.
`cases.json` extends the previous block record with nested `sentences` and
`raw_frontend`: exact authored offsets/text, TTS input/interventions, normalized
text chunks from public upstream outputs, gap classifications, phonemes, seed, per-request
commands/logs, PCM sample counts/rate, sentence audio and final Opus intervals.
There are no invented XHTML fragment IDs. Preprocessing
and synthesis exceptions have separate statuses. Normal tests require no inference.

## Human findings from the preceding revision

These earlier listening observations remain historical evidence, not automatic
quality scores or acceptance of every newly generated file.

| Case | Human finding | Previous Quỳnh Anh Ogg seconds |
| --- | --- | ---: |
| `s10-b42` | Read correctly. | 152.266 |
| `s5-b26` | Content correct; some stutters, specifically `1256`: "một nghìn hai ... trăm năm mươi sáu". | 51.036 |
| `s15-b17` | Content/date correct; stutter within `1284`: "một nghìn ... hai trăm tám tư". | 18.256 |
| `s12-b68` | Acceptable. | 93.576 |
| `s12-b30` | Read fairly correctly. | 26.956 |
| `s18-b35` | Authored transliteration plus original names, e.g. `Quy-lê (Kulá)` / `Ta-khai Xa-ric (Tagai-sariq)`; not a TTS failure. | 35.866 |
| `s2-b70` | Numbers correct; slash markers merge perceptually into item bodies. Treatment below needs listening. | 13.556 |
| `s5-b9` | Full 3,427-character long-form/prosody material; no invented seam accounting. | 202.256 |
| `s17-b135` | Raw baseline lexical content correct; treated output omitted the cry and is rejected. | 9.566 |

These observations refer to `data/issue-14-quynh-anh-review/`, before this
frontend/synthesis-unit substitution. Generation success is not a subjective
prosody judgement. New results and listening material are below; MOSS is unused.

### General slash-enumeration treatment

Source XHTML has inline slash-number items inside a `<p>`, with no `<ol>` or
`<li>` semantics. SEA-G2P 0.10.0 on raw source yields `một trên`, `hai trên`, etc.
This source notation denotes list markers, so disambiguation remains necessary.
The narrow TTS-only rule recognizes a whole sequential run starting at `1/`,
with at least two markers, at text/line start or after `(`, `:`, `;`, or `.`;
item bodies begin with letters. Replace only those marker slashes with commas,
before sentence slices, retaining source offsets. Dates, fractions, singleton
and ambiguous non-sequential markers remain unchanged. Authored XHTML is unchanged.

Selected input yields `một, văn thù sư lỵ.`, `hai, quan thế âm.`, etc.
Human listening now accepts the comma realization: ordered-list separation is
correct. No pause parameter is tuned. Tests retain positive lists and
fraction/date/ambiguous negatives.

### Cry normalization failure, manual correction and expressive limitation

The authored context repeats "Sát Thát!" and establishes the lexical form.
Under current SEA-G2P 0.10.0, the intra-word ellipsis/multi-dot notation is folded
before standalone-letter handling. The raw `S…át Th.. át!` consequently produces
an incorrect audible realization such as letter names (`ét át th. át!` in the
normalized trace). Human review classifies this as a **frontend normalization
failure**, separately from the inability to express the stronger/extended shout.

Apply the explicitly reviewed, **manual TTS-only normalization** to exactly one
observed span in the s17-b135 feasibility case:

```text
S…át Th.. át! -> Sát Thát!
```

The source-case fixture records the correction; reusable processing has no
book-specific pronunciation rule. Authored source/XHTML, sentence text and source
offsets are unchanged. Locate each sentence on the authored source first, then
apply the correction within its TTS input before upstream normalization. Fail if
the observed span is missing, repeated or crosses sentence targets. No generic
ellipsis regex, vendor patch, custom phonemes, emotion tags or gain processing.

This changes sentence 001, authored offsets `[34, 95)`. The exact TTS input is:
`Dường như cả Thăng Long: Sát Thát! Sát Thát! Sát Thát!...`
Its upstream normalized chunk is:
`dường như cả thăng long, sát thát! sát thát! sát thát!`
Final sentence Opus duration is **3.926 s**; recombined case is **7.916 s**.
The current full-case file measures 7.916500 s with ffprobe, recorded as 7.916 s
by the existing millisecond rounding in `cases.json`.
Human listening accepts `audio/case=s17-b135,sentence=001.opus` as lexically
correct after this explicit manual intervention. Raw SEA-G2P normalization
remains a recorded failure; the upstream frontend itself has not been fixed.

Raw failed sentence audio and its trace are retained in the fresh output with
`input=raw` names. The historical replacement that caused omission under the
older pathway remains rejected evidence in `data/issue-14-feasibility-review/`;
no generic variant infrastructure is restored for this new reviewed correction.

This selected route has no documented per-span shout/loudness control. The stronger/extended cry indicated
by typography remains an **expressive-prosody limitation**.

### Accepted human findings after semantic chunking

| Reviewed target | Qualitative human finding |
| --- | --- |
| `s5-b26`, sentence 002 | 1256 is correct; previous intra-number stutter resolved. |
| `s15-b17`, sentence 001 | 1284 and the later internal boundary are correct. |
| `s2-b70` | Ordered-list separation correct; narrow slash-list -> comma treatment accepted. |
| `s5-b9` | Long-form prosody under sentence synthesis acceptable. |
| `s17-b135`, sentence 001 | Lexically correct after explicit manual normalization; stronger/extended shout remains unsupported. |

These are listening observations, not scores. No synthesis inputs or audio
changed for this documentation update.
They are removed from the pending-listening gate.

## Prior stutter diagnosis and reviewed synthesis-unit revision

Ordinary logs contain compute timings but no phoneme chunk boundaries. A
**temporary upstream CLI diagnostic**, at the pinned revision, printed the
existing `split_phoneme_chunks` result for only `s5-b26` and `s15-b17`, then
stopped before synthesis. It used the host CPU only to reach backend-independent
text splitting; all listening audio uses the unchanged CUDA runtime. No backend
comparison, custom splitter/helper, or codec seam reconstruction was performed.
Temporary diagnostic source, build, and full logs were removed. Only the two
relevant boundary pairs remain in
`data/issue-14-quynh-anh-review/number-boundary-diagnostic.json`.

| Case | Observed upstream boundary, zero-based chunk indexes | UTF-8 offsets | Diagnosis |
| --- | --- | --- | --- |
| `s5-b26`, `1256` | chunk 3 ends `một nghìn hai`; chunk 4 begins `trăm năm mươi sáu` | chunk 3 `[414, 613)`, chunk 4 `[614, 683)` | Whitespace fallback splits inside the normalized year. |
| `s15-b17`, `1284` | chunk 1 ends `một nghìn`; chunk 2 begins `hai trăm tám mươi tư` | chunk 1 `[68, 267)`, chunk 2 `[268, 312)` | Whitespace fallback splits inside the normalized year. |

Both preceding chunks are **199 bytes**, and both boundaries have `Minor`
gap classification with upstream minimum pause **0.30 s**. These lexical
boundaries coincide exactly with the supplied audible stutters. The cause is
synthesis segmentation/pause within a number phrase, not incorrect NeMo number
content. The preceding revision's phonemes equal the diagnostic inputs;
this revision changes both the frontend and synthesis units.
The diagnostic does not measure the final audible gap duration.

### Reviewed frontend and synthesis-unit revision

The review authorized semantic text chunking **before** phonemization using the
pinned upstream VieNeu implementation, rather than a local numeric-span rule.
The nine-case frontend comparison retains exact previous normalized text/phonemes,
raw SEA frontend traces, and selected sentence/chunk traces in
`data/issue-14-sea010-review/frontend-comparison.json`. Raw and treated list inputs
are distinct. The previous rejected cry replacement belongs to older pathway
evidence; the current reviewed manual correction is recorded above. The comparison
changes both the frontend and the outer request boundaries; lowercasing alone
is not evidence of an intelligibility failure.

Both diagnosed years are now indivisible within prepared requests:

- `s5-b26`, sentence 2: `một nghìn hai trăm năm mươi sáu` (1256), one chunk,
  297 phoneme UTF-8 bytes. Final sentence duration: 8.966 s.
- `s15-b17`, sentence 1, chunk 0: `một nghìn hai trăm tám mươi bốn` (1284).
  The first prepared request has 452 phoneme UTF-8 bytes; the next has 65.
  Final sentence duration: 14.716 s. Its sole internal boundary is `... sang đánh chiêm thành, | và phong cho y
  làm trấn nam vương.`, classified `minor`, outside the year phrase.

The number phrase is no longer split `hai | trăm` or `nghìn | hai` by the
200-byte native fallback. This establishes segmentation correction, not that
all audible stutter is gone by itself. Subsequent human listening confirmed
the two reviewed number phrases/boundaries are correct and the prior intra-number
stutter is resolved.

Three normalized outer sentence targets exceed the upstream default budget:

| Case / zero-based sentence | Normalized characters before packing | Final upstream chunks | Gap |
| --- | ---: | --- | --- |
| `s10-b42` / 23 | 272 | 243 + 28 | minor |
| `s12-b68` / 16 | 265 | 206 + 58 | minor |
| `s15-b17` / 1 | 267 | 232 + 34 | minor |

The pinned splitter/balancer handles them directly; no copied number-word tables,
connective rules, greedy splitter, increased default budget, or custom helper.
The longest authored block remains 3,427 characters, mapped to 40 sentence
requests; none of those outer sentences requires an internal split.

Material normalization changes requiring review include `tám mươi tư` -> `tám mươi
bốn` in 1284, numeric expression realizations, foreign-name punctuation/forms,
and ellipsis handling. Exact strings for every case, not abbreviated excerpts,
are retained in the comparison artifact. The raw cry failure and its explicitly
reviewed manual correction are distinguished above.

### Feasibility rerun results

All nine cases completed preprocessing, synthesis and Opus packaging: **118
sentence targets / 121 prepared requests**, with no runtime exceptions.
The raw cry normalization failure is retained as human-reviewed evidence.
Every recorded request uses its actual phoneme byte length as the runtime budget;
all prepared requests are single phoneme paragraphs. No custom splitter diagnostic
or ASR was required. Six focused frontend tests plus six existing generic Media
Overlay tests passed in the current revision; `hk check --pr` passed. These are deterministic/structural
checks, not listener acceptance of the regenerated audio.

| Case | Sentences | Synthesis requests | Full listening Opus seconds |
| --- | ---: | ---: | ---: |
| `s2-b70` | 9 | 9 | 15.976 |
| `s5-b9` | 40 | 40 | 203.916 |
| `s5-b26` | 9 | 9 | 51.396 |
| `s10-b42` | 25 | 26 | 152.506 |
| `s12-b30` | 5 | 5 | 27.576 |
| `s12-b68` | 17 | 18 | 91.876 |
| `s15-b17` | 2 | 3 | 18.916 |
| `s17-b135` | 3 | 3 | 7.916 |
| `s18-b35` | 8 | 8 | 36.056 |

## Frozen synchronization decision and Issue #16 handoff

Human playback found correct paragraph targets and smooth paragraph transitions,
but highlighting was too large and following/navigation too difficult for
publication use. This is direct evidence from the repaired overlay, independent
of the earlier Readest parser failure. **Sentence level is frozen as the smallest
justified finer MO synchronization unit.** No score or threshold is invented.

Keep three levels distinct:

1. Issue #12 authored source block/target;
2. one or more upstream VieNeu text chunks/phoneme requests per sentence;
3. sentence target and its final packaged-audio timing range.

Issue #16 is reopened to own publication-facing sentence-addressable XHTML
targeting/markup after #14 freezes the final sentence/timing contract.
PR #33 already provides generic timing-to-Media-Overlay publication. It must preserve authored text, inline semantics,
reading order, and visible authored heading coverage. Issue #14 owns the audio
and reproducible sentence timing requirement, not a second publication layer.
The existing #16 `Timing` contract (`text_href`, `audio_href`, `clip_begin`,
`clip_end`) can carry those ranges once targeting and the timing path are ready.
The generic implementation merged in #33 supports `.opus` with the exact MIME
`audio/ogg; codecs=opus`; the new feasibility audio uses that suffix.

Each sentence is synthesized independently and owns one final packaged file.
Its eventual `Timing` interval is `0` to that file's measured duration, with
PCM sample count/rate retained for verification. Internal TTS boundaries do not
become Media Overlay targets. No ASR/forced alignment is needed for this arrangement.
Issue #14 stops at reviewed sentence source identities/offsets, TTS preparation,
synthesis units and reproducible final Opus sentence intervals. Missing XHTML
fragments are **Issue #16 ownership**, not work added to PR #32. It will map the
frozen sentence/timing records to addressable `text_href` values later. No spans,
IDs, targeting changes or generic publisher changes are made here.

The tokenizer, runtime, frontend and synthesis-unit mechanics are reproducibly
specified, and the accepted components are ready for freeze. Full configuration
freeze still awaits the remaining foreign/date, mixed-name and boundary
listening findings. This pass does not freeze them or run reported evaluation.

## Diagnostic EPUB and validation

The preceding revision's diagnostic excerpt retains copied authored paragraphs for `s5-b8–10` and
`s10-b41–43`. It is a **diagnostic paragraph artifact**, not the frozen publication
granularity and not evidence that sentence playback has been implemented.
Synthetic visible chapter `<h1>` elements were removed. The script-created
"Chương 11: lời kể" was not authored text; its absence from narration was not
TTS omission. Final publication must synchronize authored visible headings.

Audio uses exact MIME `audio/ogg; codecs=opus`; every SMIL audio has explicit
`clipBegin`/`clipEnd` from final Ogg durations. Overall duration is **465.316 s**;
refined overlay durations are **287.788 s** and **177.528 s**, summing consistently.
Metadata declares textual access/sufficiency, synchronizedAudioText, no hazards,
and a truthful summary of the rejected paragraph granularity. No accessibility
conformance claim is made.

Reused existing images, with no rebuild: **EPUBCheck 5.4.0**, zero errors/warnings;
**Ace 1.4.6**, pass/no issues. No system application/package or reader changes.
No new reader retest is needed to revisit the accepted human granularity decision.

## Reproduce and review gate

Find the main worktree with `git worktree list`; read its source EPUB directly.
Set `SOURCE_EPUB`, `MODEL_GGUF`, `VOICE_DIR` (verified Quỳnh Anh assets), and
`AUDIOCPP_IMAGE` as runtime inputs. Full reproduction uses an unused output
directory, separately from the review artifacts:

```sh
OUT=data/issue-14-final-frontend-reproduction
pixi run -e dev python -m scripts.issue14_feasibility prepare --output "$OUT" --source-epub "$SOURCE_EPUB"
pixi run -e dev python -m scripts.issue14_feasibility synthesize --output "$OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR" --image "$AUDIOCPP_IMAGE"
pixi run -e dev python -m pytest tests/test_issue14_feasibility.py tests/test_epub_media_overlays.py -q
hk check --pr
```

For this incremental pass, **117 unchanged sentence audio files are copied
byte-for-byte** from `data/issue-14-sea010-review/` into the fresh directory;
only s17-b135 sentence 001 is synthesized again with the existing helpers.
Rejoin its case with the unchanged sentence 000/002 PCM and repackage the case.
No other model inference or codec re-encoding is required. Source text/offset
triples and unchanged chunks/phonemes/gaps are checked before synthesis; an
observed segmentation difference stops the pass and is reported before audio work.
Runtime metadata retains the 118-target identity result and manual correction.

Per-case/sentence/chunk audio and log names use comma-separated `key=value`
components, with three-digit sentence and two-digit chunk indexes. Aggregate
`cases.json`, `runtime.json`, `source.json`, `frontend-comparison.json` names
remain unchanged. Reused request commands/logs retain their original execution
output names; record audio paths refer to the fresh, renamed byte-identical files.
This is one-time artifact staging, without migration compatibility or a layout
abstraction. The unused private normalization trace field is removed explicitly;
public normalized chunks and phonemes remain the frontend evidence.

Pending listening paths under `data/silver/issue-14/` in the **main worktree**:

- `audio/case=s12-b30,sentence=000.opus`: year range/foreign-name normalization.
- `audio/case=s12-b30,sentence=002.opus`: Koubilay and surrounding foreign text.
- `audio/case=s12-b30,sentence=004.opus`: French title/name pronunciation.
- `audio/case=s18-b35,sentence=005.opus`: authored transliteration plus original
  forms remain source behavior; listen to the changed frontend realization.
- `audio/case=s10-b42,sentence=023.opus`: internal synthesis boundary.
- `audio/case=s12-b68,sentence=016.opus`: internal synthesis boundary.

Raw failure: `audio/case=s17-b135,sentence=001,input=raw.opus`, with matching raw
frontend/chunk/request evidence in `cases.json`. Optional full corrected case:
`audio/case=s17-b135.opus`.
Already accepted 1256, 1284, list separation, full long-block audio and corrected
cry pronunciation are not pending listening; their synthesis inputs/audio did not change.

Exact normalized outputs, phonemes, requests and final timings are retained in
`cases.json` and `frontend-comparison.json`; actual pins/settings are in
`runtime.json`. Sentence indexes identify logical source targets, not XHTML IDs.
No subjective score or acceptance is inferred from successful generation.

The main-worktree `data/silver/issue-14/` handoff retains the four aggregate JSON
files unchanged and all **128 final Opus files**: 118 selected sentences, nine
full cases and the raw cry failure. All 118 source text/offset triples and
packaged-audio references/intervals were verified. Intermediate WAV/log references
in the records describe historical execution; those files are intentionally not
copied. Issue #16 can consume `packaged_audio` and final sentence intervals.

Two unique earlier artifacts are retained alongside them:
`number-boundary-diagnostic.json` from `issue-14-quynh-anh-review/`, and
`feasibility.epub` from `issue-14-feasibility-review/`. The latter is the repaired
paragraph-level artifact used for the human granularity decision (481.036 s,
including synthetic headings), preceding the later 465.316 s diagnostic described
above. No intermediate audio, models, assets, logs or validator images are staged.

Docker bake and validator-image work are retained. No new EPUB, EPUBCheck, Ace,
reader test, system application/package change or Issue #16 implementation is
required in this pass. Historical validator results apply only to the unchanged
historical diagnostic EPUB.

Stop for human review. Issue #14 remains open until configuration/timing freeze
and reported evaluation complete; no reported run has started.
