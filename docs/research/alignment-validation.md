# Storyteller alignment validation (Issue #15)

## Configuration and inputs

The automatic, full-length run used Storyteller `@storyteller-platform/align` 0.2.4, Node.js 26.10.0, and FFmpeg 9.0.2 on an NVIDIA GeForce RTX 5060 Laptop GPU host.
Storyteller's `--device auto` selected **CPU fp32** for the `ctc-local` MMS route, with batch size 1 and 25-second emission chunks.
The installed checkpoint was `onnx-community/mms-300m-1130-forced-aligner-ONNX`.
No ASR route or manual chapter mapping was used.

The source EPUB is version 2.0.
Storyteller upgraded a temporary copy to EPUB 3 for processing, marked it up at sentence granularity, and copied the original MP3 audio into numbered processed tracks.
Its 120-minute maximum track length did not split any source track.
Source files were read from the main worktree's `data/bronze/9786326186253/` and were not copied into version control.

From the Issue #15 worktree, with `MAIN` set to the main worktree path returned by `git worktree list --porcelain`, the run command was:

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

These generated paths are ignored locally.
The processed-track `.source.json` files and report confirm numeric track order 1–7.
The retained emissions and marked-up EPUB permit diagnosis without repeating model inference.

## Evaluation run

The evaluation follows the [frozen Issue #15 procedure](protocol.md#frozen-issue-15-evaluation).
Native CTC was frozen after feasibility inspection.
Automatic correspondence was usable, so no chapter-assisted condition or manual alignment correction was used.

The reported alignment reused the frozen emissions and marked-up EPUB without rerunning inference:

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

The full pipeline completed on the 16,446.6-second audiobook.
Audio processing took 2.29 seconds, emission generation 24 minutes 33.8 seconds wall time (including about 7 minutes for the initial checkpoint download), markup 262 milliseconds, and pilot EPUB alignment 10.66 seconds.
The reported alignment from retained emissions took 10.85 seconds and produced a byte-identical report.
The aligned EPUB is about 190 MB.
Storyteller aligned all nine narratable spine documents and all seven tracks; the cover and final image-only document were excluded because they contain no text.

The Storyteller report records 3,379 sentence targets: 3,319 aligned, 54 interpolated, six unmatched, and none dropped.
It records 16,181.26 matched audio seconds, 213.18 interpolated seconds, and 13.76 loose seconds.
Track 1 covers the author biography, preface, and section I in sequence; tracks 2–7 cover sections II–VII one-to-one.
No section-level correspondence failure or missing track was observed in the report.

The opening announcement absent from the EPUB appears as a 0–7.96-second audio-only hole.
The six unmatched sentences are the Roman-numeral headings for sections I and III–VII; section II's heading was marked aligned despite being spoken as "Hai."
The report also contains a 5.8-second loose-audio interval in track 2 at 1093.06–1098.86 seconds.
The owner's focused listening identified spoken footnote material: approximately "chú thích là năm 1774, chú thích của tác giả, hết chú thích."
Inspection of the exact `(2)` reference in `OEBPS/Text/section_4.html` (source block 103) found `<a href="note:" title="1774 (chú thích của tác giả)." class="sup"><sup>(2)</sup></a>`.
The note text is present in the EPUB source as the anchor's `title` attribute, but is absent from the narration text used for alignment, which contains only `(2)`.
The retained marked-up EPUB preserves this structure.
Correspondence resumes after the spoken insertion without manual repair.
These are reported output states, not manually repaired timings.
Storyteller's internal scores were not used as an acceptance criterion.

### Manual boundary verification

MOSS and Qwen3-ASR through the existing audio.cpp service were used only to locate and sanity-check verification regions; their timestamps were not timing references or evaluated routes.
The repository owner confirmed the four target onsets in 16 kHz mono signed 16-bit PCM WAV clips decoded from the original tracks.
Clip boundaries fall in quiet regions.
The invalid preliminary OGG excerpts were discarded; they contribute no reported measurement.

| Verification WAV | Source-track start | Source-track end |
| --- | ---: | ---: |
| `track1-s1-to-s2-65.9s.wav` | 65.9 s | 122.7 s |
| `track1-ordinary-s3-467.8s.wav` | 467.8 s | 529.0 s |
| `track2-heading-0s.wav` | 0 s | 34 s |
| `track6-later-904s.wav` | 904 s | 950.5 s |

The WAVs are retained under `data/issue-15/verification/`.
The table below keeps raw Storyteller timestamps separately from the approximately 0.1-second manual references and errors.

| Frozen boundary | Confirmed onset in WAV | Reference on source track | Storyteller `clipBegin` | Approximate signed error | Approximate absolute error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Preface heading, track 1 | 26.3 s | 92.2 s | 91.88 s | -0.3 s | 0.3 s |
| Ordinary narration, track 1 | 26.7 s | 494.5 s | 494.20 s | -0.3 s | 0.3 s |
| Spoken "Hai", track 2 | 1.9 s | 1.9 s | 1.54 s | -0.4 s | 0.4 s |
| "Kim đâu?", track 6 | 13.8 s | 917.8 s | 917.30 s | -0.5 s | 0.5 s |

The repository owner manually confirmed all four clip-relative onsets at the frozen 0.1-second listening precision; ASR and waveform suggestions only helped locate the regions.
This listening was evaluation assistance; it did not change chapter mapping, sentence alignment, or Storyteller output.

## Discussion

The automatic route mapped all nine narratable spine documents to the expected tracks without chapter assistance.
Interpolated sentences, unmatched headings, and the track-2 spoken-footnote insertion remain synchronization limitations.
The insertion is an explained mismatch between the spoken audio and Storyteller's narration text, not evidence of unexplained drift or silence.
The diagnostic context WAV `track2-loose-audio-1075.5s.wav` spans source-track 1075.5–1125.9 seconds, with the reported interval at clip-relative 17.56–23.36 seconds; this listening added no benchmark boundary and changed no system output.
All four starts in the fixed, manually verified subset precede the heard boundary by approximately 0.3, 0.3, 0.4, and 0.5 seconds, respectively.
This small subset does not establish general boundary accuracy.
No material blocker was observed for this experiment, so native CTC is finalized as the frozen Issue #15 route.
