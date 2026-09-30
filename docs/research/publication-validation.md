# Final publication reproduction and validation

[Issue #17](https://github.com/itskyf/lyrepub/issues/17) records the publication decisions.
The current #17 sentence records and reusable Opus clips are in `data/silver/issue-17/thang-long-noi-gian/`; benchmark records are in `data/silver/issue-17/tts-benchmark/`, and the regenerated alignment report is in `data/silver/issue-17/dem-hoi-long-tri/report.json`.
The final EPUBs are `data/gold/thang-long-noi-gian.epub` and `data/gold/dem-hoi-long-tri.epub`.
The acquired sources and frozen `data/silver/issue-14/`, `data/silver/issue-14-reported/`, and `data/silver/issue-15/` evidence are unchanged.

## Reproduction

Set `TTS_SOURCE` to the acquired Thăng Long nổi giận EPUB in `data/bronze/`.
Use fresh output directories for a new run.
The Compose audio.cpp configuration loads these assets from `data/models/VieNeu-TTS-v3-Turbo-GGUF/` on CUDA with one inference thread.
Python retains the frozen VieNeu normalization, chunking, phonemization, and audio joining; audio.cpp owns inference.
VieNeu 3.8.3, SEA-G2P 0.10.0, and `zapros[pyreqwest]` 0.19.0 are script-local PEP 723 dependencies, not project or development dependencies.
The inline environment also declares the pinned sentence frontend and its Torch requirement.
The configured audio.cpp server supplies the pinned checkpoint and voice assets; sentence records retain the actual synthesis inputs, seeds, and timings.

```sh
podman compose up --detach audiocpp playwright
TTS_OUT=data/silver/issue-17/thang-long-noi-gian
TTS_WORK=data/work/issue-17/thang-long-noi-gian
TTS_FINAL=data/gold/thang-long-noi-gian.epub
ALIGNMENT_OUT=data/silver/issue-17/dem-hoi-long-tri
ALIGNMENT_WORK=data/work/issue-17/dem-hoi-long-tri
ALIGNMENT_FINAL=data/gold/dem-hoi-long-tri.epub
BENCHMARK_OUT=data/silver/issue-17/tts-benchmark
BENCHMARK_WORK=data/work/issue-17/tts-benchmark

PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_benchmark.py \
  prepare --source-epub "$TTS_SOURCE" --output "$BENCHMARK_OUT"
PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  pixi run -e dev uv run --script scripts/tts_benchmark.py synthesize \
  --output "$BENCHMARK_OUT" --work "$BENCHMARK_WORK"
PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_benchmark.py \
  compare --output "$BENCHMARK_OUT" --frozen data/silver/issue-14

PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  pixi run -e dev uv run --script scripts/tts_publication.py prepare \
  --source "$TTS_SOURCE" --output "$TTS_OUT" --work "$TTS_WORK"
PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_publication.py \
  synthesize --output "$TTS_OUT" --work "$TTS_WORK" --concurrency 1
PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_publication.py \
  publish --source "$TTS_SOURCE" --output "$TTS_OUT" \
  --work "$TTS_WORK" --final "$TTS_FINAL"

mkdir --parents "$ALIGNMENT_OUT" "$ALIGNMENT_WORK"
align process data/bronze/9786326186253 "$ALIGNMENT_WORK/processed-audio" \
  --log-level info
align align --ctc --emissions data/silver/issue-15/emissions \
  --audiobook "$ALIGNMENT_WORK/processed-audio" \
  --epub data/silver/issue-15/markedup.epub --language vi --granularity sentence \
  --reports "$ALIGNMENT_OUT/report.json" \
  --output "$ALIGNMENT_WORK/regenerated.epub" --time --log-level info
pixi run -e dev python -m scripts.publication \
  --source "$ALIGNMENT_WORK/regenerated.epub" --output "$ALIGNMENT_FINAL" \
  --work "$ALIGNMENT_WORK" \
  --frozen-report data/silver/issue-15/report.json \
  --regenerated-report "$ALIGNMENT_OUT/report.json"
```

One Zapros async client with `AsyncPyreqwestHandler` and one semaphore serve the complete synthesis run.
`--concurrency` must be positive and defaults to one; the server serializes inference for its loaded model.
Every request carries the prepared phonemes, bronze block seed, exact UTF-8 chunk budget, and frozen sampling options.
HTTP errors, non-WAV responses, invalid PCM, and preprocessing failures stop the run and remain in its records.
Completed blocks are reused from their saved sentence records and packaged Opus clips.
No Python inference fallback is provided.
Alignment consumes retained emissions rather than rerunning inference, and verifies the frozen report spans and four recorded manual timing boundaries.
The regenerated report matches the frozen report. Opus packaging preserves its SMIL timings before the #17 opening-credit publication repair.

## Runtime and benchmark comparison

The server comparison used the configured audio.cpp endpoint and the frozen source-derived sentence inputs. The endpoint configuration is recorded in `containers/audiocpp.json`; this publication pass does not persist container inspection output.
The server comparison preserves all 118 frozen sentence inputs, frontend chunks, source mappings, and clip durations.
Decoded Opus PCM matches for 117 sentences; `s5-b9` sentence 39 reproduces the previously reviewed full-run recording rather than the older isolated recording.
The differing older isolated waveform is retained, so byte-identical reproduction of all frozen recordings is not claimed.
`benchmark-comparison.json` records each sentence comparison.
The reviewed full-book recording is checked separately from the frozen benchmark.
The earlier full-book run and its comparison records remain separate #17 experimental artifacts. The final publication is rebuilt from the repaired source; no audio-quality acceptance is inferred from repeatability checks.

## Reviewed source repairs and accessibility

The corrected TTS source removes the repeated DTV-Ebook chapter header and the detached duplicate opening fragment found in each chapter. Its separate chapter 12 correction changes `"P hú` to `"Phú`.
`data/work/issue-17/thang-long-noi-gian/corrected-source.epub` is regenerated from Bronze when needed. Source offsets refer to this corrected copy, while inference seeds derive from the matching original bronze blocks.
Deleting `data/work/` and publishing again from the acquired source and retained #17 Silver records produced the final TTS EPUB with 2,929 completed blocks and 10,239 Opus clips.
These edits do not change bronze inputs or frozen benchmark evidence, and exact-text preservation is claimed only outside the reviewed corrections.
The reviewed punctuation joins remain source-preserving sentence-boundary joins.
The TTS input is 48 kHz mono 16-bit PCM WAV (768 kb/s uncompressed). The seven alignment inputs are 44.1 kHz stereo MP3 at approximately 96 kb/s. Both publication paths encode from those inputs with libopus defaults, without a fixed bitrate or forced resampling or channel conversion. No new audio-quality review is claimed.
Alignment title-attribute notes become linked footnotes with backlinks and their original text; duplicate title attributes are removed after materialization.
The #17 alignment publication moves the spoken opening credit to visible cover text and starts biography targeting after it. MOSS placed the biography utterance near track time 20.86 seconds; a local silence boundary was near 20.92 seconds. Thorium playback of the exact Gold EPUB confirmed the credit and biography highlighting behavior, including that the dates do not highlight during the credit. No separate 0.1-second manual onset measurement was recorded. The frozen #15 report and aligned EPUB are unchanged.
The reviewed back-cover transcription is ordinary visible text referenced by a short image alternative, rather than an oversized `alt` attribute.
This transcription is absent from the audiobook, and no narration is added to the alignment pathway.
Source-specific XHTML and stylesheet repairs are limited to their respective publications.
Discovery metadata reflects the known content: textual access for both books, visual access for the alignment book's informative images, and table-of-contents and synchronized-audio features for both.
The alignment book also declares its image alternatives. Inspection of both final EPUBs found static images, no scripted or animated content, and no flashing or motion simulation; the sound-hazard assessment remains unknown.
Neither book declares `accessModeSufficient` while the human review needed to justify textual sufficiency remains incomplete.
Automated results do not establish completed human accessibility review or accessibility conformance.

## Automated validation

```sh
pixi run -e dev python -m pytest -q tests/test_publication.py \
  tests/test_tts_benchmark.py tests/test_sentence_targets.py tests/test_media_overlays.py
pixi run -e dev python -m pytest -q
hk check --pr

mkdir --parents data/work/issue-17/validation
for book in thang-long-noi-gian dem-hoi-long-tri; do
  podman compose run --rm --volume "$PWD/data:/data:ro,z" epubcheck \
    "/data/gold/$book.epub"
  podman compose run --rm --volume "$PWD/data:/data:z" ace \
    "/data/gold/$book.epub" \
    --outdir "/data/work/issue-17/validation/$book-ace" --force
done
```

Normal pytest checks reusable source mapping, coverage, all three approved punctuation joins, fail-closed source corrections, nested navigation, Opus packaging, manifest/SMIL references, and frozen alignment timings using only declared project and dev dependencies.
The full declared dev suite passes 42 tests.
`hk check --pr` passes. FFmpeg and ffprobe are resolved from the Pixi-managed `PATH`; Ruff retains S607 and ignores S603 for the reviewed shell-free subprocess pattern. Normal pytest imports reusable text mapping from `src/lyrepub`; the standalone TTS scripts import their PEP 723 runtime dependencies at module scope and were import-checked through their inline-uv commands.
All 280 files in the retained frozen-evidence checksum inventory remain unchanged.
Actual frontend and inference integration runs through the inline-uv benchmark and publication commands.
Both final EPUBs pass Compose EPUBCheck with zero errors and warnings.
Ace flags the omitted `accessModeSufficient` property, a SHOULD discovery property whose textual claim awaits human review.
The alignment package removes eight unused source resources while retaining its referenced cover, portrait, transcription, and seven audio tracks. Its source SMIL timings are verified against the frozen report before the #17 opening repair.

## Reader validation

The repository Playwright service uses `mcr.microsoft.com/playwright:v1.63.0` and Playwright 1.63.0 `run-server`, with `init`, Chromium host IPC, and a loopback-published port 3000.
Its healthcheck probes that local server port without launching a browser; the 60-second startup allowance follows [Playwright's web-server default](https://playwright.dev/docs/test-webserver).
The mise-managed CLI 0.1.19 supplies a compatible Playwright 1.63 client.
Its npm release and integrity were checked against the upstream tag and npm registry before adding narrowly versioned provenance exceptions for that release and its two published alpha dependencies.
The remote configuration explicitly selects Chromium through the server's supported endpoint query and creates an isolated context.
No browser is installed on the host, and EPUBs transfer through the CLI upload operation without an EPUB volume mount.

Create `data/work/issue-17/browser-review/` and save the following JSON as `cli.config.json` there.

```json
{
  "browser": {
    "browserName": "chromium",
    "isolated": true,
    "remoteEndpoint": "ws://127.0.0.1:3000/?browser=chromium"
  }
}
```

```sh
playwright-cli -s=readest open https://web.readest.com/ \
  --config=data/work/issue-17/browser-review/cli.config.json
playwright-cli -s=readest snapshot
# Select Import Books, then From Local File using the snapshot refs.
playwright-cli -s=readest upload data/gold/dem-hoi-long-tri.epub
playwright-cli -s=readest snapshot
playwright-cli -s=readest console
playwright-cli -s=readest requests
```

Earlier Readest imports of both publications transferred successfully but remained at "Loading…"; a bronze source control imported successfully. The retained browser diagnostics show no EPUB parsing error, and the exact cause of Readest's behavior is unknown.
Manual Thorium Reader review found earlier packages of both publications opened and read successfully, so the Readest observation is reader-specific. The exact rebuilt alignment Gold EPUB has been reopened in Thorium and its opening credit/biography highlighting checked. The rebuilt TTS Gold EPUB still requires its new manual opening and chapter-opening check.
Broader synchronization playback, audio quality, and human accessibility checks remain incomplete. The PR remains draft until the required manual checks are completed.
