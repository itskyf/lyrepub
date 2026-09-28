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
 -> confirmed ordered slash-list disambiguation (TTS only, if applicable)
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
  exact coverage with only whitespace gaps. Its existing default XLM-R tokenizer
  remains unpinned; this pre-existing reproducibility limitation must be reviewed
  before the reported configuration freeze.
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
parts and final text chunks, gap classifications, phonemes, seed, per-request
commands/logs, PCM sample counts/rate, sentence audio and final Opus intervals.
There are no invented XHTML fragment IDs. Preprocessing
and synthesis exceptions have separate statuses. Normal tests require no inference.

## Human findings from the preceding revision

These are the latest supplied listening observations, not automatic quality
scores or acceptance of every newly generated file.

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
The comma realization remains provisional pending listening. No pause parameter
is tuned. Tests retain positive lists and fraction/date/ambiguous negatives.

### Rejected cry treatment and expressive limitation

The complete paragraph and nearby context repeat the crowd cry "Sát Thát!".
Authored `S…át Th.. át!` depicts a later stronger/extended cry. Human review
confirmed raw lexical content is correct, despite letter-name fragments in the
intermediate phonemes. Those fragments alone are not proof of audible failure.

The attempted TTS-only replacement with `Sát Thát!` caused omission, so it is
rejected. Historical raw/treated evidence remains in
`data/issue-14-feasibility-review/`; the variant JSON, CLI option, and helper
have been removed. The selected pathway uses authored raw text.

This route has no documented per-span shout/loudness control. Its inability to
express the stronger later cry is an **expressive-prosody limitation**, not a
pronunciation failure. No emotion tags, SSML, gain, or volume processing is added.

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
are distinct; the rejected cry replacement is not reapplied. The comparison
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
all audible stutter is gone. Remaining stutter without such a boundary would be
acoustic/model evidence; do not add another preprocessing fix without review.

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
are retained in the comparison artifact. In particular the raw cry now includes
`ét át th. át!`; do not assume the previous raw lexical judgement transfers to
new audio, or introduce a replacement treatment.

### Feasibility rerun results

All nine cases completed preprocessing, synthesis and Opus packaging: **118
sentence targets / 121 prepared requests**, with no retained stage failures.
Every recorded request uses its actual phoneme byte length as the runtime budget;
all prepared requests are single phoneme paragraphs. No custom splitter diagnostic
or ASR was required. Four focused frontend tests plus six existing generic Media
Overlay tests passed; `hk check --pr` passed. These are deterministic/structural
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
| `s17-b135` | 3 | 3 | 8.736 |
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

Issue #16 owns publication-facing sentence-addressable XHTML targeting/markup
and generic Media Overlays. It must preserve authored text, inline semantics,
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
**Remaining publication integration:** real sentence-addressable XHTML fragments
are still required before constructing `text_href` values and invoking the generic
publisher. This PR does not invent fragment IDs or duplicate the publication layer.
Frontend, synthesis-unit handling and the complete timing path still await review.

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
`AUDIOCPP_IMAGE` as runtime inputs. Use a fresh output directory when settings change.

```sh
OUT=data/issue-14-sea010-review
pixi run -e dev python -m scripts.issue14_feasibility prepare --output "$OUT" --source-epub "$SOURCE_EPUB"
pixi run -e dev python -m scripts.issue14_feasibility synthesize --output "$OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR" --image "$AUDIOCPP_IMAGE"
pixi run -e dev python -m pytest tests/test_issue14_feasibility.py tests/test_epub_media_overlays.py -q
hk check --pr
```

The obsolete paragraph publisher and its tests are removed; the historical EPUB
and validator reports remain under `data/issue-14-quynh-anh-review/`. No EPUB is
regenerated by this frontend pass, so the previous EPUBCheck 5.4.0/Ace 1.4.6 results
apply only to that historical artifact. Generic publication code/tests come from
PR #33, without duplicate markup or a second Media Overlay implementation.

Gitignored new listening material under `data/issue-14-sea010-review/audio/`:

- `s5-b26-sentence-002.opus`: 1256 pronunciation and absence/persistence of stutter.
- `s15-b17-sentence-001.opus`: 1284 and its later internal connective boundary.
- `s2-b70.opus`: selected sequential-list comma separation.
- `s17-b135.opus`: raw punctuation/ellipsis and expressive-prosody limitation.
- `s12-b30-sentence-000.opus`, `s12-b30-sentence-002.opus`,
  `s12-b30-sentence-004.opus`: date range and French/foreign names.
- `s18-b35-sentence-005.opus`: changed hyphen/parenthesis realization of mixed
  names; authored transliteration plus original names remain source behavior.
- `s5-b9.opus`: full long-block prosody with sentence requests.
- `s10-b42-sentence-023.opus`, `s12-b68-sentence-016.opus`: the other two
  sentence targets now containing internal chunks. Review their new boundaries;
  the previously accepted ordinary text is not relabeled a TTS failure.

All exact normalized outputs, phonemes, internal chunks, PCM/final-media intervals,
commands and logs are in `cases.json`, `frontend-comparison.json`, `runtime.json`,
`source.json`, and `traces/*.log`. Sentence indexes are zero-based logical targets,
not XHTML IDs. Listen only for the changed/questionable behavior identified above;
no subjective score or blanket acceptance is inferred from successful generation.

Stop for human review before freezing frontend, synthesis units, runtime and the
complete publication timing path. Issue #14 stays open until configuration/timing
freeze and reported evaluation are complete. No reported run has started.
