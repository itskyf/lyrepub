# Storyteller alignment validation (Issue #15)

## Configuration and inputs

The automatic, full-length run used Storyteller `@storyteller-platform/align`
0.2.4, Node.js 26.10.0, and FFmpeg 9.0.2 on an NVIDIA GeForce RTX 5060
Laptop GPU host. Storyteller's `--device auto` selected **CPU fp32** for the
`ctc-local` MMS route, with batch size 1 and 25-second emission chunks. The
installed checkpoint was
`onnx-community/mms-300m-1130-forced-aligner-ONNX` (`onnx/model.onnx` SHA-256
`429e5d05c62acc8a9264db874a1b131e359fc626e40c253ac7b1fe52b11149b4`).
No ASR route or manual chapter mapping was used.

The source EPUB is version 2.0. Storyteller upgraded a temporary copy to EPUB 3 for
processing, marked it up at sentence granularity, and copied the original MP3
audio into numbered processed tracks. Its 120-minute maximum track length did
not split any source track. Source files were read from the main worktree's
`data/bronze/9786326186253/` and were not copied into version control.

| Input | SHA-256 |
| --- | --- |
| `Dem hoi Long Tri - Nguyen Huy Tuong.epub` | `bc9eefc060b80985724aa7d66ca6163fe14c944328f8fa81ce93767536d11b6a` |
| `dem-hoi-1.mp3` | `72e0894436b28a82e44d22d90b4402d733236262de6602f2b4771e6b08d6b495` |
| `dem-hoi-2.mp3` | `a7796078ab008477fe9ebe961d440590d9c33d936d17b4694113925bf3edd44f` |
| `dem-hoi-3.mp3` | `14e878a4309cba73f1316c6f7ef482042b53cfda2617e165ba6162b180263b85` |
| `dem-hoi-4.mp3` | `7ee055fc47b17729da27aca1c3c1da0d591b6f639d895c7f5202ce40c4b0ac` |
| `dem-hoi-5.mp3` | `243843e05ef2ba303e34212ecef01ec2418432f15d2d2ff5a6f8117dad5e6353` |
| `dem-hoi-6.mp3` | `0d0bdbe82e2e71339cf01bca842f9f479bf5bf6ffdc05e367ddcd79a1e4839ee` |
| `dem-hoi-7.mp3` | `b70aa993ebb44a23d8d1b0c96f332d50706aa0893589c30829c670cd4711901e` |

From the Issue #15 worktree, with `MAIN` set to the main worktree path returned
by `git worktree list --porcelain`, the run command was:

```sh
align --ctc --model mms --language vi --granularity sentence --autoupgrade \
  --audiobook "$MAIN/data/bronze/9786326186253" \
  --epub "$MAIN/data/bronze/9786326186253/Dem hoi Long Tri - Nguyen Huy Tuong.epub" \
  --processed-audio data/issue-15/ctc/processed-audio \
  --markedup data/issue-15/ctc/markedup.epub \
  --emissions data/issue-15/ctc/emissions \
  --reports data/issue-15/ctc/report.json \
  --output data/issue-15/ctc/aligned.epub --time --log-level info \
  2>&1 | tee data/issue-15/ctc/run.log
```

These generated paths are ignored locally. The processed-track `.source.json`
files and report confirm numeric track order 1–7. The retained emissions and
marked-up EPUB permit diagnosis without repeating model inference.

## Frozen evaluation procedure

The full automatic alignment is the only model input and run. After the
feasibility report showed all nine narratable spine documents on the expected
tracks, the native CTC route above was frozen for evaluation. Automatic
correspondence was usable, so the chapter-assisted condition is not applicable;
human chapter or sentence alignment assistance is **none**.

Before measuring boundary error, the following four source-derived sentence
starts were frozen. A listener records the first audible phoneme from each
local verification clip to about 0.1 second, without using Storyteller's
timestamp. Add the clip offset to obtain the reference track time, then compare
it with the corresponding Media Overlay `clipBegin`. The clips are derived for
verification only; they were not alignment inputs.

| Case | Sentence start | Track | WAV start on source track |
| --- | --- | ---: | ---: |
| Cross-document transition | `section_2.html-s0`, "LỜI NÓI ĐẦU" | 1 | 65.9 s |
| Ordinary narration | `section_3.html-s1`, "Khi bọn Bảo Kim tới Bắc Cung…" | 1 | 467.8 s |
| Heading verbalization | `section_4.html-s0`, spoken "Hai" for `II` | 2 | 0 s |
| Later long-form location | `section_8.html-s183`, "Kim đâu?" | 6 | 904 s |

Coverage, incorrect or unmatched content, section correspondence, long-form
failure, runtime, and human assistance are reported as separate observations;
no aggregate score or acceptance threshold is imposed.

The reported alignment reused the frozen emissions and marked-up EPUB without
rerunning inference:

```sh
align align --ctc --emissions data/issue-15/ctc/emissions \
  --audiobook data/issue-15/ctc/processed-audio \
  --epub data/issue-15/ctc/markedup.epub \
  --language vi --granularity sentence \
  --reports data/issue-15/evaluation/report.json \
  --output data/issue-15/evaluation/aligned.epub --time --log-level info \
  2>&1 | tee data/issue-15/evaluation/run.log
```

## Results

The full pipeline completed on the 16,446.6-second audiobook. Audio processing
took 2.29 seconds, emission generation 24 minutes 33.8 seconds wall time
(including about 7 minutes for the initial checkpoint download), markup 262
milliseconds, and pilot EPUB alignment 10.66 seconds. The reported alignment
from retained emissions took 10.85 seconds and produced a byte-identical
report (SHA-256 `d337047ce10a6ea701c8f6241db287398a87c825150714af52d3be6a3ce973a8`).
The aligned EPUB is about 190 MB. Storyteller aligned all nine narratable spine
documents and all seven
tracks; the cover and final image-only document were excluded because they
contain no text.

The Storyteller report records 3,379 sentence targets: 3,319 aligned, 54
interpolated, six unmatched, and none dropped. It records 16,181.26 matched
audio seconds, 213.18 interpolated seconds, and 13.76 loose seconds. Track 1
covers the author biography, preface, and section I in sequence; tracks 2–7
cover sections II–VII one-to-one. No section-level drift or missing track was
observed in the report, including at the ends of the long tracks.

The opening announcement absent from the EPUB appears as a 0–7.96-second
audio-only hole. The six unmatched sentences are the Roman-numeral headings
for sections I and III–VII; section II's heading was marked aligned despite
being spoken as "Hai." The report also contains a 5.8-second loose-audio hole
in track 2 at 1093.06–1098.86 seconds. These are reported output states, not
manually repaired timings. Storyteller's internal scores were not used as an
acceptance criterion.

### Verification clip pre-check

The first four OGG excerpts are retained only as diagnostic evidence. The
listener found both track-1 excerpts cut speech at the end, the track-2
heading lacked clear following context, and the intended words were not heard
in the short track-6 excerpt. No boundary measurement uses those files.

To locate the frozen targets without selecting a position from Storyteller's
output, 16 kHz mono PCM windows were decoded from the original MP3s and sent
to the existing audio.cpp service. Track 1's opening 10 minutes and track 2's
opening minute were screened in fixed 60-second windows. Track 6's 600–1200 s
region was screened in the same windows, chosen from the source block's
position within that section rather than from Storyteller's timestamp. Raw
responses and the locator WAVs are retained under `data/issue-15/locator/`.

The audio.cpp container image `localhost/audio.cpp:full-cuda13` records source
revision `955c8725c611d511774e6be132aff6609163b2d2`; its binary reports
`audio.cpp dev`, Release, gcc 14.2.0, with CPU and CUDA backends. MOSS used the
existing `moss-transcribe-diarize-bf16.gguf` checkpoint (SHA-256
`5bc627289e2586fc2d9269afda15a305e545a4ff3512c902889be71d58e56ad5`),
loaded as `moss_transcribe_diarize`, offline ASR, BF16. The optional Qwen text
check used the existing `qwen3-asr-1.7b-f16.gguf` checkpoint (SHA-256
`f12537d4ea56df4e1dcca64a902e0b37fb1111f8ef7fc8e554fd00110be047d0`),
offline ASR, F16. Both received `language=vi`. Neither model was used to create
the Storyteller output or the timing reference.

The representative track-6 locator request was:

```sh
ffmpeg -v error -nostdin -ss 900 -i "$MAIN/data/bronze/9786326186253/dem-hoi-6.mp3" \
  -t 60 -ac 1 -ar 16000 -c:a pcm_s16le \
  data/issue-15/locator/track6-0900-0960.wav
curl -sS -X POST http://127.0.0.1:8080/v1/audio/transcriptions/details \
  -F model=moss -F language=vi \
  -F file=@data/issue-15/locator/track6-0900-0960.wav \
  -o data/issue-15/locator/track6-0900-0960.json
```

The other fixed 60-second windows used the same conversion and request with
their recorded filename offsets. Qwen text checks used
`/v1/audio/transcriptions`, not its word-timestamp path.

| Target | ASR locator result on source track | New PCM WAV clip |
| --- | --- | --- |
| Preface heading | MOSS segment "Lời nói đầu" at 92.15–93.47 s | `track1-s1-to-s2-65.9s.wav` (65.9–122.7 s) |
| Ordinary narration | MOSS segment starts 494.46 s | `track1-ordinary-s3-467.8s.wav` (467.8–529.0 s) |
| Spoken section II heading | MOSS omitted "Hai"; Qwen recognized it in the original track's 0–7 s window | `track2-heading-0s.wav` (0–34 s) |
| Later "Kim đâu?" | MOSS segment starts 917.78 s; Qwen confirms the phrase in the 900–960 s window | `track6-later-904s.wav` (904–950.5 s) |

Each new clip was decoded directly from the original track as 16 kHz mono
signed 16-bit WAV. Starts and ends were placed inside quiet regions identified
from the original waveform; the first and last 0.2 s of each WAV are quiet.
Qwen's text-only check on each finished WAV contains its intended target; the
unchanged JSON responses are retained next to the clips. In particular, the
new track-6 WAV includes the phrase that the listener could not identify in
the earlier short OGG excerpt.
These ASR locations are suggestions for listening only. The listener's
confirmed or corrected word onset, measured to 0.1 s from each WAV's start,
will be the reference for boundary error. Independent listening-based
measurements remain pending.

## Discussion

The automatic route provides complete section correspondence and sentence
timings for this source without chapter assistance. Interpolated sentences,
unmatched headings, and the track-2 audio hole remain limitations for
synchronization and require focused playback interpretation. The report alone
cannot establish exact boundary accuracy; that conclusion awaits the frozen
listening check above.
