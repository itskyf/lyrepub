# VieNeu-TTS source and synchronization feasibility for #14

This is a pre-evaluation feasibility pass, not the frozen benchmark or a
subjective usability judgement. The source is *Thăng Long nổi giận*
(`9786045633946`), SHA-256
`39475a49286e7a95ee4f359937811ac4de90a81472af41a0ff30005860309ef0`.
The nine cases are the applicable representative and challenge candidates in
[source characterization](source-characterization.md). Four adjacent paragraphs
were synthesized only to expose playback transitions in the excerpt EPUB.

## Runtime and processing

- VieNeu package `3.8.3`, editable runtime commit
  `c1390abbdb2eedcdf58eafb546966c06ce27af71`; the checkout had unrelated
  local changes to `apps/gradio_main.py` and `mise.toml`.
- VieNeu-TTS v3 Turbo checkpoint `pnnbao-ump/VieNeu-TTS-v3-Turbo`, revision
  `61b85e3d937fbbacb387714180e8182823512523`, `update` weights;
  MOSS audio tokenizer revision `6aa02b01e445cc585582cf0ba480bc3ea6c8dd68`.
- Preset `Thục Đoan`; explicit PyTorch/CUDA backend, `bfloat16`, 48 kHz.
  `max_chars=256`, batch size 32, babble retries 2, watermark disabled.
  Sampling: temperature 0.8, top-k 25, top-p 0.95, maximum new frames 300,
  repetition penalty 1.2, repetition window 64. Per-block Torch seed is
  `14 + 1000 × spine_index + block_index`.
- Issue #12 `Block.text` is retained as the source target. VieNeu's
  `normalize_to_chunks_v3_with_gaps` supplies normalized synthesis chunks and
  gap classes. Its pinned internal chunk synthesis and joining functions
  supply the emitted waveform and exact chunk-join sample offsets. No project
  normalizer, authored-text edit, voice clone, ASR, or second TTS route was used.
  These settings describe this feasibility run only.

## Objective case record

`data/issue-14-feasibility/cases.json` links each source target to its complete
normalized chunk list, gap classes, per-block WAV, sample count, and join times.
All nine candidate cases and four neighboring paragraphs completed synthesis;
no preprocessing or synthesis exception occurred. Audio content and prosody
still require human listening.

| Source target (`spine:block`) | Source chars | VieNeu chunks | WAV seconds | Preprocessing observation |
| --- | ---: | ---: | ---: | --- |
| 10:42 | 2,613 | 15 | 155.65 | Person-dense narration; two minor gaps among sentence gaps. |
| 5:26 | 800 | 5 | 51.17 | Historical names and years normalized. |
| 15:17 | 281 | 2 | 19.28 | `24-8-1284` becomes spoken date words. |
| 12:68 | 1,566 | 9 | 92.46 | Mixed quotation marks are removed in normalized text. |
| 12:30 | 402 | 2 | 27.25 | `Le Livre de Marco Polo` remains; years become words. |
| 18:35 | 581 | 3 | 35.35 | Dialogue dash removed; original-form names remain. |
| 2:70 | 185 | 1 | 14.88 | Slash enumeration `1/` becomes `một trên`, similarly for 2–8. |
| 5:9 | **3,427** | **17** | **208.49** | Long paragraph spans 16 VieNeu joins. |
| 17:135 | 129 | 1 | 8.64 | `S…át Th.. át!` becomes `ét át th. át!`; inspect the speech before considering any intervention. |

The Media Overlay unit in the feasibility EPUB is one original XHTML `<p>`.
The original case paragraphs have no authored IDs, so the excerpt adds an ID
to each copied `<p>` without changing its text or inline semantics. Its two
three-paragraph sequences use source targets `5:8–10` and `10:41–43` in
reading order. One full MP3 per paragraph is paired with one SMIL `<par>`;
its duration comes from the emitted 48 kHz sample count. Chunk boundaries are
diagnostic offsets within those paragraph audio files, not Media Overlay
targets. EPUBCheck **5.4.0** reports zero errors and warnings. This structural
result does not establish usable highlighting, following, or recovery.

## Reproduce and review

From the Issue #14 worktree, with the main worktree's source `data/` present:

```sh
.pixi/envs/dev/bin/python scripts/issue14_feasibility.py prepare
/var/home/itskyf/HCMUS/VoiceProcessing/VieNeu-TTS/.venv/bin/python scripts/issue14_feasibility.py synthesize
for key in s5-b8 s5-b9 s5-b10 s10-b41 s10-b42 s10-b43; do
  ffmpeg -v error -y -i "data/issue-14-feasibility/audio/$key.wav" -codec:a libmp3lame -q:a 2 "data/issue-14-feasibility/audio/$key.mp3"
done
.pixi/envs/dev/bin/python scripts/issue14_feasibility.py publish
```

The gitignored output directory contains `runtime.json`, `source.json`,
`cases.json`, `audio/*.wav`, `joins/*.wav`, `feasibility.epub`, and
`epubcheck-5.4.0.txt`. Listen to ordinary narration (`s10-b42.wav`), date
(`s15-b17.wav`), numbers (`s2-b70.wav`), French and foreign names
(`s12-b30.wav`, `s18-b35.wav`), quotation/dialogue (`s12-b68.wav`,
`s17-b135.wav`), and the long block (`s5-b9.wav`). For the long block,
`joins/s5-b9-join-01.wav`, `-09.wav`, and `-16.wav` cover boundaries at
13.92, 112.01, and 205.77 seconds; all 16 eight-second boundary clips are
available. These clips use the actual joined waveform.

Open `feasibility.epub` in Thorium and Readest. In each reader, check that
the highlight reaches the next paragraph, the view follows the active
paragraph, playback can be paused and resumed, and navigation into and out
of the long paragraph remains practical. Record the reader/version and
specific observed behavior rather than a usability score. Review the long
paragraph and 2,613-character narration target at ordinary reading layout
and a larger text size. If paragraph granularity proves insufficient, review
sentence-addressable targeting in #16 with a timing path and XHTML markup
proposal before implementing it or freezing the reported configuration.
