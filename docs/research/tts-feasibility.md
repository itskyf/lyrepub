# VieNeu-TTS compatibility and synchronization feasibility

This Issue #14 pass is not a frozen benchmark, preprocessing/runtime decision,
or synchronization-granularity decision. Source: *Thăng Long nổi giận*
(`9786045633946`), SHA-256
`39475a49286e7a95ee4f359937811ac4de90a81472af41a0ff30005860309ef0`.
The nine candidates come from [source characterization](source-characterization.md).
Four neighboring paragraphs provide playback transitions only.

## Runtime and preprocessing

The recorded pathway is:

```text
authored Block.text -> NeMo Vietnamese TN -> SEA-G2P phonemization -> audio.cpp
```

- NeMo Text Processing is the repository's pinned fork at
  `c3afd14899658d53920b2737ff4d7216d9a32c83`. The installed package's Git
  revision is verified. `Normalizer(input_case="cased", lang="vi",
  deterministic=True)` uses default post-processing, with
  `punct_pre_process=False` and `punct_post_process=False`.
- SEA-G2P `0.9.1`, `G2P(lang="vi").convert(..., punc_norm=False)`, supplies
  phonemes only. Its normalizer and combined pipeline are not invoked.
- audio.cpp family `vieneu_v3_turbo`, explicit `cuda` backend, image revision
  `955c8725c611d511774e6be132aff6609163b2d2`; observed image digest
  `b881a557d10c435690b12894315b33dfeff22a61f833e6c55331f510ce99282d`.
  Image input, image ID, repository digests, and revision are recorded in
  `runtime.json`; the supplied image's revision is verified before inference.
- Existing `vieneu-v3-turbo-bf16.gguf`: BF16 talker and F16 codec, repository
  `pnnbao-ump/VieNeu-TTS-v3-Turbo`, revision
  `61b85e3d937fbbacb387714180e8182823512523`, SHA-256
  `c9c23d51989382e27730077c2373023bcfb0891db63a1efec97fd73b4bd6b7dc`.
- Packaged Thục Đoan (`thuc_doan`) requires both `ref_codes.txt` and
  `speaker.emb.txt`, with SHA-256 values respectively
  `9d084951e34f7c2d3cf7c6bb0f2fbcdc6e61e1e369bb0dfed1c2874077ca6bad`
  and `aae1818cda77c25d6ccd39c64387695b895fa5e85c7b279205fea744fb95a400`.
  Model and voice hashes are checked; there is no default-voice fallback.
- Inference defaults at this revision: temperature 0.8, top-k 25, top-p 0.95,
  repetition penalty 1.2, window 64, max tokens 300, sampling and frame cap
  enabled, babble retries 2. Subtalker sampling follows the main sampler.
  Seed per target is `14 + 1000 × spine_index + block_index`.
- Documented audio.cpp long-form settings remain unchanged: phoneme-string
  chunk budget 200, minimum 20, cuts at paragraphs/sentences/minor punctuation/
  whitespace and merges short chunks. Minimum seam pauses are
  0.70/0.50/0.30 seconds; longer natural pauses are retained.
- FFmpeg 9.0.2 packages WAV as Ogg Opus, `libopus`, 96 kb/s.
  FFprobe 9.0.2 measures the final Ogg files; clocks are rounded consistently
  to milliseconds.

Image, source, model, and voice locations are runtime inputs. Only identities,
options, and reproducible commands are recorded, without machine-local paths.
The audio.cpp runtime itself is under test: ordinary output/logs and full audio
are retained. No custom splitter, upstream compilation, codec-frame seam
reconstruction, or inferred chunk list is used.

Source targets, internal audio.cpp synthesis units, and Media Overlay targets
remain distinct. Internal chunks are not assumed to be addressable XHTML or
publication synchronization units. This pass does not need exact internal
chunk boundaries; any later need must follow an observed failure and review.

## Cases and treatments

The nine cases are `s10-b42`, `s5-b26`, `s15-b17`, `s12-b68`,
`s12-b30`, `s18-b35`, `s2-b70`, `s5-b9`, and `s17-b135`.
All baseline inputs are authored text, with no case-specific processing branch.
`cases.json` records source text, TTS input, NeMo normalized text, phonemes,
ordinary runtime command/log, generated audio, and final Ogg duration separately.
Preprocessing failures and synthesis failures have separate statuses.

All nine raw baselines, four playback neighbors, and one later treated variant
completed audio generation without a preprocessing or synthesis exception.
This does not establish pronunciation, intelligibility, or prosody acceptance.

| Baseline target | Authored chars | Final Ogg seconds |
| --- | ---: | ---: |
| s10-b42 | 2,613 | 156.256 |
| s5-b26 | 800 | 53.576 |
| s15-b17 | 281 | 19.076 |
| s12-b68 | 1,566 | 95.596 |
| s12-b30 | 402 | 28.326 |
| s18-b35 | 581 | 37.566 |
| s2-b70 | 185 | 13.996 |
| s5-b9 | **3,427** | **208.766** |
| s17-b135 | 129 | 9.686 |

The separately labeled `s17-b135-treated` output is 6.596 seconds.

The supplied earlier listening findings remain evidence for the earlier run:
`s15-b17` date pronunciation was correct; `s12-b30` was acceptable;
`s18-b35` was somewhat difficult to understand; item numbers in `s2-b70`
were correct but insufficiently separated; the broken cry in `s17-b135`
was pronounced incorrectly. They are not acceptance of the changed TN pathway.

### Slash enumeration: s2-b70

The XHTML contains one parenthetical paragraph, continued by the next paragraph,
with literal slash-number markers rather than semantic list items.
NeMo renders `1/` as `một /`, etc. SEA-G2P phonemization omits the slash
rather than speaking `trên`, but supplies no punctuation between marker and
item body. Listen for the previously reported marker-to-item pause problem;
do not classify it as a number-pronunciation error.

If it persists, the smallest proposed general TTS-only treatment is a comma
after slash-enumerated item numbers. It remains a proposal for review, not an
implemented book-specific rule or authored XHTML change.

### Raw and treated battle cry: s17-b135

The complete paragraph and preceding context repeatedly use "Sát Thát!" as
a crowd battle cry. Authored `S…át Th.. át!` depicts its interrupted/extended
delivery. The raw baseline is generated first and retained.
NeMo leaves that spelling intact; phonemization instead produces separate
English letter-name fragments for `S` and `Th`, including
`ˈɛɜs` and `tˌiːˈeɪtʃ`. This is a retained preprocessing incompatibility
with the intended lexical cry, not a synthesis exception.

After that baseline, a separate `s17-b135-treated` candidate renders only
this occurrence as `Sát Thát!` in TTS input. Its explicit input and rationale
are in `scripts/issue14_variants.json`, passed as a runtime variants file.
The processor does not branch on the case ID or edit source text. Both outputs
require human listening; the treatment loses the written elongation and is not
adopted as final preprocessing.

### Date, foreign text, and long narration

In the complete `s15-b17` paragraph, NeMo renders `24-8-1284` as day/month/year
words without duplicating the preceding "ngày". The earlier isolated date probe
is not a full-case result. Listen again to pronunciation and surrounding prosody.
Foreign/French names and dialogue retain their full source context.

The 3,427-character `s5-b9` baseline is provided in full for direct long-form
listening. No seam clips or reconstructed timings are needed without a concrete
audible defect. MOSS was not required for this rerun; earlier ASR observations
are not reference truth or synchronization evidence.

## Feasibility EPUB

The synchronization unit remains a copied authored XHTML paragraph with an ID
added where necessary; authored text and inline semantics are unchanged.
The two sequences are `s5-b8–10` and `s10-b41–43`.
Each paragraph has one SMIL `par`, explicit `clipBegin` and `clipEnd`,
and final audio typed exactly `audio/ogg; codecs=opus`.

The one publication duration and one refined duration per overlay equal the
corresponding final Ogg clip-duration sums: 481.036 seconds overall, with
298.758 and 182.278 seconds for the two overlays. Discoverability declares only
`textual` access, `textual` sufficiency, `synchronizedAudioText`, no hazards,
and a summary identifying the excerpt and pending human review. It claims no
full-publication accessibility conformance.

The existing EPUBCheck **5.4.0** image reported no errors or warnings; the
existing Ace **1.4.6** image reported no issues.
Their minimal build/load flow is in [README](../../README.md#validator-images)
and root `docker-bake.hcl`; no validator rebuild is needed for this run.
Reader retesting was withdrawn by the user. The earlier Readest failure cannot
establish granularity insufficiency because the old SMIL omitted `clipEnd`.

## Reproduce and review

Use `git worktree list` to locate the main worktree. Set `SOURCE_EPUB` to
its original EPUB without copying data. Supply `MODEL_GGUF`, `VOICE_DIR`,
and `AUDIOCPP_IMAGE` as runtime inputs.

```sh
OUT=data/issue-14-feasibility-review
pixi run -e dev python scripts/issue14_feasibility.py prepare --output "$OUT" --source-epub "$SOURCE_EPUB"
pixi run -e dev uv run --with sea-g2p==0.9.1 python scripts/issue14_feasibility.py synthesize --output "$OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR" --image "$AUDIOCPP_IMAGE"
# Inspect the retained raw baseline before requesting a treatment:
pixi run -e dev uv run --with sea-g2p==0.9.1 python scripts/issue14_feasibility.py synthesize --output "$OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR" --image "$AUDIOCPP_IMAGE" --variants scripts/issue14_variants.json
pixi run -e dev python scripts/issue14_feasibility.py publish --output "$OUT" --source-epub "$SOURCE_EPUB"
podman run --rm --security-opt label=disable -v "$PWD/$OUT:/work:ro" lyrepub-epubcheck:5.4.0 /work/feasibility.epub
podman run --name issue14-ace --security-opt label=disable -v "$PWD/$OUT:/work:ro" lyrepub-ace:1.4.6 -o /tmp/ace /work/feasibility.epub
podman cp issue14-ace:/tmp/ace "$OUT/ace-report"
```

Completed records are retained; rerun changed preprocessing into a fresh output
directory. The treatment command requires a completed baseline and distinct key.
Gitignored review artifacts under `data/issue-14-feasibility-review/`:

- `audio/<case>.ogg`: nine baselines plus `s17-b135-treated.ogg`;
  full `s5-b9.ogg` is the long-text listening material.
- `feasibility.epub`: paragraph-level synchronized playback excerpt.
- `source.json`, `runtime.json`, `cases.json`, `traces/*.log`: separate
  source identity, settings/hashes, preprocessing stages, and normal runtime logs.
- `epubcheck-5.4.0.txt` and `ace-report/report.html`: validation evidence.

Listen for narration clarity, date/number expressions, foreign names, item pauses,
dialogue, raw versus treated cry, and long-block joins/prosody. In the EPUB,
inspect highlighting, following/scrolling, pause/resume, and navigation/recovery,
including the long target at a larger text size. Record concrete observations
without a usability score. Stop for human review before freezing any settings or
granularity; coordinate any reviewed finer XHTML targeting with Issue #16.
