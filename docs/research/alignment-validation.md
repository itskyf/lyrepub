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

| Case | Sentence start | Track | Verification clip offset |
| --- | --- | ---: | ---: |
| Cross-document transition | `section_2.html-s0`, "LỜI NÓI ĐẦU" | 1 | 85 s |
| Ordinary narration | `section_3.html-s1`, "Khi bọn Bảo Kim tới Bắc Cung…" | 1 | 487 s |
| Heading verbalization | `section_4.html-s0`, spoken "Hai" for `II` | 2 | 0 s |
| Later long-form location | `section_8.html-s183`, "Kim đâu?" | 6 | 910 s |

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

Independent listening-based boundary-error measurements are pending. The
generated verification clips are retained under `data/issue-15/verification/`.

## Discussion

The automatic route provides complete section correspondence and sentence
timings for this source without chapter assistance. Interpolated sentences,
unmatched headings, and the track-2 audio hole remain limitations for
synchronization and require focused playback interpretation. The report alone
cannot establish exact boundary accuracy; that conclusion awaits the frozen
listening check above.
