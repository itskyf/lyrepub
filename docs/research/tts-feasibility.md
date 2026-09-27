# VieNeu-TTS compatibility and synchronization feasibility

This Issue #14 pass is not a frozen benchmark, runtime selection, preprocessing
decision, or synchronization-granularity decision. Source:
*Thăng Long nổi giận* (`9786045633946`), SHA-256
`39475a49286e7a95ee4f359937811ac4de90a81472af41a0ff30005860309ef0`.
The nine candidates come from [source characterization](source-characterization.md).
Four neighboring paragraphs provide playback transitions only.

## Reproducibility for this run

- audio.cpp image digest
  `b881a557d10c435690b12894315b33dfeff22a61f833e6c55331f510ce99282d`,
  image revision `955c8725c611d511774e6be132aff6609163b2d2`.
  Family `vieneu_v3_turbo`, explicit `cuda` backend; no backend comparison.
- Existing `vieneu-v3-turbo-bf16.gguf`: BF16 talker and F16 codec, model
  repository `pnnbao-ump/VieNeu-TTS-v3-Turbo`, revision
  `61b85e3d937fbbacb387714180e8182823512523`, SHA-256
  `c9c23d51989382e27730077c2373023bcfb0891db63a1efec97fd73b4bd6b7dc`.
- Packaged voice `thuc_doan` (Thục Đoan), both reference codes and speaker
  embedding required. Their SHA-256 values are respectively
  `9d084951e34f7c2d3cf7c6bb0f2fbcdc6e61e1e369bb0dfed1c2874077ca6bad`
  and `aae1818cda77c25d6ccd39c64387695b895fa5e85c7b279205fea744fb95a400`.
  These two small files were retrieved from the same pinned model revision;
  the checkpoint was reused. No default-voice fallback.
- SEA-G2P `0.9.1`, `SEAPipeline(lang="vi")`, `punc_norm=False`.
  Its existing normalizer and G2P produce phonemes for audio.cpp's documented
  phoneme-input route. No Python VieNeu synthesis or custom normalizer.
- audio.cpp defaults: temperature 0.8, top-k 25, top-p 0.95, repetition penalty
  1.2, window 64, max tokens 300, sampling and frame cap enabled, babble retries 2.
  Seed per source target: `14 + 1000 × spine_index + block_index`.
  Subtalker sampling follows the main sampler defaults.
- Upstream audio.cpp long-form chunking: size 200, minimum 20, unchanged.
  The pinned C++ code counts UTF-8 bytes of phonemes; this differs from the
  previous Python `max_chars=256` route. It cuts at paragraphs, sentences,
  minor punctuation, then whitespace and packs/merges short chunks.
  Pause minima are 0.70/0.50/0.30 seconds for paragraph/sentence/minor seams;
  existing longer natural pauses are retained.
- Stereo 48 kHz WAV is encoded with FFmpeg 9.0.2, `libopus`, 96 kb/s, into
  final `.ogg` files. Clip endpoints and metadata use FFprobe 9.0.2 measurements
  of those files, rounded consistently to milliseconds.

The chunk diagnostic links the original splitter from the pinned audio.cpp
source, rather than copying its rules. The synthesis code dump confirms the
generated chunk count. For this run, codec-frame lengths plus measured zero
padding exactly account for every WAV sample; the retained join times are
listening diagnostics, not finer Media Overlay targets. A mismatch fails
explicitly, including if a future babble retry changes the dumped waveform.

## Source and listening evidence

All nine cases and four playback neighbors generated audio successfully.
No preprocessing or synthesis exception remains in this run.

| Target | Authored chars | audio.cpp chunks | Final Ogg seconds |
| --- | ---: | ---: | ---: |
| s10-b42 | 2,613 | 34 | 157.746 |
| s5-b26 | 800 | 11 | 53.436 |
| s15-b17 | 281 | 4 | 19.346 |
| s12-b68 | 1,566 | 21 | 95.496 |
| s12-b30 | 402 | 6 | 29.056 |
| s18-b35 | 581 | 8 | 37.736 |
| s2-b70 | 185 | 3 | 16.526 |
| s5-b9 | **3,427** | **44** | **209.436** |
| s17-b135 | 129 | 2 | 7.646 |

The supplied human findings apply to the earlier Python run: `s15-b17` date
pronunciation was correct; `s12-b30` was acceptable; `s18-b35` was somewhat
difficult to understand. They are retained as listening evidence, not acceptance
of newly generated audio.

### Slash enumeration: s2-b70

The complete XHTML is one parenthetical `<p>`, continued by the next paragraph,
with literal `1/ … 2/ …` markers rather than semantic list items. The reported
problem is insufficient separation after correctly pronounced item numbers.
The new SEA-G2P output reads the markers as `một trên`, `hai trên`, etc.;
audio.cpp packs items into three chunks and does not create seams after markers.
Its minimum seam pauses therefore cannot supply marker-to-item separation.

Retain this as a segmentation/pause observation. If listening confirms the
problem persists, the smallest proposed general treatment is to recognize
slash-enumerated item markers and render each marker as a number followed by a
comma in TTS input only. Review the changed lexical/pause behavior before adopting
it; no book-specific core exception or authored XHTML edit has been implemented.

### Battle cry: s17-b135

The complete paragraph and preceding paragraph repeatedly use "Sát Thát!"
as a crowd battle cry. The authored `S…át Th.. át!` represents an extended or
interrupted version of that same cry. The earlier normalization produced
`ét át th. át!`, matching the reported incorrect pronunciation.

This case explicitly replaces only that occurrence with `Sát Thát!` in TTS
input. Authored text and XHTML remain unchanged. The new normalized input contains
the lexical cry correctly. The treatment sacrifices the written elongation;
its pronunciation and dramatic delivery require human review and are not frozen.

### Optional intelligibility diagnostic: s18-b35

`GET /v1/models` identified the existing `moss_transcribe_diarize` model
`moss`, BF16 GGUF. Only this case's WAV was submitted to
`POST /v1/audio/transcriptions/details`. MOSS follows the paragraph's broad
sequence but transcribes several substitutions, including "Cần bèn dân thư"
for "Thần bèn dâng thư" and uncertain foreign-name spellings. This does not
establish TTS omissions or substitutions: ASR itself may be wrong. Retain the
intelligibility observation and listen, particularly to those phrases.
ASR is optional, supplies no reference truth, and supplies no synchronization.

## Feasibility EPUB and validation

The Media Overlay unit remains one copied authored XHTML `<p>`, with an added
ID where needed. Text and inline semantics are preserved. Two sequences use
`s5-b8–10` and `s10-b41–43`; each full paragraph has one SMIL `<par>`.
Every audio element now has explicit `clipBegin` and `clipEnd`.
Manifest typing is exactly `audio/ogg; codecs=opus`.

One publication duration is `483.196s`; refined overlay durations are
`299.828s` and `183.368s`. They equal their packaged clip-duration sums.
EPUBCheck **5.4.0** reports zero errors and warnings. Ace **1.4.6** reports no
issues using the existing local validator images, without rebuilding them.

Discoverability metadata declares textual and auditory access, textual
sufficiency (all excerpt content is text), synchronized audio/text, and no
hazards. Its summary identifies the excerpt and pending human review. No
full-publication accessibility conformance is claimed.

The previous Readest failure is invalid as granularity evidence: its SMIL
omitted `clipEnd`. Reader retesting was withdrawn by the user; highlighting,
following, navigation, and recovery remain pending on this repaired EPUB.
No system applications or packages are required by this workflow.

## Reproduce and review

Locate the main worktree with `git worktree list`; set `SOURCE_EPUB` to its
original EPUB without copying source data. Set `MODEL_GGUF`, `VOICE_DIR`, and
`AUDIOCPP_SOURCE` to runtime locations. Check out the image revision above in
`AUDIOCPP_SOURCE`; `VOICE_DIR` must contain both pinned Thục Đoan files.

```sh
OUT=data/issue-14-feasibility-audiocpp
pixi run -e dev python scripts/issue14_feasibility.py prepare --output "$OUT" --source-epub "$SOURCE_EPUB"
pixi run g++ -std=c++17 -ffunction-sections -fdata-sections -Wl,--gc-sections -I "$AUDIOCPP_SOURCE/include" scripts/issue14_chunk_trace.cpp "$AUDIOCPP_SOURCE/src/community_models/vieneu_v3_turbo/orchestration.cpp" -o "$OUT/chunk_trace"
pixi run -e dev uv run --no-project --with sea-g2p==0.9.1 python scripts/issue14_feasibility.py synthesize --output "$OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR" --chunk-helper "$OUT/chunk_trace"
pixi run -e dev python scripts/issue14_feasibility.py publish --output "$OUT" --source-epub "$SOURCE_EPUB"
podman run --rm --security-opt label=disable -v "$PWD/$OUT:/work:ro" lyrepub-epubcheck:5.4.0 /work/feasibility.epub
podman run --name issue14-ace --security-opt label=disable -v "$PWD/$OUT:/work:ro" lyrepub-ace:1.4.6 -o /tmp/ace /work/feasibility.epub
podman cp issue14-ace:/tmp/ace "$OUT/ace-report"
```

Gitignored outputs in `data/issue-14-feasibility-audiocpp/`:

- `cases.json`: authored text → explicit TTS intervention → SEA-G2P normalized
  text/phonemes → actual audio.cpp chunks → audio and measured joins.
- `runtime.json`, `source.json`, `traces/`: settings, identities, commands,
  generated code dumps, and logs, without machine-local paths in metadata.
- `audio/<target>.ogg`: the nine new cases require human judgment because the
  synthesis/frontend route changed; neighboring playback-only audio is not
  separate listening material.
- `joins/s5-b9-join-01.ogg`, `-22.ogg`, `-43.ogg`: short excerpts around
  measured joins at **2.48**, **105.51**, and **206.71** seconds. `clips.json`
  gives exact clip windows; full long-block audio remains available.
- `feasibility.epub`, `epubcheck-5.4.0.txt`,
  `ace-report-final/report.html`, and `s18-b35-moss.json`.

Listen for narration clarity, number/date pronunciation, French/foreign names,
list marker pauses, mixed quotation/dialogue delivery, the treated battle cry,
and long-block seams/prosody. In the EPUB, inspect highlight transitions,
following/scrolling, pause/resume, and navigation into/out of the long target,
including a larger text size. Record concrete observations without a score.
Stop for review before freezing settings or adding finer synchronization.
Any reviewed sentence-addressable targeting belongs with Issue #16.
