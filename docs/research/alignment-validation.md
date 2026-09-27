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

## Evaluation run

The evaluation follows the [frozen Issue #15 procedure](protocol.md#frozen-issue-15-evaluation).
Native CTC was frozen after feasibility inspection. Automatic correspondence
was usable, so no chapter-assisted condition or manual alignment correction
was used.

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
cover sections II–VII one-to-one. No section-level correspondence failure or missing track was observed in the
report.

The opening announcement absent from the EPUB appears as a 0–7.96-second
audio-only hole. The six unmatched sentences are the Roman-numeral headings
for sections I and III–VII; section II's heading was marked aligned despite
being spoken as "Hai." The report also contains a 5.8-second loose-audio hole
in track 2 at 1093.06–1098.86 seconds. These are reported output states, not
manually repaired timings. Storyteller's internal scores were not used as an
acceptance criterion.

### Manual boundary verification

MOSS BF16 and Qwen3-ASR F16 through the existing audio.cpp service (image
revision `955c8725c611d511774e6be132aff6609163b2d2`) were convenience tools for
locating and checking clean verification clips, not evaluated routes or timing
references. The repository owner confirmed the four target onsets in 16 kHz
mono signed 16-bit PCM WAV clips decoded from the original tracks. Clip
boundaries fall in quiet regions. The invalid preliminary OGG excerpts were
discarded; they contribute no reported measurement.

| Verification WAV | Source-track start | Source-track end |
| --- | ---: | ---: |
| `track1-s1-to-s2-65.9s.wav` | 65.9 s | 122.7 s |
| `track1-ordinary-s3-467.8s.wav` | 467.8 s | 529.0 s |
| `track2-heading-0s.wav` | 0 s | 34 s |
| `track6-later-904s.wav` | 904 s | 950.5 s |

The WAVs are retained under `data/issue-15/verification/`. The table below
keeps raw Storyteller timestamps separately from the approximately
0.1-second manual references and errors.

| Frozen boundary | Confirmed onset in WAV | Reference on source track | Storyteller `clipBegin` | Approximate signed error | Approximate absolute error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Preface heading, track 1 | 26.3 s | 92.2 s | 91.88 s | -0.3 s | 0.3 s |
| Ordinary narration, track 1 | 26.7 s | 494.5 s | 494.20 s | -0.3 s | 0.3 s |
| Spoken "Hai", track 2 | 1.9 s | 1.9 s | 1.54 s | -0.4 s | 0.4 s |
| "Kim đâu?", track 6 | 13.8 s | 917.8 s | 917.30 s | -0.5 s | 0.5 s |

The first, second, and fourth clip-relative values are the owner's confirmation
of the ASR-located region, rounded to the frozen 0.1-second listening
precision. The owner separately confirmed 1.9 s for the heading after a
waveform-based suggestion. This listening was evaluation assistance; it did
not change chapter mapping, sentence alignment, or Storyteller output.

## Discussion

The automatic route provides complete section correspondence and sentence
timings for this source without chapter assistance. Interpolated sentences,
unmatched headings, and the track-2 audio hole remain limitations for
synchronization and require focused playback interpretation. All four starts
in the fixed, manually verified subset precede the heard boundary by approximately
0.3, 0.3, 0.4, and 0.5 seconds, respectively. This small subset does not establish general boundary accuracy. No
observed blocker requires promoting another ASR route, so native CTC remains
the frozen alignment route for this source.
