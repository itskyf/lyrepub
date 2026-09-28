# VieNeu-TTS compatibility and synchronization feasibility

Issue #14 remains in feasibility mode. Human playback review has frozen the
Media Overlay synchronization granularity at **sentence level**. Preprocessing,
synthesis-unit handling, the publication timing path, and reported runtime
configuration remain unfrozen; no reported evaluation has run.

Source: *Thăng Long nổi giận* (`9786045633946`), SHA-256
`39475a49286e7a95ee4f359937811ac4de90a81472af41a0ff30005860309ef0`.
The nine candidates come from [source characterization](source-characterization.md),
not a newly frozen benchmark. Four neighbors exercise paragraph transitions.

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
authored Block.text -> slash-enumeration treatment when applicable
                   -> NeMo Vietnamese TN -> SEA-G2P phonemization -> audio.cpp
```

- NeMo Text Processing: repository fork revision
  `c3afd14899658d53920b2737ff4d7216d9a32c83`, verified from the installed
  package. `Normalizer(input_case="cased", lang="vi", deterministic=True)`;
  default post-processing; punctuation pre/post processing disabled.
- SEA-G2P `0.9.1`: `G2P(lang="vi").convert(..., punc_norm=False)` only.
  Its normalizer and combined pipeline are not invoked.
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
  Seed: `14 + 1000 * spine_index + block_index`.
- Upstream chunk budget 200/minimum 20 remains unchanged. Although documented
  as characters, this revision uses `std::string::size()` on UTF-8 phonemes:
  the observed budget counts **bytes**. Paragraph/sentence/minor-punctuation/
  whitespace splitting and short-chunk merging remain upstream behavior.
  Minimum seam pauses remain 0.70/0.50/0.30 seconds.
- FFmpeg/FFprobe 9.0.2; Ogg Opus via `libopus`, 96 kb/s; duration measured
  from final Ogg and rounded consistently to milliseconds.

Source/model/voice/image locations are runtime arguments, not encoded host paths.
`cases.json` separates source text, TTS input/interventions, normalized text,
phonemes, seed, runtime command/log, audio, and final Ogg duration. Preprocessing
and synthesis exceptions have separate statuses. Normal tests require no inference.

## Human findings and current generation

These are the latest supplied listening observations, not automatic quality
scores or acceptance of every newly generated file.

| Case | Human finding | Current Quỳnh Anh Ogg seconds |
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

All nine cases and four neighbors completed without preprocessing/synthesis
exceptions. Only `s2-b70` receives a TTS-input intervention in this rerun.
Generation success is not a subjective prosody judgement. MOSS was not needed.

### General slash-enumeration treatment

Source XHTML has inline slash-number items inside a paragraph, not a semantic
list. Previously NeMo produced `một /`, and SEA removed `/` without leaving
separation. The implemented TTS-only rule replaces `/` with `,` for a confirmed
ordered run starting at `1/`, with at least two consecutive numbered markers.
Markers occur at the text/line start or after `(`, `:`, `;`, or `.`, and the
item body begins with a letter. Singleton markers and markers outside confirmed consecutive runs are left
unchanged; numeric fractions/date slashes are not list markers.

For `s2-b70`, all eight markers become `1,`, `2,`, etc. NeMo emits `một,`,
`hai,`; SEA retains those commas in phonemes. This supplies punctuation for
upstream pause behavior without tuning it. Authored XHTML is unchanged.
The focused test covers inline/newline lists and fraction/date/ambiguous negatives.
Human listening must confirm whether the added separation is sufficient.

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

## Narrow stutter diagnosis and unresolved synthesis-unit decision

Ordinary logs contain compute timings but no phoneme chunk boundaries. A
**temporary upstream CLI diagnostic**, at the pinned revision, printed the
existing `split_phoneme_chunks` result for only `s5-b26` and `s15-b17`, then
stopped before synthesis. It used the host CPU only to reach backend-independent
text splitting; all listening audio uses the unchanged CUDA runtime. No backend
comparison, custom splitter/helper, or codec seam reconstruction was performed.
Temporary diagnostic source, build, and full logs were removed. Only the two
relevant boundary pairs remain in `number-boundary-diagnostic.json`.

| Case | Observed upstream boundary, zero-based chunk indexes | UTF-8 offsets | Diagnosis |
| --- | --- | --- | --- |
| `s5-b26`, `1256` | chunk 3 ends `một nghìn hai`; chunk 4 begins `trăm năm mươi sáu` | chunk 3 `[414, 613)`, chunk 4 `[614, 683)` | Whitespace fallback splits inside the normalized year. |
| `s15-b17`, `1284` | chunk 1 ends `một nghìn`; chunk 2 begins `hai trăm tám mươi tư` | chunk 1 `[68, 267)`, chunk 2 `[268, 312)` | Whitespace fallback splits inside the normalized year. |

Both preceding chunks are **199 bytes**, and both boundaries have `Minor`
gap classification with upstream minimum pause **0.30 s**. These lexical
boundaries coincide exactly with the supplied audible stutters. The cause is
synthesis segmentation/pause within a number phrase, not incorrect NeMo number
content. Current rerun phonemes for both cases equal the diagnostic inputs.
The diagnostic does not measure the final audible gap duration.

**Proposed smallest general treatment, not implemented:** preserve number/date
normalization spans as indivisible phrases when preparing synthesis requests;
move a request boundary before a phrase that would otherwise cross the existing
upstream budget. Preserve all content, prefer existing punctuation for surrounding
cuts, and keep upstream chunk size/pause settings. This requires a general mapping
from authored numeric expressions to normalized/phonemized spans and materially
changes synthesis-unit handling; review is required before implementing it.
Sentence-only requests cannot by themselves guarantee that a long sentence's
number phrase will survive upstream internal splitting.

## Frozen synchronization decision and Issue #16 handoff

Human playback found correct paragraph targets and smooth paragraph transitions,
but highlighting was too large and following/navigation too difficult for
publication use. This is direct evidence from the repaired overlay, independent
of the earlier Readest parser failure. **Sentence level is frozen as the smallest
justified finer MO synchronization unit.** No score or threshold is invented.

Keep three levels distinct:

1. Issue #12 authored source block/target;
2. TTS request and its internal audio.cpp chunks;
3. sentence target and its final packaged-audio timing range.

Issue #16 owns publication-facing sentence-addressable XHTML targeting/markup
and generic Media Overlays. It must preserve authored text, inline semantics,
reading order, and visible authored heading coverage. Issue #14 owns the audio
and reproducible sentence timing requirement, not a second publication layer.
The existing #16 `Timing` contract (`text_href`, `audio_href`, `clip_begin`,
`clip_end`) can carry those ranges once targeting and the timing path are ready.
Its current audio suffix support must be reconciled with these `.ogg` artifacts
without changing the Opus MIME or transcoding unnecessarily.

**Remaining timing blocker:** block audio plus its total duration does not
supply sentence timings. Sentence synthesis requests with final-media-derived
bounds are the smallest proposed timing path, subject to reviewing synthesis-unit
handling and long-sentence number protection. No alignment/ASR path or sentence
markup is implemented here. Any materially different timing method needs review.

## Diagnostic EPUB and validation

The regenerated excerpt retains copied authored paragraphs for `s5-b8–10` and
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
OUT=data/issue-14-quynh-anh-review
pixi run -e dev python scripts/issue14_feasibility.py prepare --output "$OUT" --source-epub "$SOURCE_EPUB"
pixi run -e dev uv run --with sea-g2p==0.9.1 python scripts/issue14_feasibility.py synthesize --output "$OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR" --image "$AUDIOCPP_IMAGE"
pixi run -e dev python scripts/issue14_feasibility.py publish --output "$OUT" --source-epub "$SOURCE_EPUB"
podman run --rm --security-opt label=disable -v "$PWD/$OUT:/work:ro" lyrepub-epubcheck:5.4.0 /work/feasibility.epub
podman run --name issue14-ace --security-opt label=disable -v "$PWD/$OUT:/work:ro" lyrepub-ace:1.4.6 -o /tmp/ace /work/feasibility.epub
podman cp issue14-ace:/tmp/ace "$OUT/ace-report"
podman rm issue14-ace
```

Gitignored review outputs under `data/issue-14-quynh-anh-review/`:

- `audio/s2-b70.ogg`: listen for marker-to-body separation after the treatment.
- `audio/s5-b26.ogg`, `audio/s15-b17.ogg`: retained number-phrase stutters,
  pending review of the proposed general synthesis-unit treatment.
- `audio/s17-b135.ogg`: raw cry; expressive-prosody limitation remains.
- `audio/s5-b9.ogg`: full long-block selected-voice prosody check, 202.256 seconds.
- `feasibility.epub`: updated diagnostic excerpt without synthetic headings;
  paragraph granularity remains rejected, not a new usability candidate.
- `cases.json`, `runtime.json`, `source.json`, `traces/*.log`,
  `number-boundary-diagnostic.json`: traceable inputs/runtime and narrow diagnosis.
- `epubcheck-5.4.0.txt`, `ace-report/report.html`: validation evidence.

Stop for human review of the enumeration audio and proposed synthesis-unit/timing
handling. Do not freeze remaining settings or begin the reported run; Issue #14
stays open until the configuration/timing path is frozen and evaluation completes.
